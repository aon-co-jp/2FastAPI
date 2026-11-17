; Inno Setup script: 2FastAPI-Setup-<arch>.exe  (iscc /DArch=x64 /DExeDir=dist installer\2fastapi.iss)
#ifndef Arch
#define Arch "x64"
#endif
#ifndef ExeDir
#define ExeDir "..\dist"
#endif
[Setup]
AppName=2FastAPI
AppVersion=0.5.1
AppPublisher=aon-co-jp
DefaultDirName={autopf}\2FastAPI
DefaultGroupName=2FastAPI
OutputBaseFilename=2FastAPI-Setup-{#Arch}
OutputDir=Output
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\2fastapi.ico
#if Arch == "arm64"
ArchitecturesAllowed=arm64
ArchitecturesInstallIn64BitMode=arm64
#else
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif
[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"
[Files]
Source: "{#ExeDir}\2FastAPI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\src\tofastapi\2fastapi.ico"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autodesktop}\2FastAPI"; Filename: "{app}\2FastAPI.exe"; IconFilename: "{app}\2fastapi.ico"
Name: "{autodesktop}\2FastAPI (Web)"; Filename: "{app}\2FastAPI.exe"; Parameters: "web"; IconFilename: "{app}\2fastapi.ico"
Name: "{group}\2FastAPI"; Filename: "{app}\2FastAPI.exe"; IconFilename: "{app}\2fastapi.ico"
Name: "{group}\2FastAPI (Web)"; Filename: "{app}\2FastAPI.exe"; Parameters: "web"; IconFilename: "{app}\2fastapi.ico"
[Tasks]
Name: "oew"; Description: "Install open-easy-web too if it is missing (recommended) / open-easy-web が未導入なら一緒に導入(推奨)"
[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""iwr https://raw.githubusercontent.com/aon-co-jp/2FastAPI/main/install/install-windows.ps1 -OutFile $env:TEMP\i2f.ps1; & $env:TEMP\i2f.ps1 -OewOnly"""; Tasks: oew; Flags: runhidden
Filename: "{app}\2FastAPI.exe"; Description: "Launch 2FastAPI"; Flags: postinstall nowait skipifsilent
