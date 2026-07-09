; Inno Setup installer for EvalData (built artifacts from py2exe)

#define AppName "EvalData"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#define AppPublisher "EvalData"
#define BuildRoot "Dist\\EvalData"

[Setup]
AppId={{F2B55785-428A-4B51-9E59-E8048B790FD0}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Dist\Installer
OutputBaseFilename=EvalData-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\EvalData.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#BuildRoot}\\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\\{#AppName}"; Filename: "{app}\\EvalData.exe"

[Run]
Filename: "{app}\\EvalData.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
