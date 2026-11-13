# IthuteSign

Standalone, offline Windows document-signing application for Wacom STU-540.

## Goals

- Open PDF, DOC, or DOCX locally (Microsoft Word required for Word conversion)
- Preview pages and position one or more handwritten signatures
- Capture handwriting with the Wacom STU-540 through the official STU SDK
- Display an IthuteSign welcome screen, signing screen, and thank-you screen on the tablet
- Export a signed PDF while preserving the original document
- No IthuteSign account, subscription, activation key, or digital-certificate setup

## Development status

The current local source package is **v0.12**. Hardware operation and Windows installer compilation still require acceptance testing on a physical STU-540. Do **not** treat an embedded signature image as a cryptographic PDF signature.

Wacom drivers/SDK remain subject to their own vendor terms and are not distributed in this repository.

## Windows build prerequisites

Python 3.11+, Microsoft Word (for DOC/DOCX), Wacom STU SDK 2.19.1, Wacom STU driver, Windows C#/.NET build tools, and Inno Setup 6 for installer builds.

The application source will be imported into this repository on a development branch; this initialization alone does not constitute a tested Windows release.
