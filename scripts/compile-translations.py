#!/usr/bin/env python3
"""Compile gettext catalogs for source, wheel and Debian package builds."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
CATALOGUE_DIR = ROOT / "po"
OUTPUT_DIRS = (ROOT / "locale", ROOT / "ubuntu_l10n" / "locale")


def compile_catalogues() -> None:
    for catalogue in sorted(CATALOGUE_DIR.glob("*.po")):
        language = catalogue.stem
        for output_dir in OUTPUT_DIRS:
            output = output_dir / language / "LC_MESSAGES" / "ubuntu-l10n.mo"
            output.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [
                    "msgfmt", "--check", "--check-format",
                    "-o", str(output), str(catalogue),
                ],
                check=True,
            )


if __name__ == "__main__":
    compile_catalogues()
