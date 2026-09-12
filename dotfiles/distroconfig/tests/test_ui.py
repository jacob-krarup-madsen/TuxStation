"""Tests for the distroconfig GTK UI layer.

Mocks GTK/Adw so tests run headlessly without a display server.
"""

import importlib
import importlib.util
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class _Namespace:
    """Simple namespace for enum-like constants."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeWidget:
    """Base fake GTK widget — stores kwargs, noop methods."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getattr__(self, name):
        return MagicMock()


class _FakeLabel(_FakeWidget):
    """Fake Gtk.Label that stores markup for testing."""
    def __init__(self, **kwargs):
        self._markup = ""
        self._tooltip = ""
        super().__init__(**kwargs)

    def set_markup(self, text):
        self._markup = text

    def set_tooltip_text(self, text):
        self._tooltip = text


class _FakeSwitch(_FakeWidget):
    """Fake Gtk.Switch with get_active()."""
    def get_active(self):
        return self.active


def _make_base(name):
    """Create a real class usable as an Adw widget base class."""
    def _init(self, **kwargs):
        pass

    def _get(self, attr):
        return MagicMock()

    return type(name, (), {"__init__": _init, "__getattr__": _get})


def _import_app_with_mocked_gtk():
    """Import app.py with fully-mocked GTK/Adw."""
    saved = {k: sys.modules.pop(k, None) for k in ("gi", "gi.repository")}

    mock_gi = MagicMock()
    mock_gr = types.ModuleType("gi.repository")

    # ── Gtk: proper module with widget classes ────────────────────────────
    mock_gr.Gtk = types.ModuleType("Gtk")
    mock_gr.Gtk.Box = _FakeWidget
    mock_gr.Gtk.Label = _FakeLabel
    mock_gr.Gtk.Switch = _FakeSwitch
    mock_gr.Gtk.ListBox = _FakeWidget
    mock_gr.Gtk.ScrolledWindow = _FakeWidget
    mock_gr.Gtk.Button = _FakeWidget
    mock_gr.Gtk.Separator = _FakeWidget
    mock_gr.Gtk.Spinner = _FakeWidget
    mock_gr.Gtk.TextView = _FakeWidget
    mock_gr.Gtk.Align = _Namespace(CENTER="center", START="start")
    mock_gr.Gtk.SelectionMode = _Namespace(NONE="none")
    mock_gr.Gtk.Orientation = _Namespace(VERTICAL="vertical", HORIZONTAL="horizontal")

    # ── Adw: real base classes so app classes can subclass them ───────────
    mock_gr.Adw = types.ModuleType("Adw")
    mock_gr.Adw.ActionRow = _make_base("ActionRow")
    mock_gr.Adw.AlertDialog = _make_base("AlertDialog")
    mock_gr.Adw.ApplicationWindow = _make_base("ApplicationWindow")
    mock_gr.Adw.Application = _make_base("Application")
    mock_gr.Adw.ToastOverlay = _make_base("ToastOverlay")
    mock_gr.Adw.HeaderBar = _make_base("HeaderBar")
    mock_gr.Adw.TabView = _make_base("TabView")
    mock_gr.Adw.TabBar = _make_base("TabBar")
    mock_gr.Adw.ToolbarView = _make_base("ToolbarView")
    mock_gr.Adw.Toast = MagicMock()
    mock_gr.Adw.ResponseAppearance = MagicMock()

    # ── GLib / Gio ───────────────────────────────────────────────────────
    mock_gr.GLib = MagicMock()
    mock_gr.GLib.idle_add.side_effect = lambda fn, *a: fn(*a)
    mock_gr.Gio = MagicMock()

    sys.modules["gi"] = mock_gi
    sys.modules["gi.repository"] = mock_gr

    if "app" in sys.modules:
        del sys.modules["app"]

    spec = importlib.util.spec_from_file_location("app", Path(__file__).parent.parent / "app.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app"] = mod
    spec.loader.exec_module(mod)

    # Restore real gi
    for k, v in saved.items():
        sys.modules.pop(k, None)
        if v is not None:
            sys.modules[k] = v

    return mod


app = _import_app_with_mocked_gtk()
PackageManager = app.PackageManager


def _row(active=False):
    m = MagicMock()
    m.get_active.return_value = active
    return m


def _win(tmp, **kwargs):
    """Build a DistroConfigWindow with real backend + mocked UI."""
    w = app.DistroConfigWindow.__new__(app.DistroConfigWindow)
    w.backend = PackageManager()
    w.backend.packages_dir = Path(tmp) / "packages"
    w.backend.packages_dir.mkdir(exist_ok=True)
    w.backend.gnome_dir = Path(tmp) / "gnome"
    w.backend.gnome_dir.mkdir(exist_ok=True)
    w.backend.dotfiles_dir = Path(tmp) / "dotfiles"
    w.backend.dotfiles_dir.mkdir(exist_ok=True)
    w.toast_overlay = MagicMock()
    w.flatpak_rows = kwargs.get("flatpak_rows", {})
    w.rpm_rows = kwargs.get("rpm_rows", {})
    w.ext_rows = kwargs.get("ext_rows", {})
    return w


def _run_in_thread(method, win, btn=None, dialog_factory=None):
    """Call a _on_* method, capture the thread target, and run it synchronously.

    Returns the mock dialog used inside the thread.
    """
    btn = btn or MagicMock()
    dialog = dialog_factory() if dialog_factory else MagicMock()
    target_ref = {}

    original_thread_init = app.threading.Thread.__init__

    def capture_init(self, target=None, **kw):
        target_ref["fn"] = target
        original_thread_init(self, target=target, **kw)

    original_thread_start = app.threading.Thread.start

    def noop_start(self):
        pass

    with patch.object(app.threading.Thread, "__init__", capture_init):
        with patch.object(app.threading.Thread, "start", noop_start):
            with patch("app.TaskDialog", return_value=dialog):
                method(win, btn)

    original_idle = app.GLib.idle_add

    def immediate_idle(fn, *args):
        fn(*args)

    app.GLib.idle_add = immediate_idle
    try:
        target_ref["fn"]()
    finally:
        app.GLib.idle_add = original_idle

    return dialog


# ═══════════════════════════════════════════════════════════════════════════════
# PackageRow
# ═══════════════════════════════════════════════════════════════════════════════

class TestPackageRow(unittest.TestCase):
    def test_app_id(self):
        r = app.PackageRow("com.test.App")
        self.assertEqual(r.app_id, "com.test.App")

    def test_get_active_delegates(self):
        r = app.PackageRow.__new__(app.PackageRow)
        r.switch = MagicMock()
        r.switch.get_active.return_value = True
        self.assertTrue(r.get_active())
        r.switch.get_active.return_value = False
        self.assertFalse(r.get_active())

    def test_installed_green(self):
        r = app.PackageRow("x", installed=True)
        self.assertIn("#2ec27e", r.status_dot._markup)

    def test_not_installed_gray(self):
        r = app.PackageRow("x", installed=False)
        self.assertIn("#808080", r.status_dot._markup)

    def test_switch_active(self):
        r = app.PackageRow("x", enabled=True)
        self.assertTrue(r.switch.active)

    def test_switch_inactive(self):
        r = app.PackageRow("x", enabled=False)
        self.assertFalse(r.switch.active)


# ═══════════════════════════════════════════════════════════════════════════════
# TaskDialog
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaskDialog(unittest.TestCase):
    def _make(self):
        d = app.TaskDialog.__new__(app.TaskDialog)
        d.spinner = MagicMock()
        d.text_view = MagicMock()
        d._heading = None
        d._responses = {}
        return d

    def _patch_done_methods(self, d):
        """Make done() track calls for assertion."""
        calls = {"heading": [], "spinning": [], "response": [], "text": []}

        def set_heading(h):
            calls["heading"].append(h)
            d._heading = h

        def set_spinning(v):
            calls["spinning"].append(v)

        def set_response_enabled(r, v):
            calls["response"].append((r, v))

        def append_text(t):
            calls["text"].append(t)

        d.set_heading = set_heading
        d.spinner.set_spinning = set_spinning
        d.set_response_enabled = set_response_enabled
        d.append_text = append_text
        return calls

    def test_done_success(self):
        d = self._make()
        calls = self._patch_done_methods(d)
        d.done(True)
        self.assertEqual(calls["heading"], ["Done"])
        self.assertEqual(calls["spinning"], [False])

    def test_done_failure(self):
        d = self._make()
        calls = self._patch_done_methods(d)
        d.done(False)
        self.assertEqual(calls["heading"], ["Failed"])

    def test_done_with_message(self):
        d = self._make()
        calls = self._patch_done_methods(d)
        d.done(True, "All good")
        self.assertEqual(calls["heading"], ["Done"])
        self.assertIn("\nAll good", calls["text"])

    def test_done_without_message(self):
        d = self._make()
        calls = self._patch_done_methods(d)
        d.done(True, "")
        self.assertEqual(calls["heading"], ["Done"])
        self.assertEqual(calls["text"], [])


# ═══════════════════════════════════════════════════════════════════════════════
# _on_flatpak_install
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnFlatpakInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_no_selection(self):
        w = _win(self.tmp)
        app.DistroConfigWindow._on_flatpak_install(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()

    def test_success(self):
        w = _win(self.tmp, flatpak_rows={"com.a": _row(True)})
        w.backend.install_flatpak = MagicMock(return_value=MagicMock(returncode=0))
        d = _run_in_thread(app.DistroConfigWindow._on_flatpak_install, w)
        d.append_text.assert_any_call("Installing com.a...\n")
        d.append_text.assert_any_call("  OK\n")

    def test_failure(self):
        w = _win(self.tmp, flatpak_rows={"com.a": _row(True)})
        w.backend.install_flatpak = MagicMock(
            return_value=MagicMock(returncode=1, stderr="err")
        )
        d = _run_in_thread(app.DistroConfigWindow._on_flatpak_install, w)
        d.append_text.assert_any_call("  Failed: err\n")

    def test_multiple_apps(self):
        w = _win(self.tmp, flatpak_rows={
            "com.a": _row(True), "com.b": _row(True), "com.c": _row(False),
        })
        w.backend.install_flatpak = MagicMock(return_value=MagicMock(returncode=0))
        _run_in_thread(app.DistroConfigWindow._on_flatpak_install, w)
        self.assertEqual(w.backend.install_flatpak.call_count, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# _on_flatpak_uninstall
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnFlatpakUninstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_no_selection(self):
        w = _win(self.tmp)
        app.DistroConfigWindow._on_flatpak_uninstall(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()

    def test_success(self):
        w = _win(self.tmp, flatpak_rows={"com.a": _row(True)})
        w.backend.uninstall_flatpak = MagicMock(return_value=MagicMock(returncode=0))
        d = _run_in_thread(app.DistroConfigWindow._on_flatpak_uninstall, w)
        d.append_text.assert_any_call("Uninstalling com.a...\n")
        d.append_text.assert_any_call("  OK\n")

    def test_failure(self):
        w = _win(self.tmp, flatpak_rows={"com.a": _row(True)})
        w.backend.uninstall_flatpak = MagicMock(
            return_value=MagicMock(returncode=1, stderr="bad")
        )
        d = _run_in_thread(app.DistroConfigWindow._on_flatpak_uninstall, w)
        d.append_text.assert_any_call("  Failed: bad\n")


# ═══════════════════════════════════════════════════════════════════════════════
# _on_rpm_install
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnRpmInstall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_no_selection(self):
        w = _win(self.tmp)
        app.DistroConfigWindow._on_rpm_install(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()

    def test_success(self):
        w = _win(self.tmp, rpm_rows={"pkg": _row(True)})
        w.backend.install_rpm_ostree = MagicMock(
            return_value=MagicMock(returncode=0, stdout="ok", stderr="")
        )
        d = _run_in_thread(app.DistroConfigWindow._on_rpm_install, w)
        d.done.assert_called_with(True, "\nReboot required to apply changes.")

    def test_failure_with_stderr(self):
        w = _win(self.tmp, rpm_rows={"pkg": _row(True)})
        w.backend.install_rpm_ostree = MagicMock(
            return_value=MagicMock(returncode=1, stdout="", stderr="err msg")
        )
        d = _run_in_thread(app.DistroConfigWindow._on_rpm_install, w)
        d.append_text.assert_any_call("err msg")
        d.done.assert_called_with(False, "\nReboot required to apply changes.")

    def test_failure_no_stderr(self):
        w = _win(self.tmp, rpm_rows={"pkg": _row(True)})
        w.backend.install_rpm_ostree = MagicMock(
            return_value=MagicMock(returncode=1, stdout="", stderr="")
        )
        d = _run_in_thread(app.DistroConfigWindow._on_rpm_install, w)
        d.done.assert_called_with(False, "\nReboot required to apply changes.")


# ═══════════════════════════════════════════════════════════════════════════════
# _on_ext_apply
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnExtApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.subprocess.run")
    @patch.object(app.PackageManager, "enabled_gnome_extensions", return_value=set())
    def test_enable_and_disable(self, mock_en, mock_run):
        w = _win(self.tmp, ext_rows={
            "ext-a@x.com": _row(True), "ext-b@y.com": _row(False),
        })
        app.DistroConfigWindow._on_ext_apply(w, MagicMock())
        calls = mock_run.call_args_list
        self.assertTrue(any("enable" in str(c) for c in calls))
        self.assertTrue(any("disable" in str(c) for c in calls))

    @patch("app.subprocess.run")
    @patch.object(app.PackageManager, "enabled_gnome_extensions", return_value=set())
    def test_toast(self, mock_en, mock_run):
        w = _win(self.tmp)
        app.DistroConfigWindow._on_ext_apply(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()

    @patch("app.subprocess.run")
    @patch.object(app.PackageManager, "enabled_gnome_extensions", return_value={"ext-a"})
    def test_empty_rows(self, mock_en, mock_run):
        w = _win(self.tmp, ext_rows={})
        app.DistroConfigWindow._on_ext_apply(w, MagicMock())
        mock_run.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# _on_dconf_apply
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnDconfApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_success_no_msg(self):
        w = _win(self.tmp)
        w.backend.apply_dconf = MagicMock(return_value=(True, None))
        d = _run_in_thread(app.DistroConfigWindow._on_dconf_apply, w)
        d.done.assert_called_with(True)

    def test_success_with_msg(self):
        w = _win(self.tmp)
        w.backend.apply_dconf = MagicMock(return_value=(True, "warn"))
        d = _run_in_thread(app.DistroConfigWindow._on_dconf_apply, w)
        d.append_text.assert_any_call("warn")

    def test_failure(self):
        w = _win(self.tmp)
        w.backend.apply_dconf = MagicMock(return_value=(False, "error"))
        d = _run_in_thread(app.DistroConfigWindow._on_dconf_apply, w)
        d.done.assert_called_with(False)


# ═══════════════════════════════════════════════════════════════════════════════
# _on_dotfiles_deploy
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnDotfilesDeploy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.Path.home")
    def test_deploy(self, mock_home):
        mock_home.return_value = Path(self.tmp) / "home"
        (Path(self.tmp) / "home").mkdir()
        w = _win(self.tmp)
        (w.backend.dotfiles_dir / "gitconfig").write_text("[u]\n")
        app.DistroConfigWindow._on_dotfiles_deploy(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()

    @patch("app.Path.home")
    def test_empty(self, mock_home):
        mock_home.return_value = Path(self.tmp) / "home"
        (Path(self.tmp) / "home").mkdir()
        w = _win(self.tmp)
        app.DistroConfigWindow._on_dotfiles_deploy(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()


class TestOnDotfilesBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_shows_toast(self):
        w = _win(self.tmp)
        w.backend.backup_dotfiles = MagicMock(return_value=["gitconfig", "bashrc"])
        app.DistroConfigWindow._on_dotfiles_backup(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()

    def test_empty_backup(self):
        w = _win(self.tmp)
        w.backend.backup_dotfiles = MagicMock(return_value=[])
        app.DistroConfigWindow._on_dotfiles_backup(w, MagicMock())
        w.toast_overlay.add_toast.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# _on_rescan
# ═══════════════════════════════════════════════════════════════════════════════

class TestOnRescan(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_displays_results(self):
        w = _win(self.tmp)
        w.backend.rescan_system = MagicMock(
            return_value=["flatpaks.txt: 3 apps", "dconf-settings.ini updated"]
        )
        d = _run_in_thread(app.DistroConfigWindow._on_rescan, w)
        d.append_text.assert_any_call("Backing up system configuration...\n\n")
        d.append_text.assert_any_call("  flatpaks.txt: 3 apps\n")
        d.append_text.assert_any_call("  dconf-settings.ini updated\n")


# ═══════════════════════════════════════════════════════════════════════════════
# _toast
# ═══════════════════════════════════════════════════════════════════════════════

class TestToast(unittest.TestCase):
    def test_adds_toast(self):
        w = _win(tempfile.mkdtemp())
        app.DistroConfigWindow._toast(w, "msg")
        w.toast_overlay.add_toast.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# DistroConfigApp
# ═══════════════════════════════════════════════════════════════════════════════

class TestTaskDialogInit(unittest.TestCase):
    def test_init_creates_widgets(self):
        d = app.TaskDialog()
        self.assertTrue(hasattr(d, 'spinner'))
        self.assertTrue(hasattr(d, 'text_view'))

    def test_append_text_real(self):
        d = app.TaskDialog()
        d.append_text("hello world")
        d.append_text(" second")


class TestDistroConfigApp(unittest.TestCase):
    def test_on_activate(self):
        a = app.DistroConfigApp.__new__(app.DistroConfigApp)
        app.DistroConfigApp._on_activate(a, MagicMock())

    def test_init(self):
        a = app.DistroConfigApp()
        self.assertIsNotNone(a)


# ═══════════════════════════════════════════════════════════════════════════════
# main()
# ═══════════════════════════════════════════════════════════════════════════════

class TestMain(unittest.TestCase):
    @patch("app.DistroConfigApp")
    def test_main(self, MockApp):
        inst = MagicMock()
        MockApp.return_value = inst
        app.main()
        MockApp.assert_called_once()
        inst.run.assert_called_once()

    def test_main_guard(self):
        saved = {k: sys.modules.pop(k, None) for k in ("gi", "gi.repository")}
        mock_gi = MagicMock()
        mock_gr = types.ModuleType("gi.repository")
        mock_gr.Gtk = types.ModuleType("Gtk")
        for n, c in (("Box", _FakeWidget), ("Label", _FakeLabel), ("Switch", _FakeSwitch),
                      ("ListBox", _FakeWidget), ("ScrolledWindow", _FakeWidget),
                      ("Button", _FakeWidget), ("Separator", _FakeWidget),
                      ("Spinner", _FakeWidget), ("TextView", _FakeWidget)):
            setattr(mock_gr.Gtk, n, c)
        mock_gr.Gtk.Align = _Namespace(CENTER="center", START="start")
        mock_gr.Gtk.SelectionMode = _Namespace(NONE="none")
        mock_gr.Gtk.Orientation = _Namespace(VERTICAL="vertical", HORIZONTAL="horizontal")
        mock_gr.Adw = types.ModuleType("Adw")
        for n in ("ActionRow", "AlertDialog", "ApplicationWindow", "Application",
                   "ToastOverlay", "HeaderBar", "TabView", "TabBar", "ToolbarView"):
            setattr(mock_gr.Adw, n, _make_base(n))
        mock_gr.Adw.Toast = MagicMock()
        mock_gr.Adw.ResponseAppearance = MagicMock()
        mock_gr.GLib = MagicMock()
        mock_gr.GLib.idle_add.side_effect = lambda fn, *a: fn(*a)
        mock_gr.Gio = MagicMock()
        sys.modules["gi"] = mock_gi
        sys.modules["gi.repository"] = mock_gr
        try:
            exec(compile(Path(app.__file__).read_text(), app.__file__, "exec"),
                 {"__name__": "__main__", "__file__": app.__file__})
        finally:
            sys.modules.pop("gi", None)
            sys.modules.pop("gi.repository", None)
            for k, v in saved.items():
                if v is not None:
                    sys.modules[k] = v


if __name__ == "__main__":
    unittest.main()
