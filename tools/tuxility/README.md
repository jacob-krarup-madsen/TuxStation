# Tuxility

A setup and maintenance assistant for Fedora Silverblue (and other rpm-ostree
desktops like Kinoite or Bazzite). It presents your post-install checklist and
ongoing upkeep tasks as a click-to-run tool — enabling Flathub, installing apps,
layering packages with `rpm-ostree`, applying desktop settings, and keeping the
system updated — so you don't have to remember a wall of commands.

## Features

- Task catalog in a single editable `tasks.toml` — no code needed to add tasks
- Tasks grouped into tabs (Status / System / Applications / Maintenance / …)
- Click-to-run: tick the tasks you want, hit **Run selected**; results appear
  as row icons and toast notifications — no terminal, no log viewer
- **Status** tab renders rpm-ostree deployments, layered packages, and removed
  packages graphically, refreshed after every run
- Tasks can layer packages (`pkexec rpm-ostree`), install Flatpak apps, apply
  `gsettings`, or run any shell command
- `recurring` tasks (updates, cleanup) stay runnable and aren't marked permanent
- Per-task `check` commands mark already-installed/configured items as done
- Done state persisted at `~/.local/state/tuxility.json`
- Confirmation prompts for risky tasks, reboot prompt when an update needs it
- Runs entirely from the immutable base image — nothing to layer

## Requirements

- Fedora Silverblue or any rpm-ostree system
- `python3-gobject`, `gtk4`, `libadwaita` (present in the base image), `pkexec`
- `flatpak`, `rpm-ostree`, and optionally `fwupdmgr` for the default catalog

## Install

```sh
install -m 755 tuxility ~/.local/bin/tuxility
cp tasks.toml ~/.config/tuxility/tasks.toml
cp extras/tuxility.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/
```

Or just run `./tuxility` from the repo. The script looks for tasks in
`~/.config/tuxility/tasks.toml` first, then next to the script.

## Usage

- **Check** — re-evaluate every task's `check` command and refresh the done marks
- **Run selected** — execute the ticked tasks in order; each finishes with a
  toast and a row icon (checkmark on success, error on failure)
- **Status** tab — current deployment, layered packages, and removed packages
  (use its **Refresh** button to re-read)
- Menu (⋮): **Select all**, **Clear selection**, **Reset done state**
- Shortcuts: `F5` check, `Ctrl+Enter` run selected, `Ctrl+A` / `Ctrl+Shift+A`
  select / clear all

`tuxility --list` prints the catalog for quick review; `tuxility --help`
shows usage.

## Writing tasks

`tasks.toml` groups tasks under `[[group]]` (one tab each); each task is a
`[[group.item]]`:

```toml
[[group.item]]
id = "my-app"                    # unique id, used for the done state
name = "My app"                  # row title
detail = "One-line description"  # row subtitle
command = "flatpak install --user -y flathub org.example.App"   # what to run
sudo = false                     # run via pkexec (e.g. rpm-ostree layer)
check = "flatpak info --user org.example.App >/dev/null 2>&1"   # exit 0 = done
reboot = false                   # warn + offer reboot after the run
recurring = false                # never store as permanently done
confirm = "Explain what this does"   # optional pre-run confirmation text
```

`command` and `check` are shell strings (run with `bash -lc`). Tasks with
`sudo = true` are wrapped in `pkexec`, which pops the polkit password dialog.
