# Windows acceptance checklist

**This branch is not a verified release.** The physical STU-540 and a Windows compiler are required to finish acceptance.

1. Install the official Wacom STU driver and SDK separately; the application has no license key, login, or activation.
2. Run the SDK installation and compile the C# bridge with its x86 .NET Framework 4.8 project, verifying Interop.wgssSTU.dll is available.
3. Connect the STU-540 and run the bridge device probe.
4. Send the custom 'Welcome to IthuteSign' image to the tablet; confirm that it is visible, remains displayed and fits the tablet.
5. Begin a signing session and check live strokes and Clear, Cancel, and OK.
6. Confirm that the Thank You screen appears only after a successful signature.
7. Open a multi-page PDF, place signatures on different pages, save and inspect the output PDF.
8. Open a DOCX with Microsoft Word and compare the converted PDF to the original.
9. Install with the Inno Setup installer and repeat tests after reboot.

No device-only feature should be called verified until steps 3-9 have been completed on Windows hardware. Do not store signing data in the repository.
