# Ubuntu L10n

A GTK4/Adwaita application for viewing Ubuntu translation statistics from Launchpad.

![Screenshot](data/screenshots/screenshot-01.png)

## Features

- Translation status per package (translated/untranslated/fuzzy)
- Color-coded progress bars (green/yellow/red)
- Language selector (defaults to system language)
- Distribution selector: Resolute (26.04), Questing, Plucky, Oracular, Noble, Focal
- Search/filter packages
- Sort by most/least translated
- Click any package to open its Launchpad translation page
- Overall progress bar with summary statistics

## Installation

### Debian/Ubuntu

```bash
# Add repository
curl -fsSL https://yeager.github.io/debian-repo/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/yeager-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/yeager-archive-keyring.gpg] https://yeager.github.io/debian-repo stable main" | sudo tee /etc/apt/sources.list.d/yeager.list
sudo apt update
sudo apt install ubuntu-l10n
```

### Fedora/RHEL

```bash
sudo dnf config-manager --add-repo https://yeager.github.io/rpm-repo/yeager.repo
sudo dnf install ubuntu-l10n
```

### From source

```bash
pip install .
ubuntu-l10n
```

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

## License

GPL-3.0-or-later — Daniel Nylander <daniel@danielnylander.se>
