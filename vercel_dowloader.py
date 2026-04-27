#!/usr/bin/env python3
"""
Vercel Deployment Source Downloader - Version Moderne
======================================================
Nécessite: pip install customtkinter
"""

import base64
import json
import os
import sys
import threading
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from datetime import datetime

try:
    import customtkinter as ctk
    try:
        from CTkMessagebox import CTkMessagebox
        HAS_MSGBOX = True
    except ImportError:
        HAS_MSGBOX = False
except ImportError:
    ctk = None
    HAS_MSGBOX = False

# Configuration
CONFIG_FILE = Path.home() / ".vercel_downloader_config.json"
if ctk:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except:
        pass


def show_message(title, message, icon="info"):
    """Affiche un message (avec ou sans CTkMessagebox)"""
    if HAS_MSGBOX:
        CTkMessagebox(title=title, message=message, icon=icon)
    else:
        # Fallback simple
        dialog = ctk.CTkToplevel()
        dialog.title(title)
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text=message, wraplength=350).pack(pady=30, padx=20)
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy, width=100).pack(pady=10)
        
        dialog.after(100, dialog.focus_force)


class VercelAPI:
    """Client pour l'API Vercel"""
    
    BASE_URL = "https://api.vercel.com"
    
    def __init__(self, token: str, team_id: Optional[str] = None):
        self.token = token
        self.team_id = team_id
    
    def _make_request(self, endpoint: str, method: str = "GET") -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        
        if self.team_id:
            separator = "&" if "?" in url else "?"
            url += f"{separator}teamId={self.team_id}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        request = Request(url, headers=headers, method=method)
        
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    
    def _get_file_content(self, deployment_id: str, file_id: str) -> bytes:
        url = f"{self.BASE_URL}/v7/deployments/{deployment_id}/files/{file_id}"
        
        if self.team_id:
            url += f"?teamId={self.team_id}"
        
        headers = {"Authorization": f"Bearer {self.token}"}
        request = Request(url, headers=headers)
        
        try:
            with urlopen(request, timeout=30) as response:
                content_type = response.headers.get('Content-Type', '')
                raw_data = response.read()
                
                if 'application/json' in content_type:
                    try:
                        json_data = json.loads(raw_data.decode())
                        if isinstance(json_data, dict) and 'data' in json_data:
                            return base64.b64decode(json_data['data'])
                    except:
                        pass
                return raw_data
        except HTTPError as e:
            if e.code == 404:
                return b""
            raise
    
    def list_projects(self) -> list:
        all_projects = []
        endpoint = "/v9/projects?limit=100"
        while endpoint:
            result = self._make_request(endpoint)
            all_projects.extend(result.get("projects", []))
            pagination = result.get("pagination", {})
            next_cursor = pagination.get("next")
            if next_cursor:
                endpoint = f"/v9/projects?limit=100&until={next_cursor}"
            else:
                endpoint = None
        return all_projects
    
    def list_deployments(self, project_id: Optional[str] = None, limit: int = 50) -> list:
        endpoint = f"/v6/deployments?limit={limit}"
        if project_id:
            endpoint += f"&projectId={project_id}"
        result = self._make_request(endpoint)
        return result.get("deployments", [])
    
    def list_deployment_files(self, deployment_id: str) -> list:
        return self._make_request(f"/v6/deployments/{deployment_id}/files")
    
    def download_deployment(self, deployment_id: str, output_dir: str, 
                           callback=None, progress_callback=None) -> int:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        files = self.list_deployment_files(deployment_id)
        
        if not files:
            raise Exception("Aucun fichier source trouvé.\nSeuls les déploiements via CLI sont récupérables.")
        
        total_files = self._count_files(files)
        downloaded = [0]
        
        self._download_files_recursive(deployment_id, files, output_path, "", 
                                       callback, progress_callback, total_files, downloaded)
        return downloaded[0]
    
    def _count_files(self, files: list) -> int:
        count = 0
        for item in files:
            if item.get("type") == "file":
                count += 1
            elif item.get("type") == "directory":
                count += self._count_files(item.get("children", []))
        return count
    
    def _download_files_recursive(self, deployment_id: str, files: list, 
                                   base_path: Path, current_path: str, callback=None, 
                                   progress_callback=None, total_files=0, downloaded=None):
        for item in files:
            name = item.get("name", "")
            item_type = item.get("type", "")
            uid = item.get("uid", "")
            
            full_path = f"{current_path}/{name}" if current_path else name
            local_path = base_path / full_path
            
            if item_type == "directory":
                local_path.mkdir(parents=True, exist_ok=True)
                children = item.get("children", [])
                if children:
                    self._download_files_recursive(deployment_id, children, 
                                                   base_path, full_path, callback,
                                                   progress_callback, total_files, downloaded)
            elif item_type == "file" and uid:
                if callback:
                    callback(full_path)
                try:
                    content = self._get_file_content(deployment_id, uid)
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    local_path.write_bytes(content)
                    if downloaded is not None:
                        downloaded[0] += 1
                        if progress_callback and total_files > 0:
                            progress_callback(downloaded[0], total_files)
                except Exception as e:
                    if callback:
                        callback(f"⚠️ Erreur: {full_path}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Config fenêtre
        self.title("Vercel Source Downloader")
        self.geometry("900x750")
        self.minsize(700, 600)
        
        # Variables
        self.config_data = load_config()
        self.api = None
        self.projects = []
        self.deployments = []
        self.is_connected = False
        
        # Grid config
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Container principal avec scroll
        self.main_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", 
                                                  scrollbar_button_color=("gray70", "gray30"),
                                                  scrollbar_button_hover_color=("gray80", "gray20"))
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Bindings pour le scroll avec la molette de la souris (compatible i3-wm)
        # Bind directement sur le frame scrollable et tous ses enfants
        self._setup_scroll_bindings()
        
        self.create_ui()
        
        # Configurer les bindings de scroll après création de l'UI
        self.after(100, self._setup_scroll_bindings)
        
        # Auto-connect si token sauvegardé
        if self.config_data.get("token"):
            self.token_entry.insert(0, self.config_data["token"])
            if self.config_data.get("team_id"):
                self.team_entry.insert(0, self.config_data["team_id"])
            self.save_token_var.set(True)
            self.after(500, self.connect)
    
    def create_ui(self):
        # === HEADER ===
        self.create_header()
        
        # === SECTION CONNEXION ===
        self.create_connection_section()
        
        # === SECTION PROJET ===
        self.create_project_section()
        
        # === SECTION TÉLÉCHARGEMENT ===
        self.create_download_section()
        
        # === FOOTER ===
        self.create_footer()
    
    def create_header(self):
        header = ctk.CTkFrame(self.main_frame, fg_color="#1a1a2e", corner_radius=15)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header.grid_columnconfigure(0, weight=1)
        
        # Logo + Titre
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.grid(row=0, column=0, pady=25)
        
        # Triangle Vercel
        logo = ctk.CTkLabel(title_frame, text="▲", font=ctk.CTkFont(size=40, weight="bold"),
                           text_color="#ffffff")
        logo.pack(side="left", padx=(0, 15))
        
        text_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        text_frame.pack(side="left")
        
        ctk.CTkLabel(text_frame, text="Vercel Source Downloader",
                    font=ctk.CTkFont(size=24, weight="bold"),
                    text_color="#ffffff").pack(anchor="w")
        
        ctk.CTkLabel(text_frame, text="Récupérez le code source de vos déploiements",
                    font=ctk.CTkFont(size=13),
                    text_color="#888888").pack(anchor="w")
    
    def create_connection_section(self):
        # Card
        card = ctk.CTkFrame(self.main_frame, corner_radius=15)
        card.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        card.grid_columnconfigure(0, weight=1)
        
        # Header de la card
        card_header = ctk.CTkFrame(card, fg_color="transparent")
        card_header.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 15))
        card_header.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(card_header, text="🔐", font=ctk.CTkFont(size=20)).grid(row=0, column=0, padx=(0, 10))
        ctk.CTkLabel(card_header, text="Connexion", 
                    font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=1, sticky="w")
        
        self.connection_status = ctk.CTkLabel(card_header, text="", 
                                             font=ctk.CTkFont(size=12))
        self.connection_status.grid(row=0, column=2, sticky="e")
        
        # Contenu
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=25, pady=(0, 20))
        content.grid_columnconfigure(1, weight=1)
        
        # Token
        ctk.CTkLabel(content, text="Token Vercel", 
                    font=ctk.CTkFont(size=13)).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        token_frame = ctk.CTkFrame(content, fg_color="transparent")
        token_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        token_frame.grid_columnconfigure(0, weight=1)
        
        self.token_entry = ctk.CTkEntry(token_frame, placeholder_text="Entrez votre token...",
                                       show="●", height=45, font=ctk.CTkFont(size=14))
        self.token_entry.grid(row=0, column=0, sticky="ew")
        
        self.show_token_btn = ctk.CTkButton(token_frame, text="👁", width=45, height=45,
                                           command=self.toggle_token, fg_color="transparent",
                                           hover_color=("gray75", "gray25"))
        self.show_token_btn.grid(row=0, column=1, padx=(10, 0))
        
        # Team ID
        ctk.CTkLabel(content, text="Team ID (optionnel)", 
                    font=ctk.CTkFont(size=13)).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 5))
        
        self.team_entry = ctk.CTkEntry(content, placeholder_text="team_xxxxx",
                                      height=45, font=ctk.CTkFont(size=14))
        self.team_entry.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        # Options
        options_frame = ctk.CTkFrame(content, fg_color="transparent")
        options_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        self.save_token_var = ctk.BooleanVar(value=False)
        self.save_token_check = ctk.CTkCheckBox(options_frame, text="Sauvegarder le token",
                                               variable=self.save_token_var,
                                               font=ctk.CTkFont(size=13),
                                               command=self.on_save_changed)
        self.save_token_check.pack(side="left")
        
        # Bouton connexion
        self.connect_btn = ctk.CTkButton(content, text="Se connecter", height=45,
                                        font=ctk.CTkFont(size=15, weight="bold"),
                                        command=self.connect)
        self.connect_btn.grid(row=5, column=0, columnspan=2, sticky="ew")
    
    def create_project_section(self):
        # Card
        self.project_card = ctk.CTkFrame(self.main_frame, corner_radius=15)
        self.project_card.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.project_card.grid_columnconfigure(0, weight=1)
        
        # Header
        card_header = ctk.CTkFrame(self.project_card, fg_color="transparent")
        card_header.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 15))
        
        ctk.CTkLabel(card_header, text="📦", font=ctk.CTkFont(size=20)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(card_header, text="Sélection", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        # Contenu
        content = ctk.CTkFrame(self.project_card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=25, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        
        # Projet
        ctk.CTkLabel(content, text="Projet", 
                    font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        self.project_menu = ctk.CTkComboBox(content, values=["Connectez-vous d'abord..."],
                                            height=45, font=ctk.CTkFont(size=14),
                                            command=self.on_project_selected,
                                            state="disabled")
        self.project_menu.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        # Déploiement
        ctk.CTkLabel(content, text="Déploiement", 
                    font=ctk.CTkFont(size=13)).grid(row=2, column=0, sticky="w", pady=(0, 5))
        
        self.deployment_menu = ctk.CTkOptionMenu(content, values=["Sélectionnez un projet..."],
                                                height=45, font=ctk.CTkFont(size=14),
                                                command=self.on_deployment_selected,
                                                state="disabled",
                                                dynamic_resizing=False)
        self.deployment_menu.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        # Info déploiement
        self.deploy_info_frame = ctk.CTkFrame(content, fg_color=("gray90", "gray17"), corner_radius=10)
        self.deploy_info_frame.grid(row=4, column=0, sticky="ew")
        self.deploy_info_frame.grid_columnconfigure(0, weight=1)
        
        self.deploy_info = ctk.CTkLabel(self.deploy_info_frame, text="Aucun déploiement sélectionné",
                                       font=ctk.CTkFont(size=12), text_color="gray")
        self.deploy_info.grid(row=0, column=0, pady=12, padx=15, sticky="w")
    
    def create_download_section(self):
        # Card
        self.download_card = ctk.CTkFrame(self.main_frame, corner_radius=15)
        self.download_card.grid(row=3, column=0, sticky="ew", pady=(0, 15))
        self.download_card.grid_columnconfigure(0, weight=1)
        
        # Header
        card_header = ctk.CTkFrame(self.download_card, fg_color="transparent")
        card_header.grid(row=0, column=0, sticky="ew", padx=25, pady=(20, 15))
        
        ctk.CTkLabel(card_header, text="⬇️", font=ctk.CTkFont(size=20)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(card_header, text="Téléchargement", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        
        # Contenu
        content = ctk.CTkFrame(self.download_card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=25, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        
        # Dossier de sortie
        ctk.CTkLabel(content, text="Dossier de destination", 
                    font=ctk.CTkFont(size=13)).grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        output_frame = ctk.CTkFrame(content, fg_color="transparent")
        output_frame.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        output_frame.grid_columnconfigure(0, weight=1)
        
        default_path = str(Path.home() / "WEBSITE_PROJECT")
        self.output_entry = ctk.CTkEntry(output_frame, placeholder_text=default_path,
                                        height=45, font=ctk.CTkFont(size=14))
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_entry.insert(0, default_path)
        
        self.browse_btn = ctk.CTkButton(output_frame, text="📂 Parcourir", width=120, height=45,
                                       command=self.browse_output)
        self.browse_btn.grid(row=0, column=1, padx=(10, 0))
        
        # Progress section
        self.progress_frame = ctk.CTkFrame(content, fg_color=("gray90", "gray17"), corner_radius=10)
        self.progress_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        self.progress_frame.grid_columnconfigure(0, weight=1)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Prêt à télécharger",
                                          font=ctk.CTkFont(size=13))
        self.progress_label.grid(row=0, column=0, pady=(15, 5), padx=15, sticky="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=12)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 5))
        self.progress_bar.set(0)
        
        self.file_label = ctk.CTkLabel(self.progress_frame, text="",
                                      font=ctk.CTkFont(size=11), text_color="gray")
        self.file_label.grid(row=2, column=0, pady=(0, 15), padx=15, sticky="w")
        
        # Bouton télécharger
        self.download_btn = ctk.CTkButton(content, text="⬇️  Télécharger le code source", 
                                         height=50, font=ctk.CTkFont(size=16, weight="bold"),
                                         command=self.download, state="disabled",
                                         fg_color="#10b981", hover_color="#059669")
        self.download_btn.grid(row=3, column=0, sticky="ew")
    
    def create_footer(self):
        footer = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        footer.grid_columnconfigure(0, weight=1)
        
        # Thème
        theme_frame = ctk.CTkFrame(footer, fg_color="transparent")
        theme_frame.grid(row=0, column=0)
        
        ctk.CTkLabel(theme_frame, text="Thème:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 10))
        
        self.theme_menu = ctk.CTkOptionMenu(theme_frame, values=["Sombre", "Clair", "Système"],
                                           command=self.change_theme, width=100, height=30)
        self.theme_menu.pack(side="left")
        self.theme_menu.set("Sombre")
        
        # Lien
        link = ctk.CTkLabel(footer, text="🔗 Générer un token sur vercel.com/account/tokens",
                           font=ctk.CTkFont(size=12), text_color="gray", cursor="hand2")
        link.grid(row=1, column=0, pady=(15, 0))
        link.bind("<Button-1>", lambda e: self.open_link("https://vercel.com/account/tokens"))
        link.bind("<Enter>", lambda e: link.configure(text_color=("gray10", "gray90")))
        link.bind("<Leave>", lambda e: link.configure(text_color="gray"))
    
    # === ACTIONS ===
    
    def _setup_scroll_bindings(self):
        """Configure les bindings de scroll pour le CTkScrollableFrame (compatible i3-wm)"""
        def _on_mousewheel(event):
            """Gère le scroll avec la molette de la souris"""
            try:
                # Accéder au canvas interne du CTkScrollableFrame
                # CTkScrollableFrame utilise un canvas interne accessible via _parent_canvas
                if hasattr(self.main_frame, '_parent_canvas'):
                    canvas = self.main_frame._parent_canvas
                else:
                    # Fallback: chercher le canvas dans les enfants
                    canvas = None
                    for widget in self.main_frame.winfo_children():
                        widget_type = str(type(widget))
                        if 'Canvas' in widget_type:
                            canvas = widget
                            break
                    
                    if canvas is None:
                        # Chercher récursivement
                        def find_canvas(widget):
                            for child in widget.winfo_children():
                                if 'Canvas' in str(type(child)):
                                    return child
                                result = find_canvas(child)
                                if result:
                                    return result
                            return None
                        canvas = find_canvas(self.main_frame)
                
                if canvas:
                    # Linux/i3-wm utilise Button-4 (haut) et Button-5 (bas)
                    if event.num == 4:
                        canvas.yview_scroll(-1, "units")
                    elif event.num == 5:
                        canvas.yview_scroll(1, "units")
                    elif hasattr(event, 'delta'):
                        # Windows/Mac
                        delta = event.delta
                        scroll_amount = abs(delta) // 120  # Normaliser le delta
                        if delta > 0:
                            canvas.yview_scroll(-scroll_amount, "units")
                        else:
                            canvas.yview_scroll(scroll_amount, "units")
            except Exception as e:
                # En cas d'erreur, ignorer silencieusement
                pass
            return "break"
        
        # Bind sur la fenêtre principale et le frame scrollable
        self.bind_all("<Button-4>", _on_mousewheel)  # Molette vers le haut (Linux/i3-wm)
        self.bind_all("<Button-5>", _on_mousewheel)  # Molette vers le bas (Linux/i3-wm)
        self.bind_all("<MouseWheel>", _on_mousewheel)  # Molette (Windows/Mac)
        
        # Bind également directement sur le frame scrollable
        self.main_frame.bind("<Button-4>", _on_mousewheel)
        self.main_frame.bind("<Button-5>", _on_mousewheel)
        self.main_frame.bind("<MouseWheel>", _on_mousewheel)
        
        # Bind sur tous les widgets enfants du frame scrollable
        def bind_recursive(widget):
            widget.bind("<Button-4>", _on_mousewheel)
            widget.bind("<Button-5>", _on_mousewheel)
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                bind_recursive(child)
        
        bind_recursive(self.main_frame)
    
    def toggle_token(self):
        current = self.token_entry.cget("show")
        self.token_entry.configure(show="" if current == "●" else "●")
        self.show_token_btn.configure(text="🔒" if current == "●" else "👁")
    
    def on_save_changed(self):
        if not self.save_token_var.get():
            self.config_data.pop("token", None)
            self.config_data.pop("team_id", None)
            save_config(self.config_data)
    
    def change_theme(self, choice):
        themes = {"Sombre": "dark", "Clair": "light", "Système": "system"}
        ctk.set_appearance_mode(themes.get(choice, "dark"))
    
    def open_link(self, url):
        import webbrowser
        webbrowser.open(url)
    
    def browse_output(self):
        folder = ctk.filedialog.askdirectory()
        if folder:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folder)
    
    def update_connection_status(self, text, color="gray"):
        self.connection_status.configure(text=text, text_color=color)
    
    def connect(self):
        token = self.token_entry.get().strip()
        team_id = self.team_entry.get().strip() or None
        
        if not token:
            self.update_connection_status("❌ Token requis", "#ef4444")
            return
        
        self.update_connection_status("🔄 Connexion...", "#f59e0b")
        self.connect_btn.configure(state="disabled", text="Connexion...")
        
        def do_connect():
            try:
                self.api = VercelAPI(token, team_id)
                self.projects = self.api.list_projects()
                
                if self.save_token_var.get():
                    self.config_data["token"] = token
                    if team_id:
                        self.config_data["team_id"] = team_id
                    save_config(self.config_data)
                
                self.after(0, self.on_connect_success)
            except Exception as e:
                self.after(0, lambda: self.on_connect_error(str(e)))
        
        threading.Thread(target=do_connect, daemon=True).start()
    
    def on_connect_success(self):
        self.is_connected = True
        self.connect_btn.configure(state="normal", text="✓ Connecté")
        self.update_connection_status(f"✅ {len(self.projects)} projet(s)", "#10b981")
        
        # Mettre à jour le menu des projets
        project_names = [p.get("name", "N/A") for p in self.projects]
        if project_names:
            self.project_menu.configure(values=project_names, state="normal")
            self.project_menu.set(project_names[0])
            self.on_project_selected(project_names[0])
    
    def on_connect_error(self, error):
        self.connect_btn.configure(state="normal", text="Se connecter")
        self.update_connection_status("❌ Erreur", "#ef4444")
        show_message("Erreur de connexion", error, "cancel")
    
    def on_project_selected(self, choice):
        # Trouver le projet
        project = next((p for p in self.projects if p.get("name") == choice), None)
        if not project:
            return
        
        self.deployment_menu.configure(state="disabled")
        self.deployment_menu.set("Chargement...")
        self.download_btn.configure(state="disabled")
        
        def do_load():
            try:
                self.deployments = self.api.list_deployments(project.get("id"), limit=50)
                self.after(0, self.on_deployments_loaded)
            except Exception as e:
                self.after(0, lambda: self.deployment_menu.set("Erreur"))
        
        threading.Thread(target=do_load, daemon=True).start()
    
    def on_deployments_loaded(self):
        if not self.deployments:
            self.deployment_menu.set("Aucun déploiement")
            return
        
        deployment_items = []
        for d in self.deployments:
            url = d.get("url", "N/A")
            state = d.get("state", "")
            icon = "✅" if state == "READY" else "❌" if state == "ERROR" else "⏳"
            deployment_items.append(f"{icon} {url}")
        
        self.deployment_menu.configure(values=deployment_items, state="normal")
        self.deployment_menu.set(deployment_items[0])
        self.download_btn.configure(state="normal")
        self.on_deployment_selected(deployment_items[0])
    
    def on_deployment_selected(self, choice):
        # Trouver l'index
        idx = next((i for i, d in enumerate(self.deployments) 
                   if choice.endswith(d.get("url", ""))), 0)
        
        if idx < len(self.deployments):
            d = self.deployments[idx]
            created = d.get("created", 0)
            dt = datetime.fromtimestamp(created / 1000) if created else None
            date_str = dt.strftime("%d/%m/%Y à %H:%M") if dt else "N/A"
            state = d.get("state", "N/A")
            
            self.deploy_info.configure(
                text=f"📅 {date_str}   •   🔖 {state}   •   🆔 {d.get('uid', 'N/A')[:20]}..."
            )
    
    def download(self):
        # Trouver le déploiement sélectionné
        current = self.deployment_menu.get()
        idx = next((i for i, d in enumerate(self.deployments) 
                   if current.endswith(d.get("url", ""))), 0)
        
        if idx >= len(self.deployments):
            return
        
        deployment = self.deployments[idx]
        deployment_id = deployment.get("uid")
        output_dir = self.output_entry.get().strip()

        if not output_dir:
            output_dir = str(Path.home() / "WEBSITE_PROJECT")

        # Ajouter le nom du projet comme sous-dossier
        project_name = self.project_menu.get()
        if project_name:
            output_dir = str(Path(output_dir) / project_name)

        # Supprimer le dossier existant pour actualiser
        output_path = Path(output_dir)
        if output_path.exists():
            import shutil
            shutil.rmtree(output_path)
        
        # Reset progress
        self.progress_bar.set(0)
        self.progress_label.configure(text="Préparation...")
        self.file_label.configure(text="")
        self.download_btn.configure(state="disabled", text="Téléchargement...")
        
        def update_file(filename):
            self.after(0, lambda: self.file_label.configure(text=f"📄 {filename}"))
        
        def update_progress(current, total):
            progress = current / total
            self.after(0, lambda: self.progress_bar.set(progress))
            self.after(0, lambda: self.progress_label.configure(
                text=f"Téléchargement: {current}/{total} fichiers ({progress*100:.0f}%)"
            ))
        
        def do_download():
            try:
                count = self.api.download_deployment(deployment_id, output_dir,
                                                    callback=update_file,
                                                    progress_callback=update_progress)
                self.after(0, lambda: self.on_download_success(count, output_dir))
            except Exception as e:
                self.after(0, lambda: self.on_download_error(str(e)))
        
        threading.Thread(target=do_download, daemon=True).start()
    
    def on_download_success(self, count, output_dir):
        self.download_btn.configure(state="normal", text="⬇️  Télécharger le code source")
        self.progress_bar.set(1)
        self.progress_label.configure(text=f"✅ Terminé! {count} fichier(s) téléchargé(s)")
        self.file_label.configure(text=f"📂 {output_dir}")
        
        # Ouvrir le dossier
        if sys.platform == "win32":
            os.startfile(output_dir)
        elif sys.platform == "darwin":
            os.system(f'open "{output_dir}"')
        else:
            os.system(f'xdg-open "{output_dir}"')
    
    def on_download_error(self, error):
        self.download_btn.configure(state="normal", text="⬇️  Télécharger le code source")
        self.progress_bar.set(0)
        self.progress_label.configure(text="❌ Erreur")
        self.file_label.configure(text=error)
        show_message("Erreur", error, "cancel")


def main():
    # Vérifier si customtkinter est installé
    if ctk is None:
        print("=" * 60)
        print("CustomTkinter n'est pas installé!")
        print("Installez-le avec: pip install customtkinter")
        print("Ou utilisez l'environnement virtuel: source venv/bin/activate")
        print("=" * 60)
        
        # Fallback: proposer l'installation
        import subprocess
        response = input("\nVoulez-vous l'installer maintenant? (o/n): ")
        if response.lower() in ["o", "oui", "y", "yes"]:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
            print("\n✅ Installation terminée! Relancez le script.")
        sys.exit(1)
    
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()