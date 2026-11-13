# IthuteSign v0.33 — full source with WinUI startup fix

This archive includes the complete v0.33 source folders (`ithutesign-winui-v029` and `ithute-sign`). It does not replace your installed working v0.28 application.

## Fixes
- Adds an explicit C# STA Main entry point for WinUI 3.
- Corrects the Application.Start callback: its parameter is `initializationParams`; `_ = new App()` is a discard assignment, not an assignment to the callback parameter. This addresses CS0029 in the previous patch.
- Declares `App.xaml` as `ApplicationDefinition` instead of `Page` in the project, while retaining the explicit entry point because `EnableDefaultApplicationDefinition` is disabled.
- Uses normal build verbosity to expose any independent XAML compiler errors.

## Windows instructions
1. Back up `C:\ithute-sign-moden` or extract this archive to a fresh folder.
2. Keep the archive's `ithutesign-winui-v029` folder intact.
3. Open Command Prompt in `C:\ithute-sign-moden\ithutesign-winui-v029`.
4. Run `dotnet clean IthuteSign.Modern\IthuteSign.Modern.csproj -c Release -p:Platform=x64`.
5. Run `build-modern.bat`.
6. If XAML compilation still fails, send the first diagnostic error preceding MSB3073.

Note: This package has been statically checked and Python tests run in the authoring environment; a Windows WinUI compilation cannot be performed here. The app still delegates signing to the existing tested v0.28 application.
