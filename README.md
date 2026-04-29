# Vercel Downloader

A desktop GUI application to download source code from Vercel deployments. Useful for retrieving projects deployed via Vercel CLI that may not be in version control.

**[Portfolio](https://jimmmy-portfolio.vercel.app)**

---

## Features

- **Modern GUI** — Clean interface built with CustomTkinter
- **Token Management** — Secure local storage with visibility toggle
- **Team Support** — Optional Team ID for team-based Vercel accounts
- **Project Browser** — Dropdown to browse all available Vercel projects
- **Deployment History** — View up to 50 recent deployments with metadata (date, state, ID)
- **Progress Tracking** — Real-time progress bar with file count and current file name
- **Auto-Open** — Opens the downloaded folder in file explorer on completion
- **Theme Support** — Light, Dark, and System appearance modes
- **Cross-Platform** — Works on Windows, macOS, and Linux

## Screenshots

> Screenshots coming soon

## Tech Stack

- **Python 3.6+**
- **CustomTkinter** — Modern GUI framework
- **CTkMessagebox** — Dialog boxes
- **Vercel REST API**

## Getting Started

### Prerequisites

```bash
# Arch Linux
sudo pacman -S tk

# Ubuntu/Debian
sudo apt-get install python3-tk
```

### Installation

```bash
git clone https://github.com/jimmy-ngome/Vercel-Downloader.git
cd Vercel-Downloader
pip install -r requirements.txt
```

### Run

```bash
python vercel_dowloader.py
```

Or use the launch script:

```bash
./run.sh
```

### Getting a Vercel Token

1. Go to [vercel.com/account/tokens](https://vercel.com/account/tokens)
2. Create a new personal access token
3. Paste it in the app's token field
4. Optionally check "Save token" to persist locally

## How It Works

1. Enter your Vercel API token
2. Select a project from the dropdown
3. Choose a deployment from the history
4. Pick a download destination
5. Click download — files are fetched and saved with the original directory structure

## License

MIT
