import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("desktop_merge", ROOT / "desktop-merge.py")
desktop_merge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(desktop_merge)


class DesktopMergeTests(unittest.TestCase):
    def test_decodes_escaped_quotes_and_multiline_translation(self):
        catalogue = '''
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

#: desktop entry
msgid "Open \\\"Ubuntu\\\" settings"
msgstr "Öppna inställningarna för \\\"Ubuntu\\\""
" på datorn"
'''
        with tempfile.TemporaryDirectory() as directory:
            po_file = Path(directory) / "sv.po"
            po_file.write_text(catalogue, encoding="utf-8")

            translations = desktop_merge.parse_po(po_file)

        self.assertEqual(
            translations['Open "Ubuntu" settings'],
            'Öppna inställningarna för "Ubuntu" på datorn',
        )

    def test_omits_fuzzy_translations(self):
        catalogue = '''
#, fuzzy
msgid "Network settings"
msgstr "Nätverksinställningar"

msgid "Sound settings"
msgstr "Ljudinställningar"
'''
        with tempfile.TemporaryDirectory() as directory:
            po_file = Path(directory) / "sv.po"
            po_file.write_text(catalogue, encoding="utf-8")

            translations = desktop_merge.parse_po(po_file)

        self.assertNotIn("Network settings", translations)
        self.assertEqual(translations["Sound settings"], "Ljudinställningar")

    def test_merge_writes_translations_without_corrupting_template_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            po_dir = root / "po"
            po_dir.mkdir()
            template = root / "app.desktop.in"
            template.write_text(
                "[Desktop Entry]\n_Name=Ubuntu L10n\n_Comment=Translation viewer\n",
                encoding="utf-8",
            )
            (po_dir / "sv.po").write_text(
                'msgid "Ubuntu L10n"\nmsgstr "Ubuntu L10n"\n\n'
                'msgid "Translation viewer"\n'
                'msgstr "Översättningsvisare\\nför skrivbordet"\n',
                encoding="utf-8",
            )
            output = root / "app.desktop"

            desktop_merge.merge(template, po_dir, output)

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "[Desktop Entry]\nName=Ubuntu L10n\nName[sv]=Ubuntu L10n\n"
                "Comment=Translation viewer\n"
                "Comment[sv]=Översättningsvisare\\nför skrivbordet\n",
            )

    def test_project_desktop_description_and_keywords_have_swedish_translations(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "se.danielnylander.ubuntu-l10n.desktop"

            desktop_merge.merge(
                ROOT / "se.danielnylander.ubuntu-l10n.desktop.in",
                ROOT / "po",
                output,
            )

            generated = output.read_text(encoding="utf-8")
        self.assertIn(
            "Comment[sv]=Visare för översättningsstatistik för Ubuntu och Launchpad",
            generated,
        )
        self.assertIn(
            "Keywords[sv]=översättning;lokalisering;ubuntu;launchpad;l10n;",
            generated,
        )


if __name__ == "__main__":
    unittest.main()
