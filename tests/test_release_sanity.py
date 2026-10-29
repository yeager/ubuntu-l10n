import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT))
from ubuntu_l10n.scraper import DISTRO_VERSIONS, EOL_DISTROS

class ReleaseSanityTests(unittest.TestCase):
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

    def test_release_list_includes_current_lts_and_marks_interim_eol(self):
        self.assertEqual(DISTRO_VERSIONS["stonking"], "26.10")
        self.assertEqual(DISTRO_VERSIONS["jammy"], "22.04 LTS")
        self.assertTrue(EOL_DISTROS <= DISTRO_VERSIONS.keys())
        self.assertEqual(EOL_DISTROS, {"questing", "plucky", "oracular"})

if __name__ == "__main__":
    unittest.main()
