#!/usr/bin/env python3
"""distroconfig - Fedora Silverblue setup GUI"""

import os
import subprocess
import shutil
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Gio

APP_ID = "io.github.jacob.distroconfig"
SCRIPT_DIR = Path(__file__).resolve().parent


# ── Backend ──────────────────────────────────────────────────────────────────

class PackageManager:
    """Reads/writes package lists and talks to the system."""

    def __init__(self):
        self.packages_dir = SCRIPT_DIR / "packages"
        self.gnome_dir = SCRIPT_DIR / "gnome"
        self.dotfiles_dir = SCRIPT_DIR / "dotfiles"

    def read_flatpaks(self):
        return self._read_list(self.packages_dir / "flatpaks.txt")

    def read_rpm_ostree(self):
        return self._read_list(self.packages_dir / "rpm-ostree.txt")

    def read_gnome_extensions(self):
        return self._read_list(self.gnome_dir / "extensions.txt")

    def write_flatpaks(self, items):
        self._write_list(self.packages_dir / "flatpaks.txt", items, "Flatpak applications", "application-id")

    def write_rpm_ostree(self, items):
        self._write_list(self.packages_dir / "rpm-ostree.txt", items, "rpm-ostree layered packages", "package name")

    def write_gnome_extensions(self, items):
        self._write_list(self.gnome_dir / "extensions.txt", items, "GNOME Shell extensions", "extension-name")

    def installed_flatpaks(self):
        try:
            out = subprocess.check_output(
                ["flatpak", "list", "--app", "--columns=application"],
                text=True, stderr=subprocess.DEVNULL,
            )
            return {line.strip() for line in out.splitlines() if line.strip()}
        except Exception:
            return set()

    def layered_rpms(self):
        try:
            out = subprocess.check_output(["rpm-ostree", "status"], text=True, stderr=subprocess.DEVNULL)
            packages = set()
            in_layered = False
            for line in out.splitlines():
                if "LayeredPackages:" in line:
                    in_layered = True
                    part = line.split("LayeredPackages:", 1)[1].strip()
                    if part:
                        packages.update(part.split())
                    continue
                if in_layered:
                    if line.strip().startswith("LocalPackages:"):
                        in_layered = False
                        continue
                    if line.startswith(" ") or line.startswith("\t"):
                        packages.update(line.strip().split())
                    else:
                        in_layered = False
            return packages
        except Exception:
            return set()

    def installed_gnome_extensions(self):
        try:
            out = subprocess.check_output(
                ["gnome-extensions", "list"],
                text=True, stderr=subprocess.DEVNULL,
            )
            return {line.strip() for line in out.splitlines() if line.strip()}
        except Exception:
            return set()

    def enabled_gnome_extensions(self):
        try:
            out = subprocess.check_output(
                ["gsettings", "get", "org.gnome.shell", "enabled-extensions"],
                text=True, stderr=subprocess.DEVNULL,
            )
            raw = out.strip()
            if raw == "@as []":
                return set()
            items = raw.strip("[]").split(",")
            return {s.strip().strip("'\"") for s in items if s.strip()}
        except Exception:
            return set()

    def dconf_file(self):
        return self.gnome_dir / "dconf-settings.ini"

    def install_flatpak(self, app_id):
        return subprocess.run(
            ["flatpak", "install", "-y", "flathub", app_id],
            capture_output=True, text=True,
        )

    def uninstall_flatpak(self, app_id):
        return subprocess.run(
            ["flatpak", "uninstall", "-y", app_id],
            capture_output=True, text=True,
        )

    def install_rpm_ostree(self, packages):
        return subprocess.run(
            ["sudo", "rpm-ostree", "install"] + packages,
            capture_output=True, text=True,
        )

    def apply_dconf(self):
        dconf_file = self.dconf_file()
        if not dconf_file.exists():
            return False, "dconf-settings.ini not found"
        result = subprocess.run(
            ["dconf", "load", "/"],
            input=dconf_file.read_text(), text=True,
            capture_output=True,
        )
        return result.returncode == 0, result.stderr

    DOTFILE_MAP = {
        "gitconfig": ".gitconfig",
        "bashrc": ".bashrc",
        "bash_profile": ".bash_profile",
        "profile": ".profile",
        "zshrc": ".zshrc",
        "zprofile": ".zprofile",
    }

    def deploy_dotfiles(self):
        deployed = []
        for f in self.dotfiles_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                if f.name in self.DOTFILE_MAP:
                    dest = Path.home() / self.DOTFILE_MAP[f.name]
                else:
                    dest = Path.home() / ".config" / f.name

                if dest.exists():
                    backup = dest.with_suffix(dest.suffix + f".backup")
                    shutil.copy2(dest, backup)

                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                deployed.append(f"{f.name} -> {dest}")
        return deployed

    def backup_dotfiles(self):
        backed_up = []
        self.dotfiles_dir.mkdir(parents=True, exist_ok=True)
        for name, home_name in self.DOTFILE_MAP.items():
            src = Path.home() / home_name
            if src.exists() and src.is_file():
                shutil.copy2(src, self.dotfiles_dir / name)
                backed_up.append(name)
        for f in (Path.home() / ".config").iterdir():
            if f.is_file() and not f.name.startswith("."):
                dest = self.dotfiles_dir / f.name
                if not dest.exists():
                    shutil.copy2(f, dest)
                    backed_up.append(f.name)
        return backed_up

    def backup_flatpak_remotes(self):
        try:
            out = subprocess.check_output(
                ["flatpak", "remotes", "--columns=name,url"],
                text=True, stderr=subprocess.DEVNULL,
            )
            remotes = []
            for line in out.splitlines():
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    remotes.append(f"{parts[0]}\t{parts[1]}")
            path = self.packages_dir / "flatpak-remotes.txt"
            lines = [
                "# Flatpak remotes",
                "# Format: name<tab>url",
                "# Restore with: flatpak remote-add --if-not-exists <name> <url>",
                "",
            ] + remotes
            path.write_text("\n".join(lines) + "\n")
            return len(remotes)
        except Exception:
            return 0

    def rescan_system(self):
        results = []

        flatpaks = sorted(self.installed_flatpaks())
        if flatpaks:
            self.write_flatpaks(flatpaks)
            results.append(f"flatpaks.txt: {len(flatpaks)} apps")

        remote_count = self.backup_flatpak_remotes()
        if remote_count:
            results.append(f"flatpak-remotes.txt: {remote_count} remotes")

        layered = sorted(self.layered_rpms())
        if layered:
            self.write_rpm_ostree(layered)
            results.append(f"rpm-ostree.txt: {len(layered)} packages")

        extensions = sorted(self.installed_gnome_extensions())
        if extensions:
            self.write_gnome_extensions(extensions)
            results.append(f"extensions.txt: {len(extensions)} extensions")

        dconf_file = self.dconf_file()
        with open(dconf_file, "w") as f:
            subprocess.run(["dconf", "dump", "/"], stdout=f, text=True)
        results.append("dconf-settings.ini updated")

        dotfiles = self.backup_dotfiles()
        if dotfiles:
            results.append(f"dotfiles: {len(dotfiles)} files backed up")

        return results

    def _read_list(self, path):
        if not path.exists():
            return []
        items = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                items.append(line)
        return items

    def _write_list(self, path, items, title, format_hint):
        lines = [
            f"# {title}",
            f"# Format: {format_hint}",
            f"# Install with the distroconfig GUI",
            "",
        ]
        for item in items:
            lines.append(item)
        path.write_text("\n".join(lines) + "\n")


# ── UI Widgets ───────────────────────────────────────────────────────────────

class PackageRow(Adw.ActionRow):
    """A row with a switch and status indicator."""

    def __init__(self, app_id, installed=False, enabled=True, **kwargs):
        super().__init__(title=app_id, **kwargs)

        self.app_id = app_id

        self.status_dot = Gtk.Label()
        if installed:
            self.status_dot.set_markup('<span foreground="#2ec27e">●</span>')
            self.status_dot.set_tooltip_text("Installed")
        else:
            self.status_dot.set_markup('<span foreground="#808080">●</span>')
            self.status_dot.set_tooltip_text("Not installed")
        self.add_suffix(self.status_dot)

        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=enabled)
        self.add_suffix(self.switch)

    def get_active(self):
        return self.switch.get_active()


class TaskDialog(Adw.AlertDialog):
    """Shows command output while running."""

    def __init__(self, **kwargs):
        super().__init__(heading="Running...", **kwargs)

        self.spinner = Gtk.Spinner(spinning=True, width_request=32, height_request=32)
        self.text_view = Gtk.TextView(
            editable=False, monospace=True,
            left_margin=12, right_margin=12,
            top_margin=12, bottom_margin=12,
        )
        self.text_view.set_size_request(500, 250)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.append(self.spinner)
        box.append(Gtk.ScrolledWindow(child=self.text_view, vexpand=True))

        self.set_child(box)
        self.add_response("close", "Close")
        self.set_response_appearance("close", Adw.ResponseAppearance.SUGGESTED)
        self.set_response_enabled("close", False)

    def append_text(self, text):
        buf = self.text_view.get_buffer()
        end = buf.get_end_iter()
        buf.insert(end, text)

    def done(self, success, message=""):
        self.spinner.set_spinning(False)
        self.set_response_enabled("close", True)
        if success:
            self.set_heading("Done")
        else:
            self.set_heading("Failed")
        if message:
            self.append_text(f"\n{message}")


# ── Main Window ──────────────────────────────────────────────────────────────

class DistroConfigWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title="distroconfig", default_width=700, default_height=600, **kwargs)

        self.backend = PackageManager()
        self.toast_overlay = Adw.ToastOverlay()

        # Header bar
        header = Adw.HeaderBar()

        update_btn = Gtk.Button(label="Backup System", tooltip_text="Scan system and save all config to repo")
        update_btn.add_css_class("flat")
        update_btn.connect("clicked", self._on_rescan)
        header.pack_end(update_btn)

        # Tab view
        self.tab_view = Adw.TabView()
        self.tab_bar = Adw.TabBar()
        self.tab_bar.set_view(self.tab_view)

        self._build_flatpak_page()
        self._build_rpm_page()
        self._build_extensions_page()
        self._build_gnome_page()

        # Layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(self.tab_bar)
        main_box.append(self.tab_view)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(main_box)

        self.toast_overlay.set_child(toolbar_view)
        self.set_content(self.toast_overlay)

    def _build_flatpak_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_top(12)

        installed = self.backend.installed_flatpaks()
        flatpaks = self.backend.read_flatpaks()

        self.flatpak_rows = {}
        scroll = Gtk.ScrolledWindow(vexpand=True)
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")

        for app in flatpaks:
            row = PackageRow(app, installed=(app in installed))
            listbox.append(row)
            self.flatpak_rows[app] = row

        scroll.set_child(listbox)

        label = Gtk.Label(
            label=f"<b>{len(flatpaks)}</b> flatpak applications",
            use_markup=True, margin_top=8, margin_bottom=8,
        )

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER, margin_bottom=12)
        install_btn = Gtk.Button(label="Install Selected", css_classes=["suggested-action"])
        install_btn.connect("clicked", self._on_flatpak_install)
        uninstall_btn = Gtk.Button(label="Uninstall Selected", css_classes=["destructive-action"])
        uninstall_btn.connect("clicked", self._on_flatpak_uninstall)
        btn_box.append(install_btn)
        btn_box.append(uninstall_btn)

        page.append(label)
        page.append(scroll)
        page.append(btn_box)

        tab = self.tab_view.append(page)
        tab.set_title("Flatpaks")

    def _build_rpm_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_top(12)

        layered = self.backend.layered_rpms()
        packages = self.backend.read_rpm_ostree()

        self.rpm_rows = {}
        scroll = Gtk.ScrolledWindow(vexpand=True)
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")

        for pkg in packages:
            row = PackageRow(pkg, installed=(pkg in layered))
            listbox.append(row)
            self.rpm_rows[pkg] = row

        scroll.set_child(listbox)

        label = Gtk.Label(
            label=f"<b>{len(packages)}</b> rpm-ostree packages",
            use_markup=True, margin_top=8, margin_bottom=8,
        )

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER, margin_bottom=12)
        install_btn = Gtk.Button(label="Install Selected (requires reboot)", css_classes=["suggested-action"])
        install_btn.connect("clicked", self._on_rpm_install)
        btn_box.append(install_btn)

        page.append(label)
        page.append(scroll)
        page.append(btn_box)

        tab = self.tab_view.append(page)
        tab.set_title("Packages")

    def _build_extensions_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_top(12)

        installed = self.backend.installed_gnome_extensions()
        enabled = self.backend.enabled_gnome_extensions()
        extensions = self.backend.read_gnome_extensions()

        self.ext_rows = {}
        scroll = Gtk.ScrolledWindow(vexpand=True)
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")

        for ext in extensions:
            row = PackageRow(ext, installed=(ext in installed), enabled=(ext in enabled))
            listbox.append(row)
            self.ext_rows[ext] = row

        scroll.set_child(listbox)

        label = Gtk.Label(
            label=f"<b>{len(extensions)}</b> GNOME extensions",
            use_markup=True, margin_top=8, margin_bottom=8,
        )

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, halign=Gtk.Align.CENTER, margin_bottom=12)
        apply_btn = Gtk.Button(label="Apply (enable/disable)", css_classes=["suggested-action"])
        apply_btn.connect("clicked", self._on_ext_apply)
        btn_box.append(apply_btn)

        page.append(label)
        page.append(scroll)
        page.append(btn_box)

        tab = self.tab_view.append(page)
        tab.set_title("Extensions")

    def _build_gnome_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_margin_top(12)
        page.set_margin_start(12)
        page.set_margin_end(12)

        # dconf settings
        dconf_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dconf_label = Gtk.Label(
            label="<b>GNOME Settings (dconf)</b>",
            use_markup=True, halign=Gtk.Align.START,
        )
        dconf_desc = Gtk.Label(
            label="Applies: dark mode, Danish keyboard, night light, dash-to-dock config, and more.",
            halign=Gtk.Align.START, wrap=True,
        )
        dconf_btn = Gtk.Button(label="Apply dconf Settings", css_classes=["suggested-action"], halign=Gtk.Align.START)
        dconf_btn.connect("clicked", self._on_dconf_apply)
        dconf_group.append(dconf_label)
        dconf_group.append(dconf_desc)
        dconf_group.append(dconf_btn)

        sep = Gtk.Separator(margin_top=6, margin_bottom=6)

        # Dotfiles
        dotfiles_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dotfiles_label = Gtk.Label(
            label="<b>Dotfiles</b>",
            use_markup=True, halign=Gtk.Align.START,
        )

        dotfiles = list(self.backend.dotfiles_dir.iterdir()) if self.backend.dotfiles_dir.exists() else []
        dotfiles = [f.name for f in dotfiles if f.is_file() and not f.name.startswith(".")]
        dotfiles_desc = Gtk.Label(
            label=f"Deploys: {', '.join(dotfiles) if dotfiles else 'none found'}",
            halign=Gtk.Align.START, wrap=True,
        )
        dotfiles_btn = Gtk.Button(label="Deploy Dotfiles", css_classes=["suggested-action"], halign=Gtk.Align.START)
        dotfiles_btn.connect("clicked", self._on_dotfiles_deploy)
        backup_dotfiles_btn = Gtk.Button(label="Backup Dotfiles", css_classes=["suggested-action"], halign=Gtk.Align.START)
        backup_dotfiles_btn.connect("clicked", self._on_dotfiles_backup)
        dotfiles_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        dotfiles_btn_box.append(dotfiles_btn)
        dotfiles_btn_box.append(backup_dotfiles_btn)
        dotfiles_group.append(dotfiles_label)
        dotfiles_group.append(dotfiles_desc)
        dotfiles_group.append(dotfiles_btn_box)

        page.append(dconf_group)
        page.append(sep)
        page.append(dotfiles_group)

        tab = self.tab_view.append(page)
        tab.set_title("GNOME & Dots")

    # ── Actions ──────────────────────────────────────────────────────────

    def _on_flatpak_install(self, _btn):
        to_install = [app for app, row in self.flatpak_rows.items() if row.get_active()]
        if not to_install:
            self._toast("No packages selected")
            return

        dialog = TaskDialog()
        dialog.present(self)

        def run():
            for app in to_install:
                GLib.idle_add(dialog.append_text, f"Installing {app}...\n")
                result = self.backend.install_flatpak(app)
                if result.returncode != 0:
                    GLib.idle_add(dialog.append_text, f"  Failed: {result.stderr.strip()}\n")
                else:
                    GLib.idle_add(dialog.append_text, f"  OK\n")
            GLib.idle_add(dialog.done, True)

        threading.Thread(target=run, daemon=True).start()

    def _on_flatpak_uninstall(self, _btn):
        to_uninstall = [app for app, row in self.flatpak_rows.items() if row.get_active()]
        if not to_uninstall:
            self._toast("No packages selected")
            return

        dialog = TaskDialog()
        dialog.present(self)

        def run():
            for app in to_uninstall:
                GLib.idle_add(dialog.append_text, f"Uninstalling {app}...\n")
                result = self.backend.uninstall_flatpak(app)
                if result.returncode != 0:
                    GLib.idle_add(dialog.append_text, f"  Failed: {result.stderr.strip()}\n")
                else:
                    GLib.idle_add(dialog.append_text, f"  OK\n")
            GLib.idle_add(dialog.done, True)

        threading.Thread(target=run, daemon=True).start()

    def _on_rpm_install(self, _btn):
        to_install = [pkg for pkg, row in self.rpm_rows.items() if row.get_active()]
        if not to_install:
            self._toast("No packages selected")
            return

        dialog = TaskDialog()
        dialog.present(self)

        def run():
            GLib.idle_add(dialog.append_text, f"Running: sudo rpm-ostree install {' '.join(to_install)}\n\n")
            result = self.backend.install_rpm_ostree(to_install)
            GLib.idle_add(dialog.append_text, result.stdout)
            if result.stderr:
                GLib.idle_add(dialog.append_text, result.stderr)
            GLib.idle_add(dialog.done, result.returncode == 0, "\nReboot required to apply changes.")

        threading.Thread(target=run, daemon=True).start()

    def _on_ext_apply(self, _btn):
        current = set(self.backend.enabled_gnome_extensions())
        new_enabled = {ext for ext, row in self.ext_rows.items() if row.get_active()}
        new_disabled = {ext for ext, row in self.ext_rows.items() if not row.get_active()}

        for ext in new_enabled:
            subprocess.run(["gnome-extensions", "enable", ext], capture_output=True)
        for ext in new_disabled:
            subprocess.run(["gnome-extensions", "disable", ext], capture_output=True)

        self._toast("Extension settings applied")

    def _on_dconf_apply(self, _btn):
        dialog = TaskDialog()
        dialog.present(self)

        def run():
            GLib.idle_add(dialog.append_text, "Applying dconf settings...\n")
            ok, msg = self.backend.apply_dconf()
            if msg:
                GLib.idle_add(dialog.append_text, msg)
            GLib.idle_add(dialog.done, ok)

        threading.Thread(target=run, daemon=True).start()

    def _on_dotfiles_deploy(self, _btn):
        deployed = self.backend.deploy_dotfiles()
        self._toast(f"Deployed {len(deployed)} dotfiles")

    def _on_dotfiles_backup(self, _btn):
        backed = self.backend.backup_dotfiles()
        self._toast(f"Backed up {len(backed)} dotfiles")

    def _on_rescan(self, _btn):
        dialog = TaskDialog()
        dialog.present(self)

        def run():
            GLib.idle_add(dialog.append_text, "Backing up system configuration...\n\n")
            results = self.backend.rescan_system()
            for r in results:
                GLib.idle_add(dialog.append_text, f"  {r}\n")
            GLib.idle_add(dialog.append_text, "\nAll config saved to repo. Review with git diff.")
            GLib.idle_add(dialog.done, True, "\nYou may need to restart the app to see changes.")

        threading.Thread(target=run, daemon=True).start()

    def _toast(self, msg):
        self.toast_overlay.add_toast(Adw.Toast.new(msg))


# ── Application ──────────────────────────────────────────────────────────────

class DistroConfigApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("activate", self._on_activate)

    def _on_activate(self, app):
        win = DistroConfigWindow(application=app)
        win.present()


def main():
    app = DistroConfigApp()
    app.run()


if __name__ == "__main__":
    main()
