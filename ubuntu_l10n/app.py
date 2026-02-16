"""Ubuntu Translation Statistics - GTK4/Libadwaita app."""

import csv
import datetime as _dt_now
import gettext
import json
import locale
import os
import sys
import threading
import webbrowser

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
# Optional desktop notifications
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify as _Notify
    HAS_NOTIFY = True
except (ValueError, ImportError):
    HAS_NOTIFY = False
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

VERSION = "0.1.1"


def _setup_heatmap_css():
    css = b"""
    .heatmap-green { background-color: #26a269; color: white; border-radius: 8px; }
    .heatmap-yellow { background-color: #e5a50a; color: white; border-radius: 8px; }
    .heatmap-orange { background-color: #ff7800; color: white; border-radius: 8px; }
    .heatmap-red { background-color: #c01c28; color: white; border-radius: 8px; }
    .heatmap-gray { background-color: #77767b; color: white; border-radius: 8px; }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def _heatmap_css_class(pct):
    if pct >= 100: return "heatmap-green"
    elif pct >= 75: return "heatmap-yellow"
    elif pct >= 50: return "heatmap-orange"
    elif pct > 0: return "heatmap-red"
    return "heatmap-gray"
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



import json as _json
import platform as _platform
from pathlib import Path as _Path

_NOTIFY_APP = "ubuntu-l10n"


def _notify_config_path():
    return _Path(GLib.get_user_config_dir()) / _NOTIFY_APP / "notifications.json"


def _load_notify_config():
    try:
        return _json.loads(_notify_config_path().read_text())
    except Exception:
        return {"enabled": True}


def _save_notify_config(config):
    p = _notify_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(config))


def _send_notification(summary, body="", icon="dialog-information"):
    if HAS_NOTIFY and _load_notify_config().get("enabled"):
        try:
            n = _Notify.Notification.new(summary, body, icon)
            n.show()
        except Exception:
            pass


def _get_system_info():
    return "\n".join([
        f"App: Ubuntu L10n",
        f"Version: {VERSION}",
        f"GTK: {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        f"Adw: {Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}",
        f"Python: {_platform.python_version()}",
        f"OS: {_platform.system()} {_platform.release()} ({_platform.machine()})",
    ])


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
        self._from_cache = False
        self._cache_age = 0
        self._heatmap_mode = False

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

        # Heatmap toggle
        self._heatmap_btn = Gtk.ToggleButton(icon_name="view-grid-symbolic")
        self._heatmap_btn.set_tooltip_text(_("Toggle heatmap view"))
        self._heatmap_btn.connect("toggled", self._on_heatmap_toggled)
        header.pack_start(self._heatmap_btn)

        # Menu button
        menu = Gio.Menu()
        menu.append(_("Settings"), "win.settings")
        menu.append(_("Notifications"), "win.toggle-notifications")
        menu.append(_("About"), "win.about")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        menu_btn.set_tooltip_text(_("Menu"))
        header.pack_end(menu_btn)

        # Theme toggle
        self._theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic",
                                     tooltip_text=_("Toggle dark/light theme"))
        self._theme_btn.connect("clicked", self._on_theme_toggle)
        # Export button
        export_btn = Gtk.Button(icon_name="document-save-symbolic",
                                tooltip_text=_("Export data"))
        export_btn.connect("clicked", self._on_export_clicked)
        header.pack_end(export_btn)

        header.pack_end(self._theme_btn)

        # Actions
        settings_action = Gio.SimpleAction(name="settings")
        settings_action.connect("activate", self._on_settings)
        self.add_action(settings_action)

        about_action = Gio.SimpleAction(name="about")
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        notif_action = Gio.SimpleAction(name="toggle-notifications")
        notif_action.connect("activate", lambda *_: _save_notify_config({"enabled": not _load_notify_config().get("enabled", False)}))
        self.add_action(notif_action)

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

        # Sort dropdown
        sort_model = Gtk.StringList()
        self._sort_options = [
            ("name_asc", _("Name (A-Z)")),
            ("most_translated", _("Most translated")),
            ("least_translated", _("Least translated")),
            ("most_strings", _("Most strings")),
            ("last_updated", _("Last updated")),
        ]
        for _key, label in self._sort_options:
            sort_model.append(label)
        sort_drop = Gtk.DropDown(model=sort_model)
        sort_drop.set_selected(0)
        sort_drop.connect("notify::selected", self._on_sort_changed)
        self._sort_drop = sort_drop

        sort_label = Gtk.Label(label=_("Sort:"))
        sort_label.add_css_class("dim-label")
        controls.append(sort_label)
        controls.append(sort_drop)

        # Statistics button
        stats_btn = Gtk.Button(icon_name="dialog-information-symbolic")
        stats_btn.set_tooltip_text(_("Language statistics"))
        stats_btn.connect("clicked", self._on_show_stats)
        controls.append(stats_btn)

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

        # Heatmap view
        heatmap_scroll = Gtk.ScrolledWindow(vexpand=True)
        self._heatmap_flow = Gtk.FlowBox()
        self._heatmap_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._heatmap_flow.set_homogeneous(True)
        self._heatmap_flow.set_min_children_per_line(3)
        self._heatmap_flow.set_max_children_per_line(8)
        self._heatmap_flow.set_column_spacing(4)
        self._heatmap_flow.set_row_spacing(4)
        self._heatmap_flow.set_margin_start(12)
        self._heatmap_flow.set_margin_end(12)
        self._heatmap_flow.set_margin_top(8)
        self._heatmap_flow.set_margin_bottom(12)
        heatmap_scroll.set_child(self._heatmap_flow)

        # Stack for loading/content
        self._stack = Gtk.Stack()
        self._stack.add_named(self._spinner_box, "loading")
        self._stack.add_named(scrolled, "content")
        self._stack.add_named(heatmap_scroll, "heatmap")
        # Status bar
        self._last_update_label = Gtk.Label(label="", halign=Gtk.Align.START,
                                            margin_start=12, margin_end=12, margin_bottom=4)
        self._last_update_label.add_css_class("dim-label")
        self._last_update_label.add_css_class("caption")
        content.append(self._last_update_label)
        content.append(self._stack)

        # Apply CSS
        self._apply_css()
        _setup_heatmap_css()

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

    def _on_theme_toggle(self, _btn):
        sm = Adw.StyleManager.get_default()
        if sm.get_color_scheme() == Adw.ColorScheme.FORCE_DARK:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            self._theme_btn.set_icon_name("weather-clear-night-symbolic")
        else:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self._theme_btn.set_icon_name("weather-clear-symbolic")

    def _update_last_updated(self):
        self._last_update_label.set_text("Last updated: " + _dt_now.now().strftime("%Y-%m-%d %H:%M"))

    def _on_export_clicked(self, *_args):
        dialog = Adw.MessageDialog(transient_for=self,
                                   heading=_("Export Data"),
                                   body=_("Choose export format:"))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("csv", "CSV")
        dialog.add_response("json", "JSON")
        dialog.set_response_appearance("csv", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_export_format_chosen)
        dialog.present()

    def _on_export_format_chosen(self, dialog, response):
        if response not in ("csv", "json"):
            return
        self._export_fmt = response
        fd = Gtk.FileDialog()
        fd.set_initial_name(f"ubuntu-l10n.{response}")
        fd.save(self, None, self._on_export_save)

    def _on_export_save(self, dialog, result):
        try:
            path = dialog.save_finish(result).get_path()
        except Exception:
            return
        data = [{"name": p.name, "translated_pct": p.translated_pct,
                 "untranslated": p.untranslated, "need_review": p.need_review,
                 "changed": p.changed, "total": p.total,
                 "last_edited": p.last_edited, "last_editor": p.last_editor}
                for p in self.packages]
        if not data:
            return
        if self._export_fmt == "csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=data[0].keys())
                w.writeheader()
                w.writerows(data)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def _on_refresh(self, _btn):
        self._load_data(force=True)

    def _on_distro_changed(self, _drop, _pspec):
        self._load_data()

    def _on_lang_changed(self, _drop, _pspec):
        self._load_data()

    def _on_search_changed(self, entry):
        self._filter_and_display()

    def _on_sort_changed(self, _drop, _pspec):
        self._filter_and_display()

    def _on_show_stats(self, _btn):
        """Show language-level statistics dialog."""
        if not self.packages:
            return

        pkgs = self.packages
        total_strings = sum(p.total for p in pkgs)
        total_translated = sum(p.translated for p in pkgs)
        overall_pct = (total_translated / total_strings * 100) if total_strings > 0 else 0
        fully_translated = sum(1 for p in pkgs if p.translated_pct >= 100)
        zero_pct = sum(1 for p in pkgs if p.translated_pct == 0)

        top_translated = sorted(pkgs, key=lambda p: p.translated_pct, reverse=True)[:10]
        least_translated = sorted(
            [p for p in pkgs if p.total > 0],
            key=lambda p: p.translated_pct)[:10]

        lines = []
        lines.append(_("<b>Overall:</b> {pct}% ({translated}/{total} strings)").format(
            pct=f"{overall_pct:.1f}",
            translated=f"{total_translated:,}",
            total=f"{total_strings:,}"))
        lines.append(_("<b>Packages:</b> {count} total, {fully} at 100%, {zero} at 0%").format(
            count=len(pkgs), fully=fully_translated, zero=zero_pct))
        lines.append("")
        lines.append(_("<b>Top 10 most translated:</b>"))
        for p in top_translated:
            lines.append(f"  {p.name}: {p.translated_pct:.1f}%")
        lines.append("")
        lines.append(_("<b>Top 10 least translated:</b>"))
        for p in least_translated:
            lines.append(f"  {p.name}: {p.translated_pct:.1f}%")

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Language Statistics"),
            body="\n".join(lines),
        )
        dialog.set_body_use_markup(True)
        dialog.add_response("close", _("Close"))
        dialog.present()

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
        about = Adw.AboutDialog(
            application_name=_("Ubuntu L10n"),
            application_icon="ubuntu-l10n",
            version=VERSION,
            developer_name="Daniel Nylander",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            copyright="© 2026 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/ubuntu-l10n",
            issue_url="https://github.com/yeager/ubuntu-l10n/issues",
            comments=_("View Ubuntu translation statistics from Launchpad"),
            translator_credits="Daniel Nylander <daniel@danielnylander.se>",
        )
        about.set_debug_info(_get_system_info())
        about.set_debug_info_filename("ubuntu-l10n-debug.txt")
        about.present(self)

    def _load_data(self, force=False):
        self._spinner.start()
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

    def _on_heatmap_toggled(self, btn):
        self._heatmap_mode = btn.get_active()
        if self.packages:
            self._filter_and_display()

    def _on_data_loaded(self, packages: list[PackageStats],
                        from_cache: bool = False, age_minutes: int = 0):
        self._spinner.stop()
        self._update_last_updated()
        self.packages = packages
        self._from_cache = from_cache
        self._cache_age = age_minutes
        # Notify about low translations
        low = [p.name for p in packages if 0 < p.translated_pct < 50]
        if low:
            _send_notification(
                _("Ubuntu L10n: Low translations"),
                _("{count} packages below 50%: {names}").format(
                    count=len(low), names=", ".join(low[:5])),
                "ubuntu-l10n")
        self._filter_and_display()
        if self._heatmap_mode:
            self._stack.set_visible_child_name("heatmap")
        else:
            self._stack.set_visible_child_name("content")

    def _on_data_error(self, error: str):
        self._spinner.stop()
        self._loading_label.set_text(_("Error: {error}").format(error=error))

    def _filter_and_display(self):
        query = self._search.get_text().lower().strip()

        filtered = self.packages
        if query:
            filtered = [p for p in filtered if query in p.name.lower()]

        # Sort based on dropdown selection
        sort_key = self._sort_options[self._sort_drop.get_selected()][0]
        if sort_key == "name_asc":
            filtered.sort(key=lambda p: p.name.lower())
        elif sort_key == "most_translated":
            filtered.sort(key=lambda p: p.translated_pct, reverse=True)
        elif sort_key == "least_translated":
            filtered.sort(key=lambda p: p.translated_pct)
        elif sort_key == "most_strings":
            filtered.sort(key=lambda p: p.total, reverse=True)
        elif sort_key == "last_updated":
            filtered.sort(key=lambda p: p.last_edited or "", reverse=True)
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

        # Rebuild heatmap
        while True:
            child = self._heatmap_flow.get_first_child()
            if child is None:
                break
            self._heatmap_flow.remove(child)
        for pkg in filtered:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_size_request(140, 64)
            box.add_css_class(_heatmap_css_class(pkg.translated_pct))
            box.set_margin_start(4)
            box.set_margin_end(4)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            lbl = Gtk.Label(label=pkg.name)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_max_width_chars(18)
            lbl.set_margin_top(6)
            lbl.set_margin_start(6)
            lbl.set_margin_end(6)
            box.append(lbl)
            pct_lbl = Gtk.Label(label=f"{pkg.translated_pct:.0f}%")
            pct_lbl.set_margin_bottom(6)
            box.append(pct_lbl)
            box.set_tooltip_text(f"{pkg.name}: {pkg.translated}/{pkg.total}")
            gesture = Gtk.GestureClick()
            gesture.connect("released", lambda g, n, x, y, url=pkg.translate_url: webbrowser.open(url))
            box.add_controller(gesture)
            box.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            self._heatmap_flow.append(box)

        if self._heatmap_mode:
            self._stack.set_visible_child_name("heatmap")
        else:
            self._stack.set_visible_child_name("content")


class TranslationApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        if HAS_NOTIFY:
            _Notify.init("ubuntu-l10n")

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.refresh", ["F5"])
        self.set_accels_for_action("app.shortcuts", ["<Control>slash"])
        self.set_accels_for_action("app.export", ["<Control>e"])
        for n, cb in [("quit", lambda *_: self.quit()),
                      ("refresh", lambda *_: self._do_refresh()),
                      ("shortcuts", self._show_shortcuts_window),
                      ("export", lambda *_: self.get_active_window() and self.get_active_window()._on_export_clicked())]:
            a = Gio.SimpleAction.new(n, None); a.connect("activate", cb); self.add_action(a)

    def _do_refresh(self):
        w = self.get_active_window()
        if w: w._on_refresh(None)

    def _show_shortcuts_window(self, *_args):
        win = Gtk.ShortcutsWindow(transient_for=self.get_active_window(), modal=True)
        section = Gtk.ShortcutsSection(visible=True, max_height=10)
        group = Gtk.ShortcutsGroup(visible=True, title="General")
        for accel, title in [("<Control>q", "Quit"), ("F5", "Refresh"), ("<Control>slash", "Keyboard shortcuts")]:
            s = Gtk.ShortcutsShortcut(visible=True, accelerator=accel, title=title)
            group.append(s)
        section.append(group)
        win.add_child(section)
        win.present()

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
