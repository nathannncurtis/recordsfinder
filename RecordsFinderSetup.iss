; Inno Setup script for Records Finder

#define MyAppName "Records Finder"
#define MyAppVersion "2.0"
#define MyAppPublisher "Nathan Curtis"
#define MyAppURL "https://github.com/nathannncurtis/recordsfinder"
#define MyAppExeName "Records Finder.exe"

[Setup]
AppId={{A3E8B92D-7F14-4C61-9D3A-8E5F12B67C40}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userappdata}\{#MyAppName}
DisableDirPage=yes
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
Compression=lzma
SolidCompression=yes
OutputBaseFilename=RecordsFinderSetup
WizardStyle=dynamic
SignTool=MySignTool
SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "C:\Users\ncurtis\Documents\PROJECTS\!Completed Programs\Record Finders\dist\Records Finder\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\ncurtis\Documents\PROJECTS\!Completed Programs\Record Finders\dist\Records Finder\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\reg.exe"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\unreg.exe"; Flags: runhidden
