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

The PyPI wheel includes the compiled gettext catalogs, including Swedish. The
default package language follows the desktop locale preferences (`LANGUAGE`,
`LC_ALL`, `LC_MESSAGES` or `LANG`) when that language is supported; Swedish is
used as the fallback.



### Debian/Ubuntu

For the latest release, download the `ubuntu-l10n_*_all.deb` package from
[GitHub Releases](https://github.com/yeager/ubuntu-l10n/releases/latest) and
install the downloaded package:

```bash
sudo apt install ./ubuntu-l10n_*_all.deb
```

The Danne L10n Suite APT repository also provides Ubuntu L10n, though its index
may lag behind the latest GitHub release. To enable it:

The repository key's primary fingerprint is
`7CEE83C9C621B18667DD1BFECAED4975DAB053A8`. After downloading the key, check
it with `gpg --show-keys --with-fingerprint /tmp/yeager-repo-key.asc` before
installing it.

```bash
wget -qO /tmp/yeager-repo-key.asc https://yeager.github.io/debian-repo/yeager-repo-key.asc
sudo install -m 0644 /tmp/yeager-repo-key.asc /usr/share/keyrings/yeager-repo.asc
echo 'deb [signed-by=/usr/share/keyrings/yeager-repo.asc] https://yeager.github.io/debian-repo stable main' | sudo tee /etc/apt/sources.list.d/yeager.list
sudo apt update
apt-cache policy ubuntu-l10n
sudo apt install ubuntu-l10n
```

The Debian package includes AppStream metadata with English and Swedish
descriptions for GNOME Software.

### Fedora/RPM

An RPM package for Ubuntu L10n is not currently published. On Fedora, use the
[PyPI installation](#installation-from-pypi) after installing GTK4, libadwaita
and PyGObject from Fedora's package manager.

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
The app remembers the selected Ubuntu release and statistics language locally.
On first launch, it chooses the system language when a translation is available.

## Author

Daniel Nylander — [danielnylander.se](https://danielnylander.se)
