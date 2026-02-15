# Ubuntu L10n — Translation Statistics Viewer

A GTK4/Libadwaita app that shows the current translation status for Ubuntu packages via Launchpad.

![screenshot](screenshot.png)

## Features

- 📊 Translation status per package (translated/untranslated/fuzzy)
- 🎨 Color-coded progress bars (green/yellow/red)
- 🌍 Language selector (defaults to system language)
- 📦 Distribution selector: Resolute (26.04), Questing, Plucky, Oracular, Noble, Focal
- 🔍 Search/filter packages
- ↕️ Sort by most/least translated
- 🔗 Click any package to open its Launchpad translation page
- 📈 Overall progress bar with summary statistics

## Requirements

- Python 3.10+
- GTK 4
- libadwaita
- PyGObject, beautifulsoup4, requests, lxml

### Ubuntu/Debian

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
    python3-bs4 python3-requests python3-lxml
```

### Fedora

```bash
sudo dnf install python3-gobject gtk4 libadwaita \
    python3-beautifulsoup4 python3-requests python3-lxml
```

### pip (for other dependencies)

```bash
pip install beautifulsoup4 requests lxml
```

## Usage

```bash
# Run directly
python -m ubuntu_l10n.app

# Or install and run
pip install -e .
ubuntu-l10n
```

## Data Sources

- **Launchpad**: `https://translations.launchpad.net/ubuntu/{release}/+lang/{lang}/+index`
- **Weblate**: `https://hosted.weblate.org/projects/ubuntu-desktop-translations/`

## License

GPL-3.0-or-later — Daniel Nylander <daniel@danielnylander.se>

## 🌍 Contributing Translations

Help translate this app into your language! All translations are managed via Transifex.

**→ [Translate on Transifex](https://app.transifex.com/danielnylander/ubuntu-l10n/)**

### How to contribute:
1. Visit the [Transifex project page](https://app.transifex.com/danielnylander/ubuntu-l10n/)
2. Create a free account (or log in)
3. Select your language and start translating

### Currently supported languages:
Arabic, Czech, Danish, German, Spanish, Finnish, French, Italian, Japanese, Korean, Norwegian Bokmål, Dutch, Polish, Brazilian Portuguese, Russian, Swedish, Ukrainian, Chinese (Simplified)

### Notes:
- Please do **not** submit pull requests with .po file changes — they are synced automatically from Transifex
- Source strings are pushed to Transifex daily via GitHub Actions
- Translations are pulled back and included in releases

New language? Open an [issue](https://github.com/yeager/ubuntu-l10n/issues) and we'll add it!