# Ubuntu L10n

Ubuntu/Launchpad translation statistics viewer.

Built with GTK4/Adwaita. Part of the [Danne L10n Suite](https://github.com/yeager/debian-repo).

## Installation

## Installation from PyPI

GTK4, libadwaita and PyGObject must be installed from your distribution (they
are native system libraries and are not installed by pip). On Debian/Ubuntu:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 pipx
pipx install --system-site-packages ubuntu-l10n
```

The PyPI wheel includes the compiled gettext catalogs, including Swedish, so
the installed app follows the desktop language when available.



### Debian/Ubuntu
```bash
sudo apt install ubuntu-l10n
```

### Fedora/RPM
```bash
sudo dnf install ubuntu-l10n
```

## License

GPL-3.0

## Accessibility shortcuts

Ubuntu L10n includes app-level text scaling and a stronger-contrast mode:

- `Ctrl` + `+` or `Ctrl` + `=` to enlarge text.
- `Ctrl` + `-` to reduce text.
- `Ctrl` + `0` to restore the default text size.
- `Ctrl` + `Shift` + `H` to toggle the high-contrast styling.
- `Ctrl` + `F` to focus package search.

These shortcuts affect the current app window. Use Ubuntu's Accessibility
settings for system-wide changes.

Icon-only toolbar buttons have screen-reader names. The Release, Language and
Sort labels provide keyboard mnemonics that move focus to their selectors.

Translation results are cached locally for an hour. If a cached result is
older, Ubuntu L10n shows it while trying Launchpad again. If that request
fails, the saved result stays visible and the app explains how to retry.

## Author

Daniel Nylander — [danielnylander.se](https://danielnylander.se)
