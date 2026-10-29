import unittest
from unittest.mock import Mock, patch

try:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gdk, Gio, GLib, Gtk
except (ImportError, ValueError):
    Adw = Gdk = Gio = GLib = Gtk = None

if Adw is not None:
    from ubuntu_l10n.accessibility import (
        AccessibilityManager, associate_mnemonic, set_accessible_label,
    )
    from ubuntu_l10n.app import MainWindow, SHORTCUTS
    from ubuntu_l10n import app as app_module
    from ubuntu_l10n.scraper import DISTRO_VERSIONS, EOL_DISTROS, ESM_DISTROS
else:
    AccessibilityManager = MainWindow = SHORTCUTS = app_module = None
    DISTRO_VERSIONS = EOL_DISTROS = ESM_DISTROS = None


@unittest.skipIf(Adw is None, "GTK 4 and libadwaita are not installed")
class AccessibilityManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Gtk.init()

    def setUp(self):
        self.app = Adw.Application(
            application_id="se.danielnylander.UbuntuL10nTest",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.window = Gtk.Window()
        self.manager = AccessibilityManager(self.window, self.app)

    def tearDown(self):
        self.window.destroy()

    def test_translated_control_labels_get_distinct_mnemonics(self):
        for texts in (("Release:", "Language:", "Sort:"), ("Utgåva:", "Språk:", "Sortera:")):
            with self.subTest(labels=texts):
                used = set()
                labels = [Gtk.Label(label=text) for text in texts]
                controls = [Gtk.DropDown(), Gtk.DropDown(), Gtk.DropDown()]

                keys = [
                    associate_mnemonic(label, control, used)
                    for label, control in zip(labels, controls)
                ]

                self.assertEqual(len(set(keys)), 3)
                for label, control in zip(labels, controls):
                    self.assertIs(label.get_mnemonic_widget(), control)

    def test_icon_control_can_receive_accessible_name(self):
        button = Mock()

        set_accessible_label(button, "Refresh data")

        button.update_property.assert_called_once_with(
            [Gtk.AccessibleProperty.LABEL], ["Refresh data"],
        )

    def test_control_f_focuses_package_search(self):
        window = Mock()
        window._search = Mock()

        handled = MainWindow._on_key_pressed(
            window, Mock(), Gdk.KEY_f, 0, Gdk.ModifierType.CONTROL_MASK,
        )

        self.assertTrue(handled)
        window._search.grab_focus.assert_called_once_with()

    def test_unrelated_key_is_not_consumed_by_search_shortcut(self):
        window = Mock()
        window._search = Mock()

        handled = MainWindow._on_key_pressed(
            window, Mock(), Gdk.KEY_a, 0, Gdk.ModifierType.CONTROL_MASK,
        )

        self.assertFalse(handled)
        window._search.grab_focus.assert_not_called()

    def test_shortcut_help_lists_search_zoom_and_contrast_controls(self):
        shortcuts = dict(SHORTCUTS)

        self.assertEqual(shortcuts["<Control>f"], "Search packages…")
        self.assertEqual(shortcuts["<Control>plus"], "Increase text size")
        self.assertEqual(shortcuts["<Control>equal"], "Increase text size")
        self.assertEqual(shortcuts["<Control>minus"], "Decrease text size")
        self.assertEqual(shortcuts["<Control>0"], "Reset text size")
        self.assertEqual(shortcuts["<Control><Shift>h"], "Toggle high-contrast styling")

    def test_release_list_includes_current_lts_and_marks_interim_eol(self):
        self.assertEqual(DISTRO_VERSIONS["stonking"], "26.10")
        self.assertEqual(DISTRO_VERSIONS["jammy"], "22.04 LTS")
        self.assertEqual(EOL_DISTROS, {"questing", "plucky", "oracular"})
        self.assertEqual(ESM_DISTROS, {"focal"})
        with patch.object(app_module, "_", side_effect=lambda message: message):
            self.assertEqual(
                app_module.format_distro_label("questing", "25.10"),
                "Questing (25.10) — no longer supported",
            )
            self.assertEqual(
                app_module.format_distro_label("resolute", "26.04 LTS"),
                "Resolute (26.04 LTS)",
            )
            self.assertEqual(
                app_module.format_distro_label("focal", "20.04 LTS"),
                "Focal (20.04 LTS) — standard support ended; ESM via Ubuntu Pro",
            )

    def test_registers_zoom_and_contrast_actions_with_shortcuts(self):
        self.assertIsNotNone(self.app.lookup_action("zoom-in"))
        self.assertIsNotNone(self.app.lookup_action("zoom-out"))
        self.assertIsNotNone(self.app.lookup_action("zoom-reset"))
        self.assertIsNotNone(self.app.lookup_action("toggle-high-contrast"))
        self.assertEqual(
            self.app.get_accels_for_action("app.zoom-in"),
            ["<Control>plus", "<Control>equal"],
        )

    def test_zoom_actions_respect_limits_and_reset(self):
        self.manager._apply_css()
        zoom_in = self.app.lookup_action("zoom-in")
        for _ in range(40):
            zoom_in.activate(None)
        self.assertAlmostEqual(self.manager._font_scale, 3.0)

        zoom_out = self.app.lookup_action("zoom-out")
        for _ in range(40):
            zoom_out.activate(None)
        self.assertAlmostEqual(self.manager._font_scale, 0.5)

        self.app.lookup_action("zoom-reset").activate(None)
        self.assertEqual(self.manager._font_scale, 1.0)

    def test_contrast_action_toggles_window_style(self):
        action = self.app.lookup_action("toggle-high-contrast")
        parse_errors = []
        self.manager._css.connect(
            "parsing-error",
            lambda _provider, _section, error: parse_errors.append(str(error)),
        )

        action.activate(None)
        self.assertTrue(self.window.has_css_class("high-contrast"))
        action.activate(None)
        self.assertFalse(self.window.has_css_class("high-contrast"))
        self.assertEqual(parse_errors, [])


@unittest.skipIf(Adw is None, "GTK 4 and libadwaita are not installed")
class DataLoadStateTests(unittest.TestCase):
    def test_last_updated_uses_the_translated_label(self):
        window = Mock()
        with (
            patch.object(app_module, "_", return_value="Senast uppdaterad"),
            patch.object(app_module, "_dt_now") as clock,
        ):
            clock.now.return_value.strftime.return_value = "2026-10-29 12:30"
            MainWindow._update_last_updated(window)

        window._last_update_label.set_text.assert_called_once_with(
            "Senast uppdaterad: 2026-10-29 12:30",
        )

    def test_ignores_errors_from_an_outdated_selection(self):
        window = Mock()
        window._load_generation = 3

        result = MainWindow._on_data_error(
            window, "old network error", 2, ("noble", "sv"),
        )

        self.assertEqual(result, GLib.SOURCE_REMOVE)
        window._spinner.stop.assert_not_called()
        window._loading_label.set_text.assert_not_called()

    def test_ignores_progress_from_an_outdated_selection(self):
        window = Mock()
        window._load_generation = 3

        result = MainWindow._show_load_progress(window, 2, 300, 1200)

        self.assertEqual(result, GLib.SOURCE_REMOVE)
        window._loading_label.set_text.assert_not_called()

    def test_network_error_keeps_matching_cached_results_visible(self):
        window = Mock()
        window._load_generation = 3
        window.packages = [Mock()]
        window._loaded_key = ("noble", "sv")
        window._cache_age = 120
        window._heatmap_mode = False
        window.announce_to_screen_reader = Mock()

        result = MainWindow._on_data_error(
            window, "raw connection error", 3, ("noble", "sv"),
        )

        self.assertEqual(result, GLib.SOURCE_REMOVE)
        message = window._last_update_label.set_text.call_args.args[0]
        self.assertIn("The last results are still visible", message)
        self.assertNotIn("raw connection error", message)
        window._stack.set_visible_child_name.assert_called_once_with("content")
        window.announce_to_screen_reader.assert_called_once_with(
            window._last_update_label, message,
        )


if __name__ == "__main__":
    unittest.main()
