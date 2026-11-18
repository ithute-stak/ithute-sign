# IthuteSign Ubuntu acceptance test — signed documents and STU-540

This checklist is for a **physical Ubuntu workstation**. GitHub Actions uses Qt offscreen and cannot certify a real Wacom tablet, a desktop file manager, or an end-to-end LoanHub connection.

## Before starting

1. Check out the tested development branch and pull the latest changes. Do not run these tests against production LoanHub records.
2. Create a disposable sample PDF and use a test client National ID. Avoid real customer data in screenshots, logs or bug reports.
3. Start the app from its Python virtual environment. Record Ubuntu version, desktop environment (GNOME/KDE), Python version, and whether the STU-540 is connected.
4. Preserve the original PDF and any existing signed archive. Never overwrite an original for the purpose of testing.

## A. Explorer visual and navigation acceptance

- [ ] Open the full-screen Client Document Explorer.
- [ ] Verify folder sidebar, header, alternating rows, selected rows, and context menu are readable (no black blocks or dark-on-dark text).
- [ ] Search by client National ID and PDF filename; verify results.
- [ ] Open a client folder; navigate Back, Home and Up.
- [ ] Switch List and Tiles views; verify sorting and PDF preview.
- [ ] Copy text from the search box with Ctrl+C; it must not copy a PDF.

## B. Verified PDF export and clipboard

- [ ] Select a test signed PDF, choose Download, and save to a new destination. Confirm the exported PDF opens and is not the archive's own file path.
- [ ] Select the same PDF in List view and press Ctrl+C.
- [ ] Open Ubuntu Files (Nautilus), navigate to a separate test directory, press Ctrl+V.
- [ ] Verify a new PDF appears and opens. Compare its SHA-256 with the source exported PDF using `sha256sum`.
- [ ] Repeat copying from Tiles view and using the Copy PDF context-menu action.
- [ ] Attempt an export/copy of a deliberately tampered **test archive**; it must be refused without creating an output. Do not modify production archives.
- [ ] Close the application after pasting. Confirm the pasted destination file still exists and opens.

## C. Physical Wacom STU-540 signing

- [ ] Confirm the tablet is detected by the official Wacom SDK/bridge on this workstation.
- [ ] Open a disposable LoanHub-format PDF in IthuteSign.
- [ ] Start signature capture; verify tablet screen and pen input.
- [ ] Cancel capture and verify the original PDF remains unchanged.
- [ ] Capture again, place the signature on the intended page, and export a signed copy.
- [ ] Reopen the exported PDF and verify correct placement, no clipped signature, and preserved pages.
- [ ] Verify the document is archived under the **test client's** correct National ID.
- [ ] Confirm the archive hash check, PDF preview, Download, and Copy PDF work on the newly signed file.
- [ ] Disconnect/reconnect the tablet and verify the application reports a controlled error rather than corrupting the document.

## D. LoanHub integration (staging only)

- [ ] Open a test document from the approved LoanHub staging workflow.
- [ ] Verify document/client association before signing and after archival.
- [ ] Confirm no unintended write to production LoanHub or changes to its payment and calculator logic.
- [ ] Record any backend acknowledgement or status update separately; do not assume local PDF export proves server receipt.

## Evidence and release decision

Record date, OS/desktop, app commit SHA, Wacom SDK/bridge version, anonymized screenshots, test PDF SHA-256 values, and pass/fail for each section. Do not attach signatures, IDs, or customer documents to public GitHub issues.

**Merge gate:** all automated checks pass; A and B are confirmed on Ubuntu; C is confirmed on a physical STU-540; and D is confirmed against approved staging if LoanHub integration is included in the release. Until then, keep PR #69 in draft. A handwritten signature embedded as an image is **not** a cryptographic PDF signature.
