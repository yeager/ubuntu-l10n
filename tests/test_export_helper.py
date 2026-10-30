import unittest

from ubuntu_l10n.export_helper import csv_safe_value


class CsvExportSafetyTests(unittest.TestCase):
    def test_text_that_could_be_a_spreadsheet_formula_is_prefixed(self):
        for value in ("=1+1", "+SUM(A1:A2)", "-1+2", "@SUM(A1:A2)", " \t=1+1"):
            with self.subTest(value=value):
                self.assertEqual(csv_safe_value(value), "'" + value)

    def test_values_that_are_not_formulas_are_unchanged(self):
        for value in ("Ubuntu Core", "  package", "1.2.3", "https://example.invalid"):
            with self.subTest(value=value):
                self.assertEqual(csv_safe_value(value), value)

    def test_non_text_values_keep_their_types(self):
        self.assertEqual(csv_safe_value(100), 100)
        self.assertEqual(csv_safe_value(0.5), 0.5)
