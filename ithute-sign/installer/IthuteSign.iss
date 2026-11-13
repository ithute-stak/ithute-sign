#define AppName "IthuteSign"
#define AppVersion "0.28.0"
[Setup]
AppId={{D3CA15ED-BB9A-4FAB-BC95-202611100201}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\IthuteSign
DefaultGroupName=IthuteSign
OutputDir=..\dist\installer
OutputBaseFilename=IthuteSign-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
[Files]
Source: "..\dist\IthuteSign\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
[Icons]
Name: "{group}\IthuteSign"; Filename: "{app}\IthuteSign.exe"
Name: "{autodesktop}\IthuteSign"; Filename: "{app}\IthuteSign.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"
[Run]
Filename: "{app}\IthuteSign.exe"; Description: "Launch IthuteSign"; Flags: nowait postinstall skipifsilent
