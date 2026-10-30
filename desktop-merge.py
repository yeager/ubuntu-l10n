#!/usr/bin/env python3
"""Merge .po translations into a .desktop.in template to produce a .desktop file."""
import ast
import glob
import os
import re
import sys
from pathlib import Path


def _po_string(line):
    value = ast.literal_eval(line)
    if not isinstance(value, str):
        raise ValueError(f"Expected a quoted PO string, got: {line}")
    return value


def _desktop_escape(value):
    """Escape decoded text for a Desktop Entry string value."""
    return (
        value.replace('\\', '\\\\')
        .replace('\n', '\\n')
        .replace('\t', '\\t')
        .replace('\r', '\\r')
    )


def parse_po(po_file):
    """Extract msgid→msgstr pairs from a .po file."""
    translations = {}
    msgid = msgstr = None
    active_field = None
    fuzzy = pending_fuzzy = False

    def save_entry():
        if msgid and msgstr and not fuzzy:
            translations[msgid] = msgstr

    with open(po_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#'):
                if msgid is not None and msgstr is not None:
                    save_entry()
                    msgid = msgstr = None
                    active_field = None
                    fuzzy = False
                if line.startswith('#,') and 'fuzzy' in {
                    flag.strip() for flag in line[2:].split(',')
                }:
                    pending_fuzzy = True
                continue
            if line.startswith('msgid '):
                if msgid is not None:
                    save_entry()
                msgid = _po_string(line[6:])
                msgstr = None
                active_field = 'msgid'
                fuzzy = pending_fuzzy
                pending_fuzzy = False
            elif line.startswith('msgstr '):
                msgstr = _po_string(line[7:])
                active_field = 'msgstr'
            elif line.startswith('"') and line.endswith('"'):
                value = _po_string(line)
                if active_field == 'msgid':
                    msgid = (msgid or '') + value
                elif active_field == 'msgstr':
                    msgstr = (msgstr or '') + value
            else:
                active_field = None
        save_entry()
    return translations

def merge(template, po_dir, output):
    """Read .desktop.in, merge translations, write .desktop."""
    lines = Path(template).read_text(encoding='utf-8').splitlines(keepends=True)
    
    # Collect all .po files
    po_files = sorted(glob.glob(os.path.join(po_dir, '*.po')))
    lang_translations = {}
    for po in po_files:
        lang = os.path.splitext(os.path.basename(po))[0]
        lang_translations[lang] = parse_po(po)
    
    with open(output, 'w', encoding='utf-8') as out:
        for line in lines:
            stripped = line.strip()
            # Check for translatable keys: _Name=, _Comment=, _Keywords=, _GenericName=
            m = re.match(r'^_(\w+)=(.*)$', stripped)
            if m:
                key, value = m.group(1), m.group(2)
                out.write(f'{key}={value}\n')
                # Add translations
                for lang in sorted(lang_translations.keys()):
                    trans = lang_translations[lang].get(value, '')
                    if trans:
                        out.write(f'{key}[{lang}]={_desktop_escape(trans)}\n')
            else:
                out.write(line)

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(f'Usage: {sys.argv[0]} template.desktop.in po_dir output.desktop')
        sys.exit(1)
    merge(sys.argv[1], sys.argv[2], sys.argv[3])
