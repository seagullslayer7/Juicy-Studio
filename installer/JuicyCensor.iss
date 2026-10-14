#ifndef ProductVersion
  #define ProductVersion "1.0.0"
#endif
#ifndef PayloadDir
  #error PayloadDir must point to the staged application folder
#endif
#ifndef ReleaseDir
  #define ReleaseDir "..\release"
#endif
[Setup]
AppId={{951EC758-EB93-4B21-A632-63C410883F01}
AppName=Juicy Studio
AppVersion={#ProductVersion}
AppPublisher=Juicy Studio
AppPublisherURL=https://github.com/seagullslayer7/JuicyCensor
AppSupportURL=https://github.com/seagullslayer7/JuicyCensor/issues
AppUpdatesURL=https://github.com/seagullslayer7/JuicyCensor/releases
DefaultDirName={localappdata}\Programs\JuicyStudio
DefaultGroupName=Juicy Studio
UsePreviousGroup=no
DisableDirPage=no
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#ReleaseDir}
OutputBaseFilename=JuicyStudio-{#ProductVersion}-Windows-x64-Setup
SetupIconFile=..\assets\orange.ico
UninstallDisplayIcon={app}\JuicyStudio.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
Uninstallable=not PortableMode
CreateUninstallRegKey=not PortableMode

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked; Check: not PortableMode

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.json,banned_words.txt,banned_phrases.txt,logs\*,cache\*,runtime.local.json,appearance.json"
Source: "{#PayloadDir}\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#PayloadDir}\banned_words.txt"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall
Source: "{#PayloadDir}\banned_phrases.txt"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall

[InstallDelete]
Type: files; Name: "{autodesktop}\Juicy Studio Preview.lnk"
Type: files; Name: "{userprograms}\Juicy Studio Preview\Juicy Studio Preview.lnk"

[Icons]
Name: "{group}\Juicy Studio"; Filename: "{app}\JuicyStudio.exe"; WorkingDir: "{app}"; Check: not PortableMode
Name: "{autodesktop}\Juicy Studio"; Filename: "{app}\JuicyStudio.exe"; WorkingDir: "{app}"; Tasks: desktopicon; Check: not PortableMode

[Run]
Filename: "{app}\JuicyStudio.exe"; Description: "Launch Juicy Studio and set up its processing runtime"; Flags: nowait postinstall skipifsilent

[Code]
function PortableMode: Boolean;
begin
  Result := ExpandConstant('{param:PORTABLE|0}') = '1';
end;

function InitializeUninstall: Boolean;
begin
  Result := True;
  if ExpandConstant('{param:PURGEDATA|0}') = '1' then
    Result := MsgBox('Remove ALL Juicy Studio data stored in this installation folder, including downloaded models, settings, saved projects and exported videos? Files outside this folder are preserved. Save anything you want to keep elsewhere before continuing.', mbConfirmation, MB_YESNO) = IDYES;
end;

procedure RemoveOwnedTree(Path: String);
var
  Item: TFindRec;
begin
  { Never traverse a junction, symbolic link or other reparse point. }
  if FindFirst(Path, Item) then begin
    FindClose(Item);
    if (Item.Attributes and $400) <> 0 then Exit;
  end else Exit;
  if DirExists(Path) then begin
    if FindFirst(Path + '\*', Item) then begin
      repeat
        if (Item.Name <> '.') and (Item.Name <> '..') then
          RemoveOwnedTree(Path + '\' + Item.Name);
      until not FindNext(Item);
      FindClose(Item);
    end;
    if not RemoveDir(Path) then Log('Preserved non-empty or locked directory: ' + Path);
  end else if not DeleteFile(Path) then Log('Could not remove: ' + Path);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Root: String;
  Item: TFindRec;
begin
  if (CurUninstallStep <> usPostUninstall) or (ExpandConstant('{param:PURGEDATA|0}') <> '1') then Exit;
  Root := ExpandConstant('{app}');
  if FindFirst(Root, Item) then begin
    FindClose(Item);
    if (Item.Attributes and $400) <> 0 then begin
      MsgBox('Additional data was preserved because the installation folder is a linked directory.', mbInformation, MB_OK);
      Exit;
    end;
  end else Exit;
  { Only explicitly owned children, never the entire installation folder. }
  RemoveOwnedTree(Root + '\cache');
  RemoveOwnedTree(Root + '\logs');
  RemoveOwnedTree(Root + '\models');
  RemoveOwnedTree(Root + '\runtime');
  RemoveOwnedTree(Root + '\venv');
  RemoveOwnedTree(Root + '\tools');
  RemoveOwnedTree(Root + '\projects');
  RemoveOwnedTree(Root + '\outputs');
  RemoveOwnedTree(Root + '\config.json');
  RemoveOwnedTree(Root + '\appearance.json');
  RemoveOwnedTree(Root + '\runtime.local.json');
  RemoveOwnedTree(Root + '\banned_words.txt');
  RemoveOwnedTree(Root + '\banned_phrases.txt');
end;
