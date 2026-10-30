import unittest

from ubuntu_l10n.system_language import get_system_language

LANGUAGES = {
    "sv": "Swedish", "da": "Danish", "nb": "Norwegian Bokmål",
    "nn": "Norwegian Nynorsk", "fi": "Finnish", "de": "German",
    "fr": "French", "es": "Spanish", "pt_BR": "Portuguese (Brazil)",
    "it": "Italian", "nl": "Dutch", "pl": "Polish", "ru": "Russian",
    "uk": "Ukrainian", "zh_CN": "Chinese (Simplified)",
    "zh_TW": "Chinese (Traditional)", "ja": "Japanese", "ko": "Korean",
    "ar": "Arabic", "cs": "Czech", "hu": "Hungarian", "ro": "Romanian",
    "tr": "Turkish", "el": "Greek", "he": "Hebrew", "id": "Indonesian",
    "ca": "Catalan", "gl": "Galician", "eu": "Basque", "pt": "Portuguese",
}


class SystemLanguageTests(unittest.TestCase):
    def test_uses_first_supported_gettext_language_preference(self):
        self.assertEqual(
            get_system_language(LANGUAGES, {"LANGUAGE": "zz:pt_BR.UTF-8:sv_SE"}),
            "pt_BR",
        )

    def test_locale_environment_precedence_is_respected(self):
        self.assertEqual(
            get_system_language(LANGUAGES, {
                "LC_ALL": "de_DE.UTF-8",
                "LC_MESSAGES": "fr_FR.UTF-8",
                "LANG": "sv_SE.UTF-8",
            }),
            "de",
        )

    def test_language_environment_variables_are_normalized(self):
        self.assertEqual(
            get_system_language(LANGUAGES, {"LANG": "pt-BR.UTF-8@latin"}),
            "pt_BR",
        )
        self.assertEqual(get_system_language(LANGUAGES, {"LANG": "sv_SE.UTF-8"}), "sv")

    def test_unsupported_or_c_locale_falls_through(self):
        self.assertEqual(
            get_system_language(LANGUAGES, {"LC_ALL": "C.UTF-8", "LANG": "fr_CA"}),
            "fr",
        )
        self.assertEqual(get_system_language(LANGUAGES, {"LANG": "C.UTF-8"}), "sv")

    def test_python_locale_is_last_fallback(self):
        self.assertEqual(get_system_language(LANGUAGES, {}, locale_name="fi_FI.UTF-8"), "fi")
        self.assertEqual(get_system_language(LANGUAGES, {}, locale_name=None), "sv")


if __name__ == "__main__":
    unittest.main()
