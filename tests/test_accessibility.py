import unittest

try:
    import gi
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gio, Gtk
    from ubuntu_l10n.accessibility import AccessibilityManager
except (ImportError, ValueError):
    Adw = Gio = Gtk = AccessibilityManager = None


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
