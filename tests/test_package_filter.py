import unittest
from types import SimpleNamespace

from ubuntu_l10n.package_filter import filter_and_sort_packages


class PackageFilterTests(unittest.TestCase):
    def setUp(self):
        self.packages = [
            SimpleNamespace(name="Zulu", translated_pct=80.0, total=300, last_edited="2026-10-01"),
            SimpleNamespace(name="Straße", translated_pct=95.0, total=100, last_edited="2026-10-03"),
            SimpleNamespace(name="Alpha", translated_pct=80.0, total=200, last_edited="2026-10-02"),
        ]

    def test_sorting_returns_a_copy_and_preserves_source_order(self):
        result = filter_and_sort_packages(self.packages, sort_key="most_translated")

        self.assertEqual([package.name for package in result], ["Straße", "Zulu", "Alpha"])
        self.assertIsNot(result, self.packages)
        self.assertEqual(
            [package.name for package in self.packages], ["Zulu", "Straße", "Alpha"],
        )

    def test_search_uses_unicode_casefolding(self):
        result = filter_and_sort_packages(self.packages, "STRASSE")

        self.assertEqual([package.name for package in result], ["Straße"])

    def test_filtering_and_sorting_can_be_combined(self):
        result = filter_and_sort_packages(self.packages, "a", "last_updated")

        self.assertEqual([package.name for package in result], ["Straße", "Alpha"])


if __name__ == "__main__":
    unittest.main()
