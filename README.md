# Vercel Source Downloader

Application graphique pour télécharger le code source de vos déploiements Vercel.

## Installation

### 1. Installer les dépendances système (Arch Linux)

```bash
sudo pacman -S tk
```

### 2. Créer et activer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

Ou manuellement :

```bash
pip install customtkinter CTkMessagebox
```

## Utilisation

### Méthode 1 : Utiliser le script de lancement

```bash
./run.sh
```

### Méthode 2 : Activer l'environnement virtuel manuellement

```bash
source venv/bin/activate
python3 vercel_dowloader.py
```

## Génération d'un token Vercel

1. Allez sur https://vercel.com/account/tokens
2. Créez un nouveau token
3. Copiez-le dans l'application

## Notes

- Seuls les déploiements effectués via la CLI Vercel peuvent être téléchargés
- Le token peut être sauvegardé localement (optionnel)
- L'application supporte les thèmes sombre, clair et système


