# Changelog

## 0.3.9 — 2026-10-30

- Add AppStream metadata for GNOME Software integration
- Provide English and Swedish app descriptions to software catalogs

## 0.3.8 — 2026-10-29

- Include compiled translations in PyPI and Debian source builds
- Improve accessibility controls and keyboard navigation
- Keep cached translation data available when offline and handle malformed cache entries safely
- Retry transient Launchpad errors and fetch every results page
- Add automated tests for accessibility, caching, and Launchpad scraping

## 0.2.5 — 2026-02-15

- Remove misplaced PacketLens keywords from Swedish translation backup
- Verify English source strings use "A-Z" (not "A-Ö") for sort labels
- Regenerate .pot file

## 0.2.4

- Add CSV/JSON export
- Add translatable man page via po4a
- CI: add po4a man page translation build
