import unittest

from ubuntu_l10n.selection_state import preferred_index


class PreferredIndexTests(unittest.TestCase):
    def test_saved_value_wins_over_fallback(self):
        self.assertEqual(preferred_index(["stonking", "noble"], "noble", "stonking"), 1)

    def test_unsupported_saved_value_uses_fallback(self):
        self.assertEqual(preferred_index(["sv", "de"], "unsupported", "de"), 1)

    def test_missing_saved_value_and_fallback_uses_first_option(self):
        self.assertEqual(preferred_index(["stonking", "noble"], None), 0)

    def test_empty_options_returns_zero(self):
        self.assertEqual(preferred_index([], "sv", "de"), 0)


if __name__ == "__main__":
    unittest.main()
