"""Tests for the distroconfig PackageManager backend."""

import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from app import PackageManager, APP_ID, SCRIPT_DIR


class TestReadList(unittest.TestCase):
    """Tests for _read_list."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _write(self, name, content):
        path = self.pm.packages_dir / name
        path.write_text(textwrap.dedent(content))
        return path

    def test_reads_items(self):
        self._write("test.txt", """\
            # comment
            item-one
            item-two
            item-three
        """)
        result = self.pm._read_list(self.pm.packages_dir / "test.txt")
        self.assertEqual(result, ["item-one", "item-two", "item-three"])

    def test_skips_comments(self):
        self._write("test.txt", """\
            # This is a comment
            # Another comment
            actual-item
        """)
        result = self.pm._read_list(self.pm.packages_dir / "test.txt")
        self.assertEqual(result, ["actual-item"])

    def test_skips_blank_lines(self):
        self._write("test.txt", """\

            item-a


            item-b

        """)
        result = self.pm._read_list(self.pm.packages_dir / "test.txt")
        self.assertEqual(result, ["item-a", "item-b"])

    def test_returns_empty_for_missing_file(self):
        result = self.pm._read_list(Path("/nonexistent/file.txt"))
        self.assertEqual(result, [])

    def test_returns_empty_for_empty_file(self):
        self._write("empty.txt", "")
        result = self.pm._read_list(self.pm.packages_dir / "empty.txt")
        self.assertEqual(result, [])

    def test_strips_whitespace(self):
        self._write("test.txt", "  item-one  \n\titem-two\t\n")
        result = self.pm._read_list(self.pm.packages_dir / "test.txt")
        self.assertEqual(result, ["item-one", "item-two"])

    def test_comment_with_inline_text_not_skipped(self):
        """Lines starting with # are comments, even if they look like items."""
        self._write("test.txt", "#just-a-comment\nreal-item\n")
        result = self.pm._read_list(self.pm.packages_dir / "test.txt")
        self.assertEqual(result, ["real-item"])

    def test_real_flatpaks_file(self):
        content = (Path(__file__).parent.parent / "packages" / "flatpaks.txt").read_text()
        path = self.pm.packages_dir / "flatpaks.txt"
        path.write_text(content)
        result = self.pm._read_list(path)
        self.assertGreater(len(result), 0)
        self.assertIn("com.discordapp.Discord", result)
        self.assertIn("com.valvesoftware.Steam", result)

    def test_real_rpm_ostree_file(self):
        content = (Path(__file__).parent.parent / "packages" / "rpm-ostree.txt").read_text()
        path = self.pm.packages_dir / "rpm-ostree.txt"
        path.write_text(content)
        result = self.pm._read_list(path)
        self.assertGreater(len(result), 0)
        self.assertIn("brave-origin", result)
        self.assertIn("tailscale", result)


class TestWriteList(unittest.TestCase):
    """Tests for _write_list."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_writes_with_header(self):
        path = self.pm.packages_dir / "test.txt"
        self.pm._write_list(path, ["item-a", "item-b"], "Test Title", "format-hint")
        content = path.read_text()
        self.assertTrue(content.startswith("# Test Title"))
        self.assertIn("# Format: format-hint", content)
        self.assertIn("item-a", content)
        self.assertIn("item-b", content)

    def test_roundtrip(self):
        path = self.pm.packages_dir / "test.txt"
        items = ["app.one", "app.two", "app.three"]
        self.pm._write_list(path, items, "Title", "hint")
        result = self.pm._read_list(path)
        self.assertEqual(result, items)

    def test_empty_list(self):
        path = self.pm.packages_dir / "test.txt"
        self.pm._write_list(path, [], "Title", "hint")
        result = self.pm._read_list(path)
        self.assertEqual(result, [])

    def test_newline_terminated(self):
        path = self.pm.packages_dir / "test.txt"
        self.pm._write_list(path, ["a"], "Title", "hint")
        content = path.read_text()
        self.assertTrue(content.endswith("\n"))


class TestWriteFlatpaks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_creates_valid_flatpak_list(self):
        apps = ["com.discordapp.Discord", "com.valvesoftware.Steam"]
        self.pm.write_flatpaks(apps)
        result = self.pm.read_flatpaks()
        self.assertEqual(result, apps)


class TestWriteRpmOstree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_creates_valid_rpm_list(self):
        packages = ["brave-origin", "tailscale"]
        self.pm.write_rpm_ostree(packages)
        result = self.pm.read_rpm_ostree()
        self.assertEqual(result, packages)


class TestWriteGnomeExtensions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_creates_valid_extension_list(self):
        extensions = ["dash-to-dock@micxgx.gmail.com", "gsconnect@andyholmes.github.io"]
        self.pm.write_gnome_extensions(extensions)
        result = self.pm.read_gnome_extensions()
        self.assertEqual(result, extensions)


class TestLayeredRpms(unittest.TestCase):
    """Tests for rpm-ostree status parsing."""

    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_parses_single_line_layered(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
                      LayeredPackages: brave-origin tailscale
            """)
        result = self.pm.layered_rpms()
        self.assertEqual(result, {"brave-origin", "tailscale"})

    @patch("app.subprocess.check_output")
    def test_parses_multi_line_layered(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
                      LayeredPackages: brave-origin input-remapper
                                        libnsl tailscale xterm
            """)
        result = self.pm.layered_rpms()
        self.assertEqual(result, {"brave-origin", "input-remapper", "libnsl", "tailscale", "xterm"})

    @patch("app.subprocess.check_output")
    def test_parses_with_local_packages(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
                      LayeredPackages: brave-origin input-remapper
                        LocalPackages: opencode-1.18.5-1.x86_64
            """)
        result = self.pm.layered_rpms()
        self.assertIn("brave-origin", result)
        self.assertIn("input-remapper", result)
        # LocalPackages line doesn't start with space/tab after Layered section ends
        self.assertNotIn("opencode-1.18.5-1.x86_64", result)

    @patch("app.subprocess.check_output")
    def test_empty_layered(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
            """)
        result = self.pm.layered_rpms()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_returns_empty_on_error(self, mock_check):
        mock_check.side_effect = FileNotFoundError("command not found")
        result = self.pm.layered_rpms()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_parses_real_world_output(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
                          Version: 44.20260726.0 (2026-07-26T00:30:31Z)
                       BaseCommit: e0f49b4599d4ca8d3b207ab391ac7a2418a20fc25b49008c681fbf8da3a886a6
                     GPGSignature: Valid signature by 36F612DCF27F7D1A48A835E4DBFCF71C6D9F90A6
              RemovedBasePackages: firefox firefox-langpacks 153.0-3.fc44
                                   gnome-color-manager 3.36.2-3.fc44 gnome-disk-utility 46.1-4.fc44
              LayeredPackages: brave-origin input-remapper libnsl tailscale xterm
                LocalPackages: opencode-1.18.5-1.x86_64
            """)
        result = self.pm.layered_rpms()
        self.assertEqual(result, {"brave-origin", "input-remapper", "libnsl", "tailscale", "xterm"})


class TestEnabledGnomeExtensions(unittest.TestCase):
    """Tests for gsettings output parsing."""

    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_empty_extensions(self, mock_check):
        mock_check.return_value = "@as []\n"
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_single_extension(self, mock_check):
        mock_check.return_value = "['dash-to-dock@micxgx.gmail.com']\n"
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, {"dash-to-dock@micxgx.gmail.com"})

    @patch("app.subprocess.check_output")
    def test_multiple_extensions(self, mock_check):
        mock_check.return_value = (
            "['ext-one@foo.com', 'ext-two@bar.org', 'ext-three@baz.net']\n"
        )
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, {"ext-one@foo.com", "ext-two@bar.org", "ext-three@baz.net"})

    @patch("app.subprocess.check_output")
    def test_returns_empty_on_error(self, mock_check):
        mock_check.side_effect = FileNotFoundError()
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, set())


class TestInstalledFlatpaks(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_returns_set(self, mock_check):
        mock_check.return_value = "com.discordapp.Discord\ncom.valvesoftware.Steam\n"
        result = self.pm.installed_flatpaks()
        self.assertEqual(result, {"com.discordapp.Discord", "com.valvesoftware.Steam"})

    @patch("app.subprocess.check_output")
    def test_returns_empty_on_error(self, mock_check):
        mock_check.side_effect = FileNotFoundError()
        result = self.pm.installed_flatpaks()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_strips_empty_lines(self, mock_check):
        mock_check.return_value = "app.one\n\napp.two\n\n"
        result = self.pm.installed_flatpaks()
        self.assertEqual(result, {"app.one", "app.two"})


class TestInstalledGnomeExtensions(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_returns_set(self, mock_check):
        mock_check.return_value = "dash-to-dock@micxgx.gmail.com\ngsconnect@andyholmes.github.io\n"
        result = self.pm.installed_gnome_extensions()
        self.assertEqual(result, {"dash-to-dock@micxgx.gmail.com", "gsconnect@andyholmes.github.io"})

    @patch("app.subprocess.check_output")
    def test_returns_empty_on_error(self, mock_check):
        mock_check.side_effect = FileNotFoundError()
        result = self.pm.installed_gnome_extensions()
        self.assertEqual(result, set())


class TestInstallFlatpak(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.run")
    def test_calls_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.install_flatpak("com.discordapp.Discord")
        mock_run.assert_called_once_with(
            ["flatpak", "install", "-y", "flathub", "com.discordapp.Discord"],
            capture_output=True, text=True,
        )


class TestUninstallFlatpak(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.run")
    def test_calls_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.uninstall_flatpak("com.discordapp.Discord")
        mock_run.assert_called_once_with(
            ["flatpak", "uninstall", "-y", "com.discordapp.Discord"],
            capture_output=True, text=True,
        )


class TestInstallRpmOstree(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.run")
    def test_calls_correct_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.install_rpm_ostree(["brave-origin", "tailscale"])
        mock_run.assert_called_once_with(
            ["sudo", "rpm-ostree", "install", "brave-origin", "tailscale"],
            capture_output=True, text=True,
        )


class TestApplyDconf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.subprocess.run")
    def test_returns_false_when_file_missing(self, mock_run):
        ok, msg = self.pm.apply_dconf()
        self.assertFalse(ok)
        self.assertIn("not found", msg)
        mock_run.assert_not_called()

    @patch("app.subprocess.run")
    def test_loads_dconf_file(self, mock_run):
        dconf_file = self.pm.gnome_dir / "dconf-settings.ini"
        dconf_file.write_text("[org/gnome/desktop/interface]\ncolor-scheme='prefer-dark'\n")
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, msg = self.pm.apply_dconf()
        self.assertTrue(ok)
        mock_run.assert_called_once()
        args = mock_run.call_args
        self.assertEqual(args[0][0], ["dconf", "load", "/"])
        self.assertEqual(args[1]["input"], dconf_file.read_text())

    @patch("app.subprocess.run")
    def test_returns_false_on_dconf_error(self, mock_run):
        dconf_file = self.pm.gnome_dir / "dconf-settings.ini"
        dconf_file.write_text("[test]\nkey='value'\n")
        mock_run.return_value = MagicMock(returncode=1, stderr="error: something went wrong")
        ok, msg = self.pm.apply_dconf()
        self.assertFalse(ok)
        self.assertEqual(msg, "error: something went wrong")


class TestDconfFile(unittest.TestCase):
    def test_returns_path(self):
        pm = PackageManager()
        result = pm.dconf_file()
        self.assertIsInstance(result, Path)
        self.assertEqual(result.name, "dconf-settings.ini")
        self.assertEqual(result.parent.name, "gnome")


class TestDeployDotfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.dotfiles_dir = Path(self.tmp) / "dotfiles"
        self.pm.dotfiles_dir.mkdir()
        self._home_patcher = patch("app.Path.home")
        self.mock_home = self._home_patcher.start()
        self.mock_home.return_value = Path(self.tmp) / "home"
        (Path(self.tmp) / "home").mkdir()

    def tearDown(self):
        self._home_patcher.stop()
        shutil.rmtree(self.tmp)

    def test_deploys_gitconfig(self):
        (self.pm.dotfiles_dir / "gitconfig").write_text("[user]\nname = Test\n")
        result = self.pm.deploy_dotfiles()
        self.assertEqual(len(result), 1)
        dest = self.mock_home.return_value / ".gitconfig"
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(), "[user]\nname = Test\n")

    def test_deploys_bashrc(self):
        (self.pm.dotfiles_dir / "bashrc").write_text("alias ll='ls -la'\n")
        result = self.pm.deploy_dotfiles()
        dest = self.mock_home.return_value / ".bashrc"
        self.assertTrue(dest.exists())

    def test_deploys_unknown_files_to_config(self):
        (self.pm.dotfiles_dir / "starship.toml").write_text("[character]\nsuccess_symbol = '[+]'\n")
        self.pm.deploy_dotfiles()
        dest = self.mock_home.return_value / ".config" / "starship.toml"
        self.assertTrue(dest.exists())

    def test_creates_backup_of_existing_file(self):
        home = self.mock_home.return_value
        home.mkdir(parents=True, exist_ok=True)
        existing = home / ".gitconfig"
        existing.write_text("[old]\n")
        (self.pm.dotfiles_dir / "gitconfig").write_text("[new]\n")
        self.pm.deploy_dotfiles()
        # Old file should be backed up — suffix logic: .gitconfig -> .gitconfig.backup
        backup = home / ".gitconfig.backup"
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(), "[old]\n")
        # New file deployed
        self.assertEqual(existing.read_text(), "[new]\n")

    def test_skips_hidden_files(self):
        (self.pm.dotfiles_dir / ".hidden").write_text("secret\n")
        (self.pm.dotfiles_dir / "visible").write_text("data\n")
        result = self.pm.deploy_dotfiles()
        self.assertEqual(len(result), 1)
        self.assertIn("visible", result[0])

    def test_skips_directories(self):
        (self.pm.dotfiles_dir / "subdir").mkdir()
        (self.pm.dotfiles_dir / "subdir" / "file.txt").write_text("nested\n")
        (self.pm.dotfiles_dir / "topfile").write_text("top\n")
        result = self.pm.deploy_dotfiles()
        self.assertEqual(len(result), 1)
        self.assertIn("topfile", result[0])

    def test_empty_dotfiles_dir(self):
        result = self.pm.deploy_dotfiles()
        self.assertEqual(result, [])


class TestRescanSystem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()
        self.pm.dotfiles_dir = Path(self.tmp) / "dotfiles"
        self.mock_home = Path(self.tmp) / "home"
        self.mock_home.mkdir()
        (self.mock_home / ".config").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_writes_flatpaks(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = [
            "com.discordapp.Discord\ncom.valvesoftware.Steam\n",  # flatpak list
            "",  # flatpak remotes
            "",  # rpm-ostree status
            "",  # gnome-extensions list
        ]
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.rescan_system()
        flatpaks = self.pm.read_flatpaks()
        self.assertIn("com.discordapp.Discord", flatpaks)
        self.assertIn("com.valvesoftware.Steam", flatpaks)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_writes_extensions(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = [
            "",  # flatpak list (empty)
            "",  # flatpak remotes
            "",  # rpm-ostree status
            "dash-to-dock@micxgx.gmail.com\ngsconnect@andyholmes.github.io\n",  # gnome-extensions list
        ]
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.rescan_system()
        extensions = self.pm.read_gnome_extensions()
        self.assertIn("dash-to-dock@micxgx.gmail.com", extensions)
        self.assertIn("gsconnect@andyholmes.github.io", extensions)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_dumps_dconf(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = [
            "",  # flatpak list
            "",  # flatpak remotes
            "",  # rpm-ostree status
            "",  # gnome-extensions list
        ]
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.rescan_system()
        dconf_file = self.pm.dconf_file()
        self.assertTrue(dconf_file.exists())

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_returns_results(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = [
            "app.one\n",  # flatpak list
            "",  # flatpak remotes
            "",  # rpm-ostree status
            "ext.one\n",  # gnome-extensions list
        ]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        self.assertTrue(any("flatpaks.txt" in r for r in results))
        self.assertTrue(any("extensions.txt" in r for r in results))
        self.assertTrue(any("dconf-settings.ini" in r for r in results))


class TestReadFlatpaks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_reads_from_correct_file(self):
        (self.pm.packages_dir / "flatpaks.txt").write_text("com.test.App\n")
        result = self.pm.read_flatpaks()
        self.assertEqual(result, ["com.test.App"])


class TestReadRpmOstree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_reads_from_correct_file(self):
        (self.pm.packages_dir / "rpm-ostree.txt").write_text("test-pkg\n")
        result = self.pm.read_rpm_ostree()
        self.assertEqual(result, ["test-pkg"])


class TestReadGnomeExtensions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_reads_from_correct_file(self):
        (self.pm.gnome_dir / "extensions.txt").write_text("test-ext@gnome.org\n")
        result = self.pm.read_gnome_extensions()
        self.assertEqual(result, ["test-ext@gnome.org"])


# ── Additional coverage tests ────────────────────────────────────────────────


class TestConstants(unittest.TestCase):
    def test_app_id(self):
        self.assertEqual(APP_ID, "io.github.jacob.distroconfig")

    def test_script_dir_is_path(self):
        self.assertIsInstance(SCRIPT_DIR, Path)

    def test_script_dir_contains_app_py(self):
        self.assertTrue((SCRIPT_DIR / "app.py").exists())

    def test_script_dir_contains_packages(self):
        self.assertTrue((SCRIPT_DIR / "packages").is_dir())

    def test_script_dir_contains_gnome(self):
        self.assertTrue((SCRIPT_DIR / "gnome").is_dir())

    def test_script_dir_contains_dotfiles(self):
        self.assertTrue((SCRIPT_DIR / "dotfiles").is_dir())


class TestPackageManagerInit(unittest.TestCase):
    def test_default_paths(self):
        pm = PackageManager()
        self.assertEqual(pm.packages_dir, SCRIPT_DIR / "packages")
        self.assertEqual(pm.gnome_dir, SCRIPT_DIR / "gnome")
        self.assertEqual(pm.dotfiles_dir, SCRIPT_DIR / "dotfiles")


class TestReadListExtended(unittest.TestCase):
    """Additional edge-case tests for _read_list."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_only_comments(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("# comment one\n# comment two\n# comment three\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, [])

    def test_only_blank_lines(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("\n\n\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, [])

    def test_unicode_items(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("日本語アイテム\némoji-app\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["日本語アイテム", "émoji-app"])

    def test_special_characters(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("app-with-dots.v2\napp@with@at\napp/with/slashes\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["app-with-dots.v2", "app@with@at", "app/with/slashes"])

    def test_single_item(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("lone-item\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["lone-item"])

    def test_long_line(self):
        path = self.pm.packages_dir / "test.txt"
        long_name = "a" * 500
        path.write_text(f"{long_name}\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, [long_name])

    def test_mixed_comments_and_blanks(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("# comment\n\nitem-a\n\n# another\n\nitem-b\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["item-a", "item-b"])

    def test_comment_between_items(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("item-a\n# middle comment\nitem-b\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["item-a", "item-b"])

    def test_preserves_item_order(self):
        path = self.pm.packages_dir / "test.txt"
        items = [f"item-{i}" for i in range(20)]
        path.write_text("\n".join(items) + "\n")
        result = self.pm._read_list(path)
        self.assertEqual(result, items)

    def test_no_trailing_newline(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("item-a\nitem-b")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["item-a", "item-b"])


class TestWriteListExtended(unittest.TestCase):
    """Additional edge-case tests for _write_list."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_overwrites_existing_file(self):
        path = self.pm.packages_dir / "test.txt"
        path.write_text("old-content\n")
        self.pm._write_list(path, ["new-item"], "Title", "hint")
        result = self.pm._read_list(path)
        self.assertEqual(result, ["new-item"])
        self.assertNotIn("old-content", path.read_text())

    def test_header_structure(self):
        path = self.pm.packages_dir / "test.txt"
        self.pm._write_list(path, [], "My Title", "my-format")
        lines = path.read_text().splitlines()
        self.assertEqual(lines[0], "# My Title")
        self.assertEqual(lines[1], "# Format: my-format")
        self.assertEqual(lines[2], "# Install with the distroconfig GUI")
        self.assertEqual(lines[3], "")

    def test_items_follow_header(self):
        path = self.pm.packages_dir / "test.txt"
        self.pm._write_list(path, ["a", "b"], "Title", "hint")
        lines = path.read_text().splitlines()
        self.assertEqual(lines[4], "a")
        self.assertEqual(lines[5], "b")

    def test_many_items(self):
        path = self.pm.packages_dir / "test.txt"
        items = [f"pkg-{i:03d}" for i in range(100)]
        self.pm._write_list(path, items, "Title", "hint")
        result = self.pm._read_list(path)
        self.assertEqual(result, items)


class TestWriteFlatpaksExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_empty_list(self):
        self.pm.write_flatpaks([])
        result = self.pm.read_flatpaks()
        self.assertEqual(result, [])

    def test_single_app(self):
        self.pm.write_flatpaks(["com.discordapp.Discord"])
        result = self.pm.read_flatpaks()
        self.assertEqual(result, ["com.discordapp.Discord"])

    def test_overwrites_previous(self):
        self.pm.write_flatpaks(["old.app"])
        self.pm.write_flatpaks(["new.app"])
        result = self.pm.read_flatpaks()
        self.assertEqual(result, ["new.app"])
        self.assertNotIn("old.app", result)


class TestWriteRpmOstreeExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_single_package(self):
        self.pm.write_rpm_ostree(["brave-origin"])
        result = self.pm.read_rpm_ostree()
        self.assertEqual(result, ["brave-origin"])

    def test_version_in_name(self):
        self.pm.write_rpm_ostree(["package-1.0.0", "package-beta-2.0"])
        result = self.pm.read_rpm_ostree()
        self.assertEqual(result, ["package-1.0.0", "package-beta-2.0"])


class TestWriteGnomeExtensionsExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_complex_extension_ids(self):
        exts = [
            "dash-to-dock@micxgx.gmail.com",
            "appindicatorsupport@rgcjonas.gmail.com",
            "AlphabeticalAppGrid@stuarthayhurst",
            "ok_mixer@enklht.github.io",
        ]
        self.pm.write_gnome_extensions(exts)
        result = self.pm.read_gnome_extensions()
        self.assertEqual(result, exts)


class TestLayeredRpmsExtended(unittest.TestCase):
    """Additional edge-case tests for rpm-ostree status parsing."""

    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_tab_indented_continuation(self, mock_check):
        mock_check.return_value = (
            "  LayeredPackages: pkg-a pkg-b\n"
            "\tpkg-c\n"
        )
        result = self.pm.layered_rpms()
        self.assertEqual(result, {"pkg-a", "pkg-b", "pkg-c"})

    @patch("app.subprocess.check_output")
    def test_only_local_packages_no_layered(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
                LocalPackages: opencode-1.18.5-1.x86_64
        """)
        result = self.pm.layered_rpms()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_layered_with_removed_packages(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
              RemovedBasePackages: firefox 153.0
              LayeredPackages: brave-origin
        """)
        result = self.pm.layered_rpms()
        self.assertEqual(result, {"brave-origin"})

    @patch("app.subprocess.check_output")
    def test_multiple_deployments_only_active(self, mock_check):
        mock_check.return_value = textwrap.dedent("""\
            State: idle
            Deployments:
            ● fedora:fedora/44/x86_64/silverblue
                      LayeredPackages: pkg-a pkg-b
              fedora:fedora/44/x86_64/silverblue
                      LayeredPackages: old-pkg
        """)
        result = self.pm.layered_rpms()
        # Parser processes all lines sequentially; both LayeredPackages blocks are parsed
        self.assertIn("pkg-a", result)
        self.assertIn("pkg-b", result)

    @patch("app.subprocess.check_output")
    def test_layered_packages_empty_after_colon(self, mock_check):
        mock_check.return_value = "  LayeredPackages:\n"
        result = self.pm.layered_rpms()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_subprocess_error(self, mock_check):
        mock_check.side_effect = OSError("permission denied")
        result = self.pm.layered_rpms()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_non_indented_line_breaks_layered(self, mock_check):
        mock_check.return_value = (
            "  LayeredPackages: vim\n"
            "SomeOtherSection: stuff\n"
        )
        result = self.pm.layered_rpms()
        self.assertEqual(result, {"vim"})

    @patch("app.subprocess.check_output")
    def test_subprocess_timeout(self, mock_check):
        import subprocess
        mock_check.side_effect = subprocess.TimeoutExpired("rpm-ostree", 10)
        result = self.pm.layered_rpms()
        self.assertEqual(result, set())


class TestEnabledGnomeExtensionsExtended(unittest.TestCase):
    """Additional edge-case tests for gsettings output parsing."""

    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_single_item_no_comma(self, mock_check):
        mock_check.return_value = "['single-ext@foo.com']\n"
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, {"single-ext@foo.com"})

    @patch("app.subprocess.check_output")
    def test_double_quotes(self, mock_check):
        mock_check.return_value = '[\"ext-one@foo.com\", \"ext-two@bar.org\"]\n'
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, {"ext-one@foo.com", "ext-two@bar.org"})

    @patch("app.subprocess.check_output")
    def test_whitespace_around_items(self, mock_check):
        mock_check.return_value = "[  'ext-one@foo.com' ,  'ext-two@bar.org'  ]\n"
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, {"ext-one@foo.com", "ext-two@bar.org"})

    @patch("app.subprocess.check_output")
    def test_no_newline_at_end(self, mock_check):
        mock_check.return_value = "['ext-one@foo.com', 'ext-two@bar.org']"
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, {"ext-one@foo.com", "ext-two@bar.org"})

    @patch("app.subprocess.check_output")
    def test_gsettings_error(self, mock_check):
        import subprocess
        mock_check.side_effect = subprocess.TimeoutExpired("gsettings", 5)
        result = self.pm.enabled_gnome_extensions()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_empty_string_output(self, mock_check):
        mock_check.return_value = ""
        result = self.pm.enabled_gnome_extensions()
        # Empty string is not "@as []" so it goes through strip/split logic
        # "".strip("[]") == "", "".split(",") == [""], filter skips empty
        self.assertEqual(result, set())


class TestInstalledFlatpaksExtended(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_single_flatpak(self, mock_check):
        mock_check.return_value = "com.discordapp.Discord\n"
        result = self.pm.installed_flatpaks()
        self.assertEqual(result, {"com.discordapp.Discord"})

    @patch("app.subprocess.check_output")
    def test_whitespace_only_lines_skipped(self, mock_check):
        mock_check.return_value = "  \n\t\n  \n"
        result = self.pm.installed_flatpaks()
        self.assertEqual(result, set())

    @patch("app.subprocess.check_output")
    def test_subprocess_returns_error(self, mock_check):
        import subprocess
        mock_check.side_effect = subprocess.CalledProcessError(1, "flatpak")
        result = self.pm.installed_flatpaks()
        self.assertEqual(result, set())


class TestInstalledGnomeExtensionsExtended(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.check_output")
    def test_single_extension(self, mock_check):
        mock_check.return_value = "dash-to-dock@micxgx.gmail.com\n"
        result = self.pm.installed_gnome_extensions()
        self.assertEqual(result, {"dash-to-dock@micxgx.gmail.com"})

    @patch("app.subprocess.check_output")
    def test_whitespace_stripped(self, mock_check):
        mock_check.return_value = "  ext-one@foo.com  \n  ext-two@bar.org  \n"
        result = self.pm.installed_gnome_extensions()
        self.assertEqual(result, {"ext-one@foo.com", "ext-two@bar.org"})

    @patch("app.subprocess.check_output")
    def test_subprocess_returns_error(self, mock_check):
        import subprocess
        mock_check.side_effect = subprocess.CalledProcessError(1, "gnome-extensions")
        result = self.pm.installed_gnome_extensions()
        self.assertEqual(result, set())


class TestInstallFlatpakExtended(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.run")
    def test_returns_result_object(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = self.pm.install_flatpak("com.discordapp.Discord")
        self.assertEqual(result.returncode, 0)

    @patch("app.subprocess.run")
    def test_failure_returned(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error: not found")
        result = self.pm.install_flatpak("com.nonexistent.app")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stderr)


class TestUninstallFlatpakExtended(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.run")
    def test_failure_returned(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="error: not installed")
        result = self.pm.uninstall_flatpak("com.nonexistent.app")
        self.assertEqual(result.returncode, 1)


class TestInstallRpmOstreeExtended(unittest.TestCase):
    def setUp(self):
        self.pm = PackageManager()

    @patch("app.subprocess.run")
    def test_single_package(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.install_rpm_ostree(["brave-origin"])
        mock_run.assert_called_once_with(
            ["sudo", "rpm-ostree", "install", "brave-origin"],
            capture_output=True, text=True,
        )

    @patch("app.subprocess.run")
    def test_failure_returned(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="Error: no space")
        result = self.pm.install_rpm_ostree(["big-package"])
        self.assertEqual(result.returncode, 1)


class TestApplyDconfExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.subprocess.run")
    def test_empty_dconf_file(self, mock_run):
        dconf_file = self.pm.gnome_dir / "dconf-settings.ini"
        dconf_file.write_text("")
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, msg = self.pm.apply_dconf()
        self.assertTrue(ok)
        args = mock_run.call_args
        self.assertEqual(args[1]["input"], "")

    @patch("app.subprocess.run")
    def test_multiline_dconf_content(self, mock_run):
        content = textwrap.dedent("""\
            [org/gnome/desktop/interface]
            color-scheme='prefer-dark'

            [org/gnome/desktop/input-sources]
            sources=[('xkb', 'dk')]
        """)
        dconf_file = self.pm.gnome_dir / "dconf-settings.ini"
        dconf_file.write_text(content)
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        ok, msg = self.pm.apply_dconf()
        self.assertTrue(ok)
        self.assertEqual(mock_run.call_args[1]["input"], content)

    @patch("app.subprocess.run")
    def test_stderr_returned(self, mock_run):
        dconf_file = self.pm.gnome_dir / "dconf-settings.ini"
        dconf_file.write_text("[test]\nkey='value'\n")
        mock_run.return_value = MagicMock(returncode=1, stderr="error: cannot load")
        ok, msg = self.pm.apply_dconf()
        self.assertFalse(ok)
        self.assertEqual(msg, "error: cannot load")


class TestDeployDotfilesExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.dotfiles_dir = Path(self.tmp) / "dotfiles"
        self.pm.dotfiles_dir.mkdir()
        self._home_patcher = patch("app.Path.home")
        self.mock_home = self._home_patcher.start()
        self.mock_home.return_value = Path(self.tmp) / "home"
        (Path(self.tmp) / "home").mkdir()

    def tearDown(self):
        self._home_patcher.stop()
        shutil.rmtree(self.tmp)

    def test_deploys_bash_profile(self):
        (self.pm.dotfiles_dir / "bash_profile").write_text("source .bashrc\n")
        self.pm.deploy_dotfiles()
        dest = self.mock_home.return_value / ".bash_profile"
        self.assertTrue(dest.exists())
        self.assertEqual(dest.read_text(), "source .bashrc\n")

    def test_deploys_multiple_files(self):
        (self.pm.dotfiles_dir / "gitconfig").write_text("[user]\n")
        (self.pm.dotfiles_dir / "bashrc").write_text("alias ll='ls'\n")
        (self.pm.dotfiles_dir / "starship.toml").write_text("[character]\n")
        result = self.pm.deploy_dotfiles()
        self.assertEqual(len(result), 3)

    def test_file_with_dot_in_name(self):
        (self.pm.dotfiles_dir / "input-remapper.conf").write_text("key=value\n")
        self.pm.deploy_dotfiles()
        dest = self.mock_home.return_value / ".config" / "input-remapper.conf"
        self.assertTrue(dest.exists())

    def test_file_with_underscore_in_name(self):
        (self.pm.dotfiles_dir / "my_config.toml").write_text("x=1\n")
        self.pm.deploy_dotfiles()
        dest = self.mock_home.return_value / ".config" / "my_config.toml"
        self.assertTrue(dest.exists())

    def test_backup_name_for_bashrc(self):
        home = self.mock_home.return_value
        home.mkdir(parents=True, exist_ok=True)
        existing = home / ".bashrc"
        existing.write_text("old\n")
        (self.pm.dotfiles_dir / "bashrc").write_text("new\n")
        self.pm.deploy_dotfiles()
        # .bashrc suffix is ".bashrc", so backup is ".bashrc.backup"
        backup = home / ".bashrc.backup"
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(), "old\n")

    def test_backup_name_for_bash_profile(self):
        home = self.mock_home.return_value
        home.mkdir(parents=True, exist_ok=True)
        existing = home / ".bash_profile"
        existing.write_text("old\n")
        (self.pm.dotfiles_dir / "bash_profile").write_text("new\n")
        self.pm.deploy_dotfiles()
        backup = home / ".bash_profile.backup"
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(), "old\n")

    def test_backup_name_for_unknown_file(self):
        home = self.mock_home.return_value
        config_dir = home / ".config"
        config_dir.mkdir(parents=True, exist_ok=True)
        existing = config_dir / "starship.toml"
        existing.write_text("old\n")
        (self.pm.dotfiles_dir / "starship.toml").write_text("new\n")
        self.pm.deploy_dotfiles()
        backup = config_dir / "starship.toml.backup"
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(), "old\n")

    def test_creates_parent_dirs(self):
        home = self.mock_home.return_value
        # Remove .config if it exists
        config = home / ".config"
        if config.exists():
            shutil.rmtree(config)
        (self.pm.dotfiles_dir / "custom.conf").write_text("data\n")
        self.pm.deploy_dotfiles()
        dest = home / ".config" / "custom.conf"
        self.assertTrue(dest.exists())

    def test_no_backup_when_no_existing_file(self):
        home = self.mock_home.return_value
        (self.pm.dotfiles_dir / "gitconfig").write_text("[new]\n")
        self.pm.deploy_dotfiles()
        backups = list(home.glob("*.backup"))
        self.assertEqual(len(backups), 0)

    def test_deploy_returns_path_mapping(self):
        (self.pm.dotfiles_dir / "gitconfig").write_text("[u]\n")
        result = self.pm.deploy_dotfiles()
        self.assertEqual(len(result), 1)
        self.assertIn("gitconfig", result[0])
        self.assertIn("->", result[0])


class TestRescanSystemExtended(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()
        self.pm.dotfiles_dir = Path(self.tmp) / "dotfiles"
        self.mock_home = Path(self.tmp) / "home"
        self.mock_home.mkdir()
        (self.mock_home / ".config").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_empty_system(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = ["", "", "", ""]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        self.assertTrue(any("dconf-settings.ini" in r for r in results))

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_overwrites_previous_flatpaks(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        self.pm.write_flatpaks(["old.app"])
        mock_check.side_effect = ["new.app\n", "", "", ""]
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.rescan_system()
        result = self.pm.read_flatpaks()
        self.assertEqual(result, ["new.app"])

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_overwrites_previous_extensions(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        self.pm.write_gnome_extensions(["old-ext@foo.com"])
        mock_check.side_effect = ["", "", "", "new-ext@bar.org\n"]
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.rescan_system()
        result = self.pm.read_gnome_extensions()
        self.assertEqual(result, ["new-ext@bar.org"])

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_dconf_file_is_valid_ini(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = ["", "", "", ""]
        mock_run.return_value = MagicMock(returncode=0)
        self.pm.rescan_system()
        content = self.pm.dconf_file().read_text()
        self.assertIsInstance(content, str)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_results_count(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = ["app1\napp2\n", "", "", "ext1\n"]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        self.assertTrue(len(results) >= 3)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_flatpak_count_in_result(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = ["a\nb\nc\n", "", "", ""]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        self.assertIn("3 apps", results[0])

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_extension_count_in_result(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = ["", "", "", "x\ny\n"]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        ext_result = [r for r in results if "extensions" in r][0]
        self.assertIn("2 extensions", ext_result)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_includes_layered_rpms(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = [
            "",  # flatpak list
            "",  # flatpak remotes
            "LayeredPackages: vim gcc\n",  # rpm-ostree status
            "",  # gnome-extensions list
        ]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        self.assertTrue(any("rpm-ostree.txt" in r for r in results))
        pkgs = self.pm.read_rpm_ostree()
        self.assertIn("vim", pkgs)
        self.assertIn("gcc", pkgs)

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_includes_flatpak_remotes(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = [
            "",  # flatpak list
            "flathub\thttps://flathub.org/repo/flathub.flatpakrepo\n",  # flatpak remotes
            "",  # rpm-ostree status
            "",  # gnome-extensions list
        ]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        self.assertTrue(any("flatpak-remotes.txt" in r for r in results))

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_includes_dotfiles_backup(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".gitconfig").write_text("[user]\nname = Test\n")
        mock_check.side_effect = ["", "", "", ""]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        dotfile_results = [r for r in results if "dotfiles" in r]
        self.assertEqual(len(dotfile_results), 1)
        self.assertIn("1 files backed up", dotfile_results[0])

    @patch("app.Path.home")
    @patch("app.subprocess.check_output")
    @patch("app.subprocess.run")
    def test_no_dotfiles_backup_when_empty(self, mock_run, mock_check, mock_home):
        mock_home.return_value = self.mock_home
        mock_check.side_effect = ["", "", "", ""]
        mock_run.return_value = MagicMock(returncode=0)
        results = self.pm.rescan_system()
        dotfile_results = [r for r in results if "dotfiles" in r]
        self.assertEqual(len(dotfile_results), 0)


class TestDeployDotfilesConfig(unittest.TestCase):
    """Test deploy_dotfiles writing to .config for unknown files."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.dotfiles_dir = Path(self.tmp) / "dotfiles"
        self.pm.dotfiles_dir.mkdir()
        self.mock_home = Path(self.tmp) / "home"
        self.mock_home.mkdir()
        (self.mock_home / ".config").mkdir()
        self._home_patcher = patch("app.Path.home")
        self.mock_home_ref = self._home_patcher.start()
        self.mock_home_ref.return_value = self.mock_home

    def tearDown(self):
        self._home_patcher.stop()
        shutil.rmtree(self.tmp)

    def test_unknown_file_goes_to_config(self):
        (self.pm.dotfiles_dir / "starship.toml").write_text("[prompt]\n")
        result = self.pm.deploy_dotfiles()
        dest = self.mock_home / ".config" / "starship.toml"
        self.assertTrue(dest.exists())
        self.assertIn("starship.toml", result[0])

    def test_known_file_goes_to_home(self):
        (self.pm.dotfiles_dir / "gitconfig").write_text("[user]\n")
        result = self.pm.deploy_dotfiles()
        dest = self.mock_home / ".gitconfig"
        self.assertTrue(dest.exists())

    def test_creates_backup_of_existing(self):
        (self.mock_home / ".gitconfig").write_text("[old]\n")
        (self.pm.dotfiles_dir / "gitconfig").write_text("[new]\n")
        self.pm.deploy_dotfiles()
        self.assertTrue((self.mock_home / ".gitconfig.backup").exists())
        self.assertEqual((self.mock_home / ".gitconfig").read_text(), "[new]\n")


class TestReadWriteIntegration(unittest.TestCase):
    """Integration tests: write then read, multiple roundtrips."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_flatpak_roundtrip(self):
        apps = ["com.discordapp.Discord", "com.valvesoftware.Steam", "org.gnome.Calculator"]
        self.pm.write_flatpaks(apps)
        self.assertEqual(self.pm.read_flatpaks(), apps)

    def test_rpm_roundtrip(self):
        pkgs = ["brave-origin", "input-remapper", "libnsl", "tailscale", "xterm"]
        self.pm.write_rpm_ostree(pkgs)
        self.assertEqual(self.pm.read_rpm_ostree(), pkgs)

    def test_extensions_roundtrip(self):
        exts = ["dash-to-dock@micxgx.gmail.com", "gsconnect@andyholmes.github.io", "app-hider@lynith.dev"]
        self.pm.write_gnome_extensions(exts)
        self.assertEqual(self.pm.read_gnome_extensions(), exts)

    def test_multiple_write_read_cycles(self):
        for i in range(5):
            apps = [f"app-{i}.test" for i in range(i + 1)]
            self.pm.write_flatpaks(apps)
            self.assertEqual(self.pm.read_flatpaks(), apps)

    def test_write_flatpaks_then_rpm_independent(self):
        self.pm.write_flatpaks(["com.discordapp.Discord"])
        self.pm.write_rpm_ostree(["brave-origin"])
        self.assertEqual(self.pm.read_flatpaks(), ["com.discordapp.Discord"])
        self.assertEqual(self.pm.read_rpm_ostree(), ["brave-origin"])


class TestBackupDotfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()
        self.pm.gnome_dir = Path(self.tmp) / "gnome"
        self.pm.gnome_dir.mkdir()
        self.pm.dotfiles_dir = Path(self.tmp) / "dotfiles"
        self.mock_home = Path(self.tmp) / "home"
        self.mock_home.mkdir()
        (self.mock_home / ".config").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.Path.home")
    def test_copies_gitconfig(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".gitconfig").write_text("[user]\nname = Test\n")
        result = self.pm.backup_dotfiles()
        self.assertIn("gitconfig", result)
        self.assertEqual((self.pm.dotfiles_dir / "gitconfig").read_text(), "[user]\nname = Test\n")

    @patch("app.Path.home")
    def test_copies_bashrc(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".bashrc").write_text("alias ll='ls -la'\n")
        result = self.pm.backup_dotfiles()
        self.assertIn("bashrc", result)
        self.assertTrue((self.pm.dotfiles_dir / "bashrc").exists())

    @patch("app.Path.home")
    def test_copies_bash_profile(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".bash_profile").write_text("export PATH=$PATH:/opt\n")
        result = self.pm.backup_dotfiles()
        self.assertIn("bash_profile", result)

    @patch("app.Path.home")
    def test_copies_profile(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".profile").write_text("export LANG=en_US.UTF-8\n")
        result = self.pm.backup_dotfiles()
        self.assertIn("profile", result)

    @patch("app.Path.home")
    def test_copies_config_files(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".config" / "myapp.conf").write_text("setting=true\n")
        result = self.pm.backup_dotfiles()
        self.assertIn("myapp.conf", result)
        self.assertTrue((self.pm.dotfiles_dir / "myapp.conf").exists())

    @patch("app.Path.home")
    def test_skips_hidden_config_files(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".config" / ".hidden").write_text("secret\n")
        result = self.pm.backup_dotfiles()
        self.assertNotIn(".hidden", result)

    @patch("app.Path.home")
    def test_skips_nonexistent_files(self, mock_home):
        mock_home.return_value = self.mock_home
        result = self.pm.backup_dotfiles()
        self.assertEqual(result, [])

    @patch("app.Path.home")
    def test_does_not_overwrite_existing(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".gitconfig").write_text("new content\n")
        self.pm.dotfiles_dir.mkdir(parents=True, exist_ok=True)
        (self.pm.dotfiles_dir / "gitconfig").write_text("old content\n")
        result = self.pm.backup_dotfiles()
        self.assertEqual((self.pm.dotfiles_dir / "gitconfig").read_text(), "new content\n")

    @patch("app.Path.home")
    def test_creates_dotfiles_dir(self, mock_home):
        mock_home.return_value = self.mock_home
        (self.mock_home / ".gitconfig").write_text("[user]\n")
        self.pm.backup_dotfiles()
        self.assertTrue(self.pm.dotfiles_dir.exists())


class TestBackupFlatpakRemotes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pm = PackageManager()
        self.pm.packages_dir = Path(self.tmp) / "packages"
        self.pm.packages_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("app.subprocess.check_output")
    def test_writes_remotes(self, mock_check):
        mock_check.return_value = "flathub\thttps://flathub.org/repo/flathub.flatpakrepo\nfedora\thttps://dl.fedoraproject.org/pub/flatpak/repo-flatpak-repo.flatpakrepo\n"
        count = self.pm.backup_flatpak_remotes()
        self.assertEqual(count, 2)
        content = (self.pm.packages_dir / "flatpak-remotes.txt").read_text()
        self.assertIn("flathub", content)
        self.assertIn("fedora", content)

    @patch("app.subprocess.check_output")
    def test_empty_remotes(self, mock_check):
        mock_check.return_value = ""
        count = self.pm.backup_flatpak_remotes()
        self.assertEqual(count, 0)

    @patch("app.subprocess.check_output")
    def test_header_structure(self, mock_check):
        mock_check.return_value = "flathub\thttps://flathub.org/repo\n"
        self.pm.backup_flatpak_remotes()
        lines = (self.pm.packages_dir / "flatpak-remotes.txt").read_text().splitlines()
        self.assertTrue(lines[0].startswith("# Flatpak remotes"))
        self.assertIn("name", lines[1])
        self.assertIn("Restore", lines[2])

    @patch("app.subprocess.check_output")
    def test_exception_returns_zero(self, mock_check):
        mock_check.side_effect = FileNotFoundError("flatpak not found")
        count = self.pm.backup_flatpak_remotes()
        self.assertEqual(count, 0)

    @patch("app.subprocess.check_output")
    def test_malformed_line_skipped(self, mock_check):
        mock_check.return_value = "nourlhere\nflathub\thttps://flathub.org/repo\n"
        count = self.pm.backup_flatpak_remotes()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
