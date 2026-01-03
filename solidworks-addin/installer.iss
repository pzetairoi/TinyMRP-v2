[Setup]
AppName=TinyMRP SolidWorks Add-in
AppVersion=1.0.0
DefaultDirName={pf}\TinyMRP\SolidWorksAddin
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

#define AddinGuid "D2A7E2A8-54D3-4E39-9E7B-3F35D0A7F3E6"
#define OldAddinGuid "3C0CB70A-FFDA-4CCB-8B9D-55EA0C2D6536"

[Files]
Source: "TinyMRP.SolidWorksAddin\bin\x64\Release\net48\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: filesandordirs; Name: "{app}\net48"

[Run]
Filename: "{win}\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"; Parameters: """{app}\TinyMRP.SolidWorksAddin.dll"" /codebase /tlb"; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{win}\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"; Parameters: """{app}\TinyMRP.SolidWorksAddin.dll"" /unregister"; Flags: runhidden waituntilterminated

[Code]
const
  AddinGuid = '{#AddinGuid}';
  OldAddinGuid = '{#OldAddinGuid}';

function AddinsKeyExists: Boolean;
begin
  Result := RegKeyExists(HKLM, 'Software\SolidWorks\AddIns\{' + AddinGuid + '}');
end;

function ClsidKeyExists: Boolean;
begin
  Result := RegKeyExists(HKCR, 'CLSID\{' + AddinGuid + '}');
end;

procedure ShowRegistrationError;
var
  RegAsmPath: string;
  DllPath: string;
  MessageText: string;
begin
  RegAsmPath := ExpandConstant('{win}\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe');
  DllPath := ExpandConstant('{app}\TinyMRP.SolidWorksAddin.dll');
  MessageText := 'No se pudo registrar el add-in.' + #13#10 +
    'Faltan claves de registro:' + #13#10;

  if not AddinsKeyExists then
    MessageText := MessageText + '- HKLM\Software\SolidWorks\AddIns\{' + AddinGuid + '}' + #13#10;
  if not ClsidKeyExists then
    MessageText := MessageText + '- HKCR\CLSID\{' + AddinGuid + '}' + #13#10;

  MessageText := MessageText + #13#10 +
    'Ejecuta este comando como administrador (PowerShell):' + #13#10 +
    '& "' + RegAsmPath + '" "' + DllPath + '" /codebase /tlb';

  MsgBox(MessageText, mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    RegDeleteKeyIncludingSubkeys(HKLM, 'Software\SolidWorks\AddIns\{' + AddinGuid + '}}');
    RegDeleteKeyIncludingSubkeys(HKLM, 'Software\SolidWorks\AddIns\{' + OldAddinGuid + '}');
    RegDeleteKeyIncludingSubkeys(HKCU, 'Software\SolidWorks\AddInsStartup\{' + OldAddinGuid + '}');
  end;

  if CurStep = ssDone then
  begin
    if (not AddinsKeyExists) or (not ClsidKeyExists) then
      ShowRegistrationError;
  end;
end;
