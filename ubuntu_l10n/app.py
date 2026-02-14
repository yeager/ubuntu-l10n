"""Ubuntu Translation Statistics - GTK4/Libadwaita app."""

import gettext
import locale
import os
import sys
import threading
import webbrowser

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio, Pango, Gdk  # noqa: E402

from .scraper import (  # noqa: E402
    fetch_all_packages, PackageStats,
    DISTRO_VERSIONS, LANGUAGES,
    load_config, save_config,
)

# i18n setup
LOCALEDIR = os.path.join(os.path.dirname(__file__), '..', 'po', 'locale')
if not os.path.isdir(LOCALEDIR):
    LOCALEDIR = '/usr/share/locale'
gettext.bindtextdomain('ubuntu-l10n', LOCALEDIR)
gettext.textdomain('ubuntu-l10n')
_ = gettext.gettext

VERSION = "0.1.0"
APP_ID = "se.danielnylander.ubuntu-l10n"
FIRST_RUN_KEY = "first_run_done"


def get_system_language() -> str:
    """Detect system language code."""
    try:
        loc = locale.getlocale()[0]  # e.g. 'sv_SE'
        if loc:
            # Try exact match first
            if loc in LANGUAGES:
                return loc
            code = loc.split("_")[0]
            if code in LANGUAGES:
                return code
    except Exception:
        pass
    return "sv"


class PackageRow(Gtk.Box):
    """A single package row with progress bar and stats."""

    def __init__(self, pkg: PackageStats):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.pkg = pkg
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        # Top line: name + percentage
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top.set_hexpand(True)

        name_label = Gtk.Label(label=pkg.name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_hexpand(True)
        name_label.add_css_class("heading")
        top.append(name_label)

        pct_label = Gtk.Label(label=f"{pkg.translated_pct:.1f}%")
        pct_label.set_halign(Gtk.Align.END)
        if pkg.translated_pct >= 100:
            pct_label.add_css_class("success")
        elif pkg.translated_pct >= 80:
            pct_label.add_css_class("warning")
        else:
            pct_label.add_css_class("error")
        pct_label.add_css_class("caption-heading")
        top.append(pct_label)

        self.append(top)

        # Progress bar
        progress = Gtk.ProgressBar()
        progress.set_fraction(pkg.translated_pct / 100.0)
        progress.set_hexpand(True)
        if pkg.translated_pct >= 100:
            progress.add_css_class("success")
        elif pkg.translated_pct >= 80:
            progress.add_css_class("accent")
        else:
            progress.add_css_class("error")
        self.append(progress)

        # Bottom line: stats
        stats_parts = []
        if pkg.total > 0:
            stats_parts.append(
                _("{translated}/{total} translated").format(
                    translated=pkg.translated, total=pkg.total))
        if pkg.untranslated > 0:
            stats_parts.append(
                _("{count} untranslated").format(count=pkg.untranslated))
        if pkg.need_review > 0:
            stats_parts.append(
                _("{count} need review").format(count=pkg.need_review))
        if pkg.changed > 0:
            stats_parts.append(
                _("{count} changed").format(count=pkg.changed))

        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        stats_label = Gtk.Label(label=" · ".join(stats_parts))
        stats_label.set_halign(Gtk.Align.START)
        stats_label.set_hexpand(True)
        stats_label.add_css_class("dim-label")
        stats_label.add_css_class("caption")
        bottom.append(stats_label)

        if pkg.last_edited:
            date_label = Gtk.Label(
                label=_("{date} by {editor}").format(
                    date=pkg.last_edited, editor=pkg.last_editor))
            date_label.set_halign(Gtk.Align.END)
            date_label.add_css_class("dim-label")
            date_label.add_css_class("caption")
            bottom.append(date_label)

        self.append(bottom)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Ubuntu Translation Statistics"))
        self.set_default_size(900, 700)

        self.packages: list[PackageStats] = []
        self.filtered_packages: list[PackageStats] = []
        self.sort_ascending = True
        self._from_cache = False
        self._cache_age = 0

        # Detect system language
        sys_lang = get_system_language()

        # Main layout
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        # Header bar
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Title
        title = Adw.WindowTitle(
            title=_("Ubuntu L10n"),
            subtitle=_("Translation Statistics"))
        header.set_title_widget(title)
        self._title_widget = title

        # Refresh button
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh data"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_start(refresh_btn)

        # Sort button
        sort_btn = Gtk.Button(icon_name="view-sort-descending-symbolic")
        sort_btn.set_tooltip_text(_("Toggle sort order"))
        sort_btn.connect("clicked", self._on_toggle_sort)
        header.pack_end(sort_btn)
        self._sort_btn = sort_btn

        # Menu button
        menu = Gio.Menu()
        menu.append(_("Settings"), "win.settings")
        menu.append(_("About"), "win.about")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        menu_btn.set_tooltip_text(_("Menu"))
        header.pack_end(menu_btn)

        # Actions
        settings_action = Gio.SimpleAction(name="settings")
        settings_action.connect("activate", self._on_settings)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction(name="about")
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Content box
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        toolbar_view.set_content(content)

        # Controls bar
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.set_margin_start(12)
        controls.set_margin_end(12)
        controls.set_margin_top(8)
        controls.set_margin_bottom(8)

        # Distribution selector
        distro_model = Gtk.StringList()
        distro_items = []
        for code, ver in DISTRO_VERSIONS.items():
            label = f"{code.capitalize()} ({ver})"
            distro_model.append(label)
            distro_items.append(code)
        self._distro_items = distro_items

        distro_drop = Gtk.DropDown(model=distro_model)
        distro_drop.set_selected(0)
        distro_drop.connect("notify::selected", self._on_distro_changed)
        self._distro_drop = distro_drop

        distro_label = Gtk.Label(label=_("Release:"))
        distro_label.add_css_class("dim-label")
        controls.append(distro_label)
        controls.append(distro_drop)

        # Language selector
        lang_model = Gtk.StringList()
        lang_items = []
        selected_lang_idx = 0
        for i, (code, name) in enumerate(sorted(LANGUAGES.items(), key=lambda x: x[1])):
            lang_model.append(f"{name} ({code})")
            lang_items.append(code)
            if code == sys_lang:
                selected_lang_idx = i
        self._lang_items = lang_items

        lang_drop = Gtk.DropDown(model=lang_model)
        lang_drop.set_selected(selected_lang_idx)
        lang_drop.connect("notify::selected", self._on_lang_changed)
        self._lang_drop = lang_drop

        lang_label = Gtk.Label(label=_("Language:"))
        lang_label.add_css_class("dim-label")
        controls.append(lang_label)
        controls.append(lang_drop)

        # Search
        search = Gtk.SearchEntry()
        search.set_placeholder_text(_("Search packages…"))
        search.set_hexpand(True)
        search.connect("search-changed", self._on_search_changed)
        self._search = search
        controls.append(search)

        content.append(controls)

        # Summary bar
        self._summary = Gtk.Label(label="")
        self._summary.set_halign(Gtk.Align.START)
        self._summary.set_margin_start(12)
        self._summary.set_margin_bottom(4)
        self._summary.add_css_class("caption")
        self._summary.add_css_class("dim-label")
        content.append(self._summary)

        # Overall progress
        self._overall_progress = Gtk.ProgressBar()
        self._overall_progress.set_margin_start(12)
        self._overall_progress.set_margin_end(12)
        self._overall_progress.set_margin_bottom(8)
        content.append(self._overall_progress)

        # Loading spinner
        self._spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._spinner_box.set_valign(Gtk.Align.CENTER)
        self._spinner_box.set_vexpand(True)
        spinner = Gtk.Spinner()
        spinner.set_size_request(48, 48)
        spinner.start()
        self._spinner = spinner
        self._spinner_box.append(spinner)
        self._loading_label = Gtk.Label(label=_("Loading translations…"))
        self._loading_label.add_css_class("dim-label")
        self._spinner_box.append(self._loading_label)

        # Scrolled list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_margin_start(12)
        self._list_box.set_margin_end(12)
        self._list_box.set_margin_bottom(12)
        self._list_box.connect("row-activated", self._on_row_activated)
        scrolled.set_child(self._list_box)

        # Stack for loading/content
        self._stack = Gtk.Stack()
        self._stack.add_named(self._spinner_box, "loading")
        self._stack.add_named(scrolled, "content")
        content.append(self._stack)

        # Apply CSS
        self._apply_css()

        # Show welcome dialog on first run, then load data
        config = load_config()
        if not config.get(FIRST_RUN_KEY):
            GLib.idle_add(self._show_welcome)
        else:
            self._load_data()

    def _show_welcome(self):
        """Show welcome dialog on first launch."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Welcome to Ubuntu L10n!"),
            body=_(
                "This app shows translation progress for Ubuntu packages "
                "on Launchpad.\n\n"
                "• Pick a release and language from the top bar\n"
                "• Click any package to open it on Launchpad\n"
                "• Use the refresh button to get the latest data\n\n"
                "Data is cached locally for 1 hour to reduce load on "
                "Launchpad servers."
            ),
        )
        dialog.add_response("ok", _("Get Started"))
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def on_response(dlg, response):
            config = load_config()
            config[FIRST_RUN_KEY] = True
            save_config(config)
            self._load_data()

        dialog.connect("response", on_response)
        dialog.present()

    def _apply_css(self):
        css = b"""
        progressbar.success trough progress {
            background-color: @success_color;
        }
        progressbar.error trough progress {
            background-color: @error_color;
        }
        .success { color: @success_color; }
        .warning { color: @warning_color; }
        .error { color: @error_color; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    @property
    def _current_distro(self) -> str:
        return self._distro_items[self._distro_drop.get_selected()]

    @property
    def _current_lang(self) -> str:
        return self._lang_items[self._lang_drop.get_selected()]

    def _on_refresh(self, _btn):
        self._load_data(force=True)

    def _on_distro_changed(self, _drop, _pspec):
        self._load_data()

    def _on_lang_changed(self, _drop, _pspec):
        self._load_data()

    def _on_search_changed(self, entry):
        self._filter_and_display()

    def _on_toggle_sort(self, _btn):
        self.sort_ascending = not self.sort_ascending
        icon = ("view-sort-ascending-symbolic" if self.sort_ascending
                else "view-sort-descending-symbolic")
        self._sort_btn.set_icon_name(icon)
        self._filter_and_display()

    def _on_row_activated(self, _list_box, row):
        child = row.get_child()
        if isinstance(child, PackageRow):
            webbrowser.open(child.pkg.translate_url)

    def _on_settings(self, _action, _param):
        """Show settings dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Settings"),
            body=_(
                "Ubuntu L10n uses Launchpad's public translation pages.\n"
                "No API key is required."
            ),
        )

        # Cache control
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      margin_top=12)
        clear_btn = Gtk.Button(label=_("Clear Cache"))
        clear_btn.connect("clicked", self._on_clear_cache)
        box.append(clear_btn)
        dialog.set_extra_child(box)

        dialog.add_response("close", _("Close"))
        dialog.present()

    def _on_clear_cache(self, _btn):
        """Clear the local cache."""
        from .scraper import CACHE_FILE
        try:
            CACHE_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    def _on_about(self, _action, _param):
        """Show about dialog."""
        about = Adw.AboutWindow(
            transient_for=self,
            application_name=_("Ubuntu L10n"),
            application_icon="applications-internet",
            version=VERSION,
            developer_name="Daniel Nylander",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            copyright="© 2025 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/ubuntu-l10n",
            issue_url="https://github.com/yeager/ubuntu-l10n/issues",
        )
        about.present()

    def _load_data(self, force=False):
        self._stack.set_visible_child_name("loading")
        self._loading_label.set_text(_("Loading translations…"))
        distro = self._current_distro
        lang = self._current_lang

        self._title_widget.set_subtitle(
            f"{distro.capitalize()} · {LANGUAGES.get(lang, lang)}"
        )

        def progress_cb(loaded, total):
            GLib.idle_add(
                self._loading_label.set_text,
                _("Loading… {loaded}/{total} templates").format(
                    loaded=loaded, total=total)
            )

        def cache_cb(packages, age_minutes):
            GLib.idle_add(self._on_data_loaded, packages, True, age_minutes)

        def worker():
            try:
                packages = fetch_all_packages(
                    distro, lang,
                    callback=progress_cb,
                    cache_cb=None if force else cache_cb,
                    force=force,
                )
                GLib.idle_add(self._on_data_loaded, packages, False, 0)
            except Exception as e:
                GLib.idle_add(self._on_data_error, str(e))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_data_loaded(self, packages: list[PackageStats],
                        from_cache: bool = False, age_minutes: int = 0):
        self.packages = packages
        self._from_cache = from_cache
        self._cache_age = age_minutes
        self._filter_and_display()
        self._stack.set_visible_child_name("content")

    def _on_data_error(self, error: str):
        self._loading_label.set_text(_("Error: {error}").format(error=error))

    def _filter_and_display(self):
        query = self._search.get_text().lower().strip()

        filtered = self.packages
        if query:
            filtered = [p for p in filtered if query in p.name.lower()]

        # Sort by translated percentage
        filtered.sort(key=lambda p: p.translated_pct,
                       reverse=not self.sort_ascending)
        self.filtered_packages = filtered

        # Update summary
        if self.packages:
            total_strings = sum(p.total for p in self.packages)
            total_translated = sum(p.translated for p in self.packages)
            total_untranslated = sum(p.untranslated for p in self.packages)
            overall_pct = ((total_translated / total_strings * 100)
                           if total_strings > 0 else 0)

            fully = sum(1 for p in self.packages if p.translated_pct >= 100)
            summary = _(
                "{count} templates · "
                "{translated}/{total} strings ({pct}%) · "
                "{untranslated} untranslated · "
                "{fully} fully translated"
            ).format(
                count=len(self.packages),
                translated=f"{total_translated:,}",
                total=f"{total_strings:,}",
                pct=f"{overall_pct:.1f}",
                untranslated=f"{total_untranslated:,}",
                fully=fully,
            )
            if self._from_cache:
                summary += " · " + _("Cached ({age} min ago)").format(
                    age=self._cache_age)
            self._summary.set_text(summary)
            self._overall_progress.set_fraction(overall_pct / 100.0)
            self._overall_progress.set_text(f"{overall_pct:.1f}%")
            self._overall_progress.set_show_text(True)

        # Rebuild list
        while True:
            row = self._list_box.get_row_at_index(0)
            if row is None:
                break
            self._list_box.remove(row)

        for pkg in filtered:
            row = PackageRow(pkg)
            self._list_box.append(row)


class TranslationApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self):
        win = self.get_active_window()
        if not win:
            win = MainWindow(application=self)
        win.present()


def main():
    app = TranslationApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
