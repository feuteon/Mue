; Installeur Inno Setup pour Mue — compile avec : iscc installer.iss
; Installation par utilisateur (pas besoin des droits administrateur).

#define AppName "Mue"
#define AppVersion "1.0.0"

[Setup]
AppId={{6B2E4C1A-9D3F-4E7B-A51C-2F8D0E6B9C34}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Erweb.bzh
AppPublisherURL=https://erweb.bzh
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Mue-Setup-{#AppVersion}
SetupIconFile=assets\mue.ico
UninstallDisplayIcon={app}\Mue.exe
UninstallDisplayName={#AppName} — convertisseur local
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[Files]
Source: "dist\Mue\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; nettoie les fichiers d'une version précédente
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\Mue.exe"; Comment: "Réglages de Mue"

[Run]
Filename: "{app}\Mue.exe"; Parameters: "--install"; StatusMsg: "Ajout de « Convertir vers » au clic droit…"; Flags: runhidden waituntilterminated
Filename: "{app}\Mue.exe"; Description: "Ouvrir les réglages de Mue"; Flags: postinstall nowait skipifsilent unchecked

[UninstallRun]
Filename: "{app}\Mue.exe"; Parameters: "--uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "MueRemoveMenu"
