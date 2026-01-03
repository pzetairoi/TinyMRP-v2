#define AppVersion "1.0.0"
#define BuildStamp GetDateTimeString('yyyymmdd_hhnnss', '', '')
#define OutputDirName "Windows Installer latest"
#define OutputDirPath AddBackslash(SourcePath) + OutputDirName

#if DirExists(OutputDirPath)
  #define FindHandle
  #define FindResult
  #define OutputMask AddBackslash(OutputDirPath) + "TinyMRP_SolidWorksAddin_*.exe"
  #sub DeleteOldInstallerOutput
    #define FoundFile FindGetFileName(FindHandle)
    #expr DeleteFileNow(AddBackslash(OutputDirPath) + FoundFile)
  #endsub
  #for {FindHandle = FindResult = FindFirst(OutputMask, 0); FindResult; FindResult = FindNext(FindHandle)} DeleteOldInstallerOutput
  #if FindHandle
    #expr FindClose(FindHandle)
  #endif
#endif

[Setup]
AppName=TinyMRP SolidWorks Add-in
AppVersion={#AppVersion}
OutputDir={#OutputDirName}
DefaultDirName={pf}\TinyMRP\SolidWorksAddin
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern
WizardImageFile=InstallerAssets\wizard.bmp
WizardSmallImageFile=InstallerAssets\wizard-small.bmp
SetupIconFile=InstallerAssets\setup.ico
OutputBaseFilename=TinyMRP_SolidWorksAddin_{#AppVersion}_{#BuildStamp}

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

function GetDefaultTemplatePath(const RelativePath: string): string;
begin
  Result := AddBackslash(WizardDirValue) + RelativePath;
end;

function MakeRelativeToApp(const Value: string): string;
var
  AppDir: string;
begin
  AppDir := AddBackslash(ExpandConstant('{app}'));
  if (Value <> '') and (CompareText(Copy(Value, 1, Length(AppDir)), AppDir) = 0) then
    Result := Copy(Value, Length(AppDir) + 1, MaxInt)
  else
    Result := Value;
end;

function DefaultOutputFolder: string;
begin
  Result := ExpandConstant('{userdocs}\TinyMRP\Output');
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

var
  OutputPage: TInputDirWizardPage;
  ConfigPage: TInputQueryWizardPage;
  DefaultBlankTemplate: string;
  DefaultBomTemplate: string;

procedure InitializeWizard();
begin
  OutputPage := CreateInputDirPage(wpSelectDir,
    'Export output folder', 'Select the output folder',
    'Choose the folder where export files will be stored.', False, '');
  OutputPage.Add('Output folder:');
  OutputPage.Values[0] := DefaultOutputFolder;

  ConfigPage := CreateInputQueryPage(OutputPage.ID,
    'TinyMRP configuration', 'Templates and server',
    'Set the default templates and web server address.');
  ConfigPage.Add('Blank template (.slddrt):', False);
  ConfigPage.Add('BOM template (.sldbomtbt):', False);
  ConfigPage.Add('Web server:', False);

  DefaultBlankTemplate := GetDefaultTemplatePath('Templates\TinyMRP_BLANKSHEET_TEMPLATE.slddrt');
  DefaultBomTemplate := GetDefaultTemplatePath('Templates\TinyMRP_BOM_TEMPLATE.sldbomtbt');
  ConfigPage.Values[0] := DefaultBlankTemplate;
  ConfigPage.Values[1] := DefaultBomTemplate;
  ConfigPage.Values[2] := 'localhost:5000';
end;

procedure CurPageChanged(CurPageID: Integer);
var
  NewBlank: string;
  NewBom: string;
begin
  if CurPageID = ConfigPage.ID then
  begin
    NewBlank := GetDefaultTemplatePath('Templates\TinyMRP_BLANKSHEET_TEMPLATE.slddrt');
    NewBom := GetDefaultTemplatePath('Templates\TinyMRP_BOM_TEMPLATE.sldbomtbt');

    if (ConfigPage.Values[0] = '') or (ConfigPage.Values[0] = DefaultBlankTemplate) then
      ConfigPage.Values[0] := NewBlank;
    if (ConfigPage.Values[1] = '') or (ConfigPage.Values[1] = DefaultBomTemplate) then
      ConfigPage.Values[1] := NewBom;

    DefaultBlankTemplate := NewBlank;
    DefaultBomTemplate := NewBom;
  end;
end;

procedure WriteConfigFile;
var
  ConfigPath: string;
  OutputFolder: string;
  BlankTemplate: string;
  BomTemplate: string;
  WebLink: string;
  Lines: string;
begin
  OutputFolder := OutputPage.Values[0];
  if OutputFolder = '' then
    OutputFolder := DefaultOutputFolder;

  ForceDirectories(OutputFolder);

  BlankTemplate := ConfigPage.Values[0];
  BomTemplate := ConfigPage.Values[1];
  WebLink := Trim(ConfigPage.Values[2]);
  if WebLink = '' then
    WebLink := 'localhost:5000';

  ConfigPath := ExpandConstant('{app}\TinyMRP_config.txt');
  Lines :=
    'BlankTemplatePath=' + MakeRelativeToApp(BlankTemplate) + #13#10 +
    'REMOVE_MODIFIED_NOTES=True' + #13#10 +
    'FILTER_ANY=*' + #13#10 +
    'BOMtemplate=' + MakeRelativeToApp(BomTemplate) + #13#10 +
    'weblink=' + WebLink + #13#10 +
    'BOM_Folder=' + MakeRelativeToApp(OutputFolder) + #13#10 +
    'deliverables_folder=' + MakeRelativeToApp(OutputFolder) + #13#10;

  SaveStringToFile(ConfigPath, Lines, False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    RegDeleteKeyIncludingSubkeys(HKLM, 'Software\SolidWorks\AddIns\{' + AddinGuid + '}');
    RegDeleteKeyIncludingSubkeys(HKLM, 'Software\SolidWorks\AddIns\{' + OldAddinGuid + '}');
    RegDeleteKeyIncludingSubkeys(HKCU, 'Software\SolidWorks\AddInsStartup\{' + OldAddinGuid + '}');
  end;

  if CurStep = ssPostInstall then
  begin
    WriteConfigFile;
  end;

  if CurStep = ssDone then
  begin
    if (not AddinsKeyExists) or (not ClsidKeyExists) then
      ShowRegistrationError;
  end;
end;
