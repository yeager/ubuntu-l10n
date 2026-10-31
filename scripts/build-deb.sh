#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${1:?Usage: build-deb.sh OUTPUT_DIR VERSION}"
VERSION="${2:?Usage: build-deb.sh OUTPUT_DIR VERSION}"

cd "$ROOT_DIR"
PROJECT_VERSION="$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
if [[ "$VERSION" != "$PROJECT_VERSION" ]]; then
    printf 'Version mismatch: requested %s but pyproject.toml declares %s\n' \
        "$VERSION" "$PROJECT_VERSION" >&2
    exit 1
fi

python3 scripts/compile-translations.py
python3 desktop-merge.py se.danielnylander.ubuntu-l10n.desktop.in po/ \
    se.danielnylander.ubuntu-l10n.desktop

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
PACKAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$PACKAGE_DIR"' EXIT

mkdir -p \
    "$PACKAGE_DIR/usr/lib/python3/dist-packages/ubuntu_l10n" \
    "$PACKAGE_DIR/usr/bin" \
    "$PACKAGE_DIR/usr/share/applications" \
    "$PACKAGE_DIR/usr/share/metainfo" \
    "$PACKAGE_DIR/usr/share/icons/hicolor/scalable/apps" \
    "$PACKAGE_DIR/DEBIAN"

cp "$ROOT_DIR"/ubuntu_l10n/*.py "$PACKAGE_DIR/usr/lib/python3/dist-packages/ubuntu_l10n/"

for translation in "$ROOT_DIR"/locale/*/LC_MESSAGES/ubuntu-l10n.mo; do
    [[ -f "$translation" ]] || continue
    language="$(basename "$(dirname "$(dirname "$translation")")")"
    install_dir="$PACKAGE_DIR/usr/share/locale/$language/LC_MESSAGES"
    mkdir -p "$install_dir"
    cp "$translation" "$install_dir/"
done

cp "$ROOT_DIR/se.danielnylander.ubuntu-l10n.desktop" \
    "$PACKAGE_DIR/usr/share/applications/"
cp "$ROOT_DIR/data/se.danielnylander.ubuntu-l10n.metainfo.xml" \
    "$PACKAGE_DIR/usr/share/metainfo/"
cp "$ROOT_DIR/data/icons/ubuntu-l10n.svg" \
    "$PACKAGE_DIR/usr/share/icons/hicolor/scalable/apps/"

printf '#!/usr/bin/env python3\nfrom ubuntu_l10n.app import main\nmain()\n' \
    > "$PACKAGE_DIR/usr/bin/ubuntu-l10n"
chmod 0755 "$PACKAGE_DIR/usr/bin/ubuntu-l10n"

cat > "$PACKAGE_DIR/DEBIAN/control" <<EOF
Package: ubuntu-l10n
Version: ${VERSION}-1
Section: devel
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, python3-bs4, python3-requests, python3-lxml
Maintainer: Daniel Nylander <daniel@danielnylander.se>
Homepage: https://github.com/yeager/ubuntu-l10n
Description: Ubuntu/Launchpad translation statistics viewer
EOF

dpkg-deb --root-owner-group --build "$PACKAGE_DIR" \
    "$OUTPUT_DIR/ubuntu-l10n_${VERSION}-1_all.deb"
