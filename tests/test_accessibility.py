import unittest
from unittest.mock import Mock

try:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gdk, Gio, Gtk
except (ImportError, ValueError):
    Adw = Gdk = Gio = Gtk = None

if Adw is not None:
    from ubuntu_l10n.accessibility import (
        AccessibilityManager, associate_mnemonic, set_accessible_label,
    )
    from ubuntu_l10n.app import MainWindow
else:
    AccessibilityManager = MainWindow = None


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


if __name__ == "__main__":
    unittest.main()
