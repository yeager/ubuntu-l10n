"""Accessibility features: zoom, high contrast, ATK."""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio


def set_accessible_label(widget, label):
    """Give a widget a name that assistive technology can announce."""
    widget.update_property(
        [Gtk.AccessibleProperty.LABEL],
        [label],
    )


def set_accessible_description(widget, description):
    """Explain a control's purpose to assistive technology."""
    widget.update_property(
        [Gtk.AccessibleProperty.DESCRIPTION],
        [description],
    )


def associate_mnemonic(label, widget, used_mnemonics):
    """Connect a translated label to its control using an unused letter."""
    text = label.get_text()
    for index, character in enumerate(text):
        key = character.casefold()
        if character.isalnum() and key not in used_mnemonics:
            label.set_text_with_mnemonic(f"{text[:index]}_{text[index:]}")
            used_mnemonics.add(key)
            label.set_mnemonic_widget(widget)
            return key
    label.set_mnemonic_widget(widget)
    return None


class AccessibilityManager:
    """Manages accessibility features for a GTK4 window."""

    def __init__(self, window, app=None):
        self._window = window
        self._app = app or window.get_application()
        self._font_scale = 1.0
        self._high_contrast = False
        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
        self._setup_actions()

    def _setup_actions(self):
        if self._app is None:
            return
        actions = [
            ('zoom-in', self._zoom_in, ['<Control>plus', '<Control>equal']),
            ('zoom-out', self._zoom_out, ['<Control>minus']),
            ('zoom-reset', self._zoom_reset, ['<Control>0']),
            ('toggle-high-contrast', self._toggle_hc, ['<Control><Shift>h']),
        ]
        for name, cb, accels in actions:
            if not self._app.lookup_action(name):
                action = Gio.SimpleAction.new(name, None)
                action.connect('activate', lambda a, p, c=cb: c())
                self._app.add_action(action)
                self._app.set_accels_for_action(f'app.{name}', accels)

    def _apply_css(self):
        css = f'window {{ font-size: {self._font_scale}em; }}'
        if self._high_contrast:
            css += """
            window.high-contrast {
                background-color: #000000;
                color: #ffffff;
                border: 2px solid #ffffff;
                font-weight: bold;
            }"""
            css += """
            window.high-contrast label,
            window.high-contrast .dim-label {
                color: #ffffff;
            }
            window.high-contrast button,
            window.high-contrast entry,
            window.high-contrast dropdown {
                background-color: #000000;
                color: #ffffff;
                border: 2px solid #ffffff;
            }
            window.high-contrast :focus {
                border: 3px solid #ffff00;
            }
            """
        self._css.load_from_string(css)

    def _zoom_in(self):
        self._font_scale = min(self._font_scale + 0.1, 3.0)
        self._apply_css()

    def _zoom_out(self):
        self._font_scale = max(self._font_scale - 0.1, 0.5)
        self._apply_css()

    def _zoom_reset(self):
        self._font_scale = 1.0
        self._apply_css()

    def _toggle_hc(self):
        self._high_contrast = not self._high_contrast
        if self._high_contrast:
            self._window.add_css_class('high-contrast')
        else:
            self._window.remove_css_class('high-contrast')
        self._apply_css()
