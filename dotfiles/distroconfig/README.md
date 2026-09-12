# distroconfig

Recreate my Fedora Silverblue setup on a new machine.

## What's tracked

- **packages/flatpaks.txt** — Flatpak application IDs
- **packages/rpm-ostree.txt** — rpm-ostree layered packages
- **gnome/extensions.txt** — GNOME Shell extensions
- **gnome/dconf-settings.ini** — GNOME desktop settings (dconf dump)
- **dotfiles/** — Git config, shell config, etc.

## Quick start

```bash
git clone https://github.com/jacob/distroconfig.git
cd distroconfig
python3 app.py
```

## Requirements

- Python 3 with GTK 4 and libadwaita (pre-installed on Fedora Silverblue)
- flatpak, rpm-ostree, dconf, gnome-extensions (all pre-installed on Silverblue)

## Usage

### Setting up a new machine

1. Clone this repo
2. Run `python3 app.py`
3. Use the tabs to select what to install:
   - **Flatpaks** — Toggle switches, click Install/Uninstall
   - **Packages** — Toggle rpm-ostree layers (requires reboot)
   - **Extensions** — Enable/disable GNOME extensions
   - **GNOME & Dots** — Apply dconf settings and deploy dotfiles

### Updating from your current system

1. Open the GUI and click **Rescan System**
2. This re-scans installed flatpaks, extensions, and dconf settings
3. Review with `git diff` and commit

## Structure

```
distroconfig/
├── app.py                       # GUI application
├── packages/
│   ├── flatpaks.txt             # Flatpak app IDs (one per line)
│   └── rpm-ostree.txt           # rpm-ostree packages (one per line)
├── gnome/
│   ├── extensions.txt           # GNOME Shell extensions
│   └── dconf-settings.ini       # dconf dump
└── dotfiles/
    └── gitconfig                # Git configuration
```
