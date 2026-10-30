import re
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT))
from ubuntu_l10n.scraper import DISTRO_VERSIONS, EOL_DISTROS

class ReleaseSanityTests(unittest.TestCase):
    def test_apt_repository_instructions_include_the_primary_key_fingerprint_check(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("A387E4E726298FDA9599A4ACA689083BF25B5D38", readme)
        self.assertIn(
            "gpg --show-keys --with-fingerprint /tmp/yeager-repo-key.asc", readme,
        )
        self.assertIn("https://yeager.github.io/debian-repo stable main", readme)

    def test_python_sources_do_not_call_locale_bindtextdomain(self):
        for path in ROOT.rglob("*.py"):
            if ".git" in path.parts or "build" in path.parts or "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("locale." + "bindtextdomain(", source, str(path))

    def test_project_and_package_versions_match(self):
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        metadata_version = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)', project)
        package_init = ROOT / "ubuntu_l10n" / "__init__.py"
        source_version = re.search(r'__version__\s*=\s*["\']([^"\']+)', package_init.read_text(encoding="utf-8"))
        self.assertIsNotNone(metadata_version)
        self.assertIsNotNone(source_version)
        self.assertEqual(metadata_version.group(1), source_version.group(1))

    def test_configured_selection_helpers_are_in_all_packaging_checks(self):
        test_workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
        publish_workflow = (ROOT / ".github/workflows/pypi-publish.yml").read_text(encoding="utf-8")
        for package_path in (
            "ubuntu_l10n/system_language.py",
            "ubuntu_l10n/selection_state.py",
        ):
            self.assertIn(package_path, test_workflow)
            self.assertIn(package_path, publish_workflow)

    def test_pypi_publish_is_restricted_to_version_tags(self):
        workflow = (ROOT / ".github/workflows/pypi-publish.yml").read_text(encoding="utf-8")
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", workflow)
        self.assertIn("ref: ${{ github.ref }}", workflow)
        self.assertIn('RELEASE_TAG: ${{ github.ref_name }}', workflow)
        self.assertIn('assert tag_version == project_version', workflow)

    def test_debian_and_release_builds_check_swedish_catalogue_against_pot(self):
        for workflow_path in (
            ".github/workflows/tests.yml",
            ".github/workflows/release.yml",
        ):
            workflow = (ROOT / workflow_path).read_text(encoding="utf-8")
            self.assertIn("msgcmp po/sv.po po/ubuntu-l10n.pot", workflow)

    def test_appstream_metadata_matches_app_id_and_release(self):
        metainfo = ET.parse(ROOT / "data" / "se.danielnylander.ubuntu-l10n.metainfo.xml").getroot()
        self.assertEqual(metainfo.findtext("id"), "se.danielnylander.ubuntu-l10n")
        project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        version = re.search(r'(?m)^version\s*=\s*["\']([^"\']+)', project).group(1)
        self.assertEqual(metainfo.find("releases/release").get("version"), version)
        self.assertEqual(
            metainfo.findtext("launchable"),
            "se.danielnylander.ubuntu-l10n.desktop",
        )
        xml_lang = "{http://www.w3.org/XML/1998/namespace}lang"
        self.assertIn(
            "Visa översättningsstatus för Ubuntu och Launchpad",
            [summary.text for summary in metainfo.findall("summary")
             if summary.get(xml_lang) == "sv"],
        )
        self.assertTrue(any(
            paragraph.get(xml_lang) == "sv"
            for paragraph in metainfo.findall("description/p")
        ))

    def test_debian_package_installs_the_launcher_and_icon(self):
        install_rules = (ROOT / "debian/ubuntu-l10n.install").read_text(encoding="utf-8")
        self.assertIn(
            "se.danielnylander.ubuntu-l10n.desktop usr/share/applications",
            install_rules,
        )
        self.assertIn(
            "data/icons/ubuntu-l10n.svg usr/share/icons/hicolor/scalable/apps",
            install_rules,
        )
        build_rules = (ROOT / "debian/rules").read_text(encoding="utf-8")
        self.assertIn("desktop-merge.py se.danielnylander.ubuntu-l10n.desktop.in", build_rules)

    def test_release_list_includes_current_lts_and_marks_interim_eol(self):
        self.assertEqual(DISTRO_VERSIONS["stonking"], "26.10")
        self.assertEqual(DISTRO_VERSIONS["jammy"], "22.04 LTS")
        self.assertTrue(EOL_DISTROS <= DISTRO_VERSIONS.keys())
        self.assertEqual(EOL_DISTROS, {"questing", "plucky", "oracular"})

if __name__ == "__main__":
    unittest.main()
