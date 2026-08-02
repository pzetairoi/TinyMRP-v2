#define AppVersion "1.0.2"
#define BuildStamp GetDateTimeString('yyyymmdd_hhnnss', '', '')
#define OutputDirName "Windows Installer latest"
#define ConfigFileName "TinyMRP_config.txt"
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
DefaultDirName={commonpf}\TinyMRP\SolidWorksAddin
ArchitecturesInstallIn64BitMode=x64compatible
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
Filename: "{win}\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe"; Parameters: """{app}\TinyMRP.SolidWorksAddin.dll"" /unregister"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterAddin"

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

function GetMachineConfigPath: string;
begin
  Result := ExpandConstant('{commonappdata}\TinyMRP\{#ConfigFileName}');
end;

function GetUserConfigPath: string;
begin
  Result := ExpandConstant('{localappdata}\TinyMRP\{#ConfigFileName}');
end;

function FindExistingConfigPath(const InstallDir: string): string;
var
  InstallConfig: string;
begin
  if FileExists(GetMachineConfigPath) then
    Result := GetMachineConfigPath
  else
  begin
    if InstallDir <> '' then
    begin
      InstallConfig := AddBackslash(InstallDir) + '{#ConfigFileName}';
      if FileExists(InstallConfig) then
      begin
        Result := InstallConfig;
        Exit;
      end;
    end;
    if FileExists(GetUserConfigPath) then
      Result := GetUserConfigPath
    else
      Result := '';
  end;
end;

function ReadConfigValue(const Path, Key, DefaultValue: string): string;
var
  Lines: TArrayOfString;
  I, P: Integer;
  Line, K, V: string;
begin
  Result := DefaultValue;
  if (Path = '') or (not LoadStringsFromFile(Path, Lines)) then
    Exit;

  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    if (Line = '') or (Copy(Line, 1, 1) = '#') or (Copy(Line, 1, 1) = ';') then
      Continue;
    P := Pos('=', Line);
    if P <= 0 then
      Continue;
    K := Trim(Copy(Line, 1, P - 1));
    V := Trim(Copy(Line, P + 1, MaxInt));
    if CompareText(K, Key) = 0 then
    begin
      Result := V;
      Exit;
    end;
  end;
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
  OverrideSettingsCheck: TNewCheckBox;
  ClearTokenCheck: TNewCheckBox;
  ExistingConfigPath: string;
  ExistingConfigLoaded: Boolean;
  DefaultBlankTemplate: string;
  DefaultBomTemplate: string;
  HasParamOverride: Boolean;

procedure OverrideSettingsCheckClick(Sender: TObject); forward;

procedure InitializeWizard();
begin
  ExistingConfigPath := FindExistingConfigPath('');
  ExistingConfigLoaded := False;

  OutputPage := CreateInputDirPage(wpSelectDir,
    'Export output folder', 'Select the output folder',
    'Choose the folder where export files will be stored.', False, '');
  OutputPage.Add('Output folder:');
  OutputPage.Values[0] := ReadConfigValue(ExistingConfigPath, 'deliverables_folder', DefaultOutputFolder);

  ConfigPage := CreateInputQueryPage(OutputPage.ID,
    'TinyMRP configuration', 'Templates and server',
    'Set the default templates and server connection.');
  ConfigPage.Add('Blank template (.slddrt):', False);
  ConfigPage.Add('BOM template (.sldbomtbt):', False);
  ConfigPage.Add('Backend URL:', False);
  ConfigPage.Add('Auth token (optional):', True);

  DefaultBlankTemplate := GetDefaultTemplatePath('Templates\TinyMRP_BLANKSHEET_TEMPLATE.slddrt');
  DefaultBomTemplate := GetDefaultTemplatePath('Templates\TinyMRP_BOM_TEMPLATE.sldbomtbt');
  ConfigPage.Values[0] := ReadConfigValue(ExistingConfigPath, 'BlankTemplatePath', DefaultBlankTemplate);
  ConfigPage.Values[1] := ReadConfigValue(ExistingConfigPath, 'BOMtemplate', DefaultBomTemplate);
  ConfigPage.Values[2] := ReadConfigValue(ExistingConfigPath, 'BackendUrl', ReadConfigValue(ExistingConfigPath, 'weblink', 'http://localhost:5000'));
  ConfigPage.Values[3] := '';

  if ExpandConstant('{param:BACKENDURL|}') <> '' then
    ConfigPage.Values[2] := ExpandConstant('{param:BACKENDURL|}');
  if ExpandConstant('{param:AUTHTOKEN|}') <> '' then
    ConfigPage.Values[3] := ExpandConstant('{param:AUTHTOKEN|}');

  HasParamOverride := (ExpandConstant('{param:BACKENDURL|}') <> '') or (ExpandConstant('{param:AUTHTOKEN|}') <> '');
  OverrideSettingsCheck := TNewCheckBox.Create(ConfigPage);
  OverrideSettingsCheck.Parent := ConfigPage.Surface;
  OverrideSettingsCheck.Caption := 'Override existing TinyMRP settings';
  OverrideSettingsCheck.Checked := (ExistingConfigPath = '') or HasParamOverride;
  OverrideSettingsCheck.Left := 0;
  OverrideSettingsCheck.Top := ConfigPage.Edits[3].Top + ConfigPage.Edits[3].Height + ScaleY(8);
  OverrideSettingsCheck.Width := ConfigPage.SurfaceWidth;

  ClearTokenCheck := TNewCheckBox.Create(ConfigPage);
  ClearTokenCheck.Parent := ConfigPage.Surface;
  ClearTokenCheck.Caption := 'Clear existing auth token';
  ClearTokenCheck.Checked := False;
  ClearTokenCheck.Enabled := OverrideSettingsCheck.Checked;
  ClearTokenCheck.Left := 0;
  ClearTokenCheck.Top := OverrideSettingsCheck.Top + OverrideSettingsCheck.Height + ScaleY(4);
  ClearTokenCheck.Width := ConfigPage.SurfaceWidth;
  OverrideSettingsCheck.OnClick := @OverrideSettingsCheckClick;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  NewBlank: string;
  NewBom: string;
  NewExistingConfig: string;
begin
  if (CurPageID = OutputPage.ID) and (not ExistingConfigLoaded) then
  begin
    NewExistingConfig := FindExistingConfigPath(WizardDirValue);
    if (NewExistingConfig <> '') and (CompareText(NewExistingConfig, ExistingConfigPath) <> 0) then
    begin
      ExistingConfigPath := NewExistingConfig;
      OutputPage.Values[0] := ReadConfigValue(ExistingConfigPath, 'deliverables_folder', DefaultOutputFolder);
      ConfigPage.Values[0] := ReadConfigValue(ExistingConfigPath, 'BlankTemplatePath', DefaultBlankTemplate);
      ConfigPage.Values[1] := ReadConfigValue(ExistingConfigPath, 'BOMtemplate', DefaultBomTemplate);
      ConfigPage.Values[2] := ReadConfigValue(ExistingConfigPath, 'BackendUrl', ReadConfigValue(ExistingConfigPath, 'weblink', 'http://localhost:5000'));
      if (OverrideSettingsCheck <> nil) and (not HasParamOverride) then
      begin
        OverrideSettingsCheck.Checked := False;
        if ClearTokenCheck <> nil then
          ClearTokenCheck.Enabled := OverrideSettingsCheck.Checked;
      end;
    end;
    ExistingConfigLoaded := True;
  end;

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

procedure OverrideSettingsCheckClick(Sender: TObject);
begin
  if ClearTokenCheck <> nil then
    ClearTokenCheck.Enabled := OverrideSettingsCheck.Checked;
end;

procedure WriteConfigFile;
var
  ConfigPath: string;
  OutputFolder: string;
  BlankTemplate: string;
  BomTemplate: string;
  WebLink: string;
  BackendUrl: string;
  AuthToken: string;
  ExistingOutput: string;
  ExistingBlank: string;
  ExistingBom: string;
  ExistingWeb: string;
  ExistingBackend: string;
  ExistingToken: string;
  ExistingSchemeId: string;
  ExistingContextDefaults: string;
  ExistingAutoGeneric: string;
  ExistingAutoAny: string;
  ExistingMeshLimit: string;
  Lines: string;
begin
  ExistingOutput := ReadConfigValue(ExistingConfigPath, 'deliverables_folder', '');
  ExistingBlank := ReadConfigValue(ExistingConfigPath, 'BlankTemplatePath', '');
  ExistingBom := ReadConfigValue(ExistingConfigPath, 'BOMtemplate', '');
  ExistingWeb := ReadConfigValue(ExistingConfigPath, 'weblink', '');
  ExistingBackend := ReadConfigValue(ExistingConfigPath, 'BackendUrl', '');
  ExistingToken := ReadConfigValue(ExistingConfigPath, 'AuthToken', '');
  ExistingSchemeId := ReadConfigValue(ExistingConfigPath, 'NumberingSchemeId', '');
  ExistingContextDefaults := ReadConfigValue(ExistingConfigPath, 'NumberingContextDefaults', 'type=PART;family=;subfamily=;project=;site=');
  ExistingAutoGeneric := ReadConfigValue(ExistingConfigPath, 'AutoAssignGenericNames', 'True');
  ExistingAutoAny := ReadConfigValue(ExistingConfigPath, 'AutoAssignAnyNames', 'False');
  ExistingMeshLimit := ReadConfigValue(ExistingConfigPath, 'MeshExportSizeLimitMb', '50');

  if (ExistingConfigPath <> '') and (OverrideSettingsCheck <> nil) and (not OverrideSettingsCheck.Checked) then
  begin
    if (CompareText(ExistingConfigPath, GetMachineConfigPath) <> 0) and (not FileExists(GetMachineConfigPath)) then
    begin
      ForceDirectories(ExtractFileDir(GetMachineConfigPath));
      CopyFile(ExistingConfigPath, GetMachineConfigPath, False);
    end;
    Exit;
  end;

  OutputFolder := OutputPage.Values[0];
  if OutputFolder = '' then
    OutputFolder := ExistingOutput;
  if OutputFolder = '' then
    OutputFolder := DefaultOutputFolder;

  ForceDirectories(OutputFolder);

  BlankTemplate := ConfigPage.Values[0];
  if BlankTemplate = '' then
    BlankTemplate := ExistingBlank;
  if BlankTemplate = '' then
    BlankTemplate := DefaultBlankTemplate;
  BomTemplate := ConfigPage.Values[1];
  if BomTemplate = '' then
    BomTemplate := ExistingBom;
  if BomTemplate = '' then
    BomTemplate := DefaultBomTemplate;

  BackendUrl := Trim(ConfigPage.Values[2]);
  if BackendUrl = '' then
    BackendUrl := ExistingBackend;
  if BackendUrl = '' then
    BackendUrl := 'http://localhost:5000';

  AuthToken := Trim(ConfigPage.Values[3]);
  if (AuthToken = '') then
  begin
    if (ClearTokenCheck <> nil) and ClearTokenCheck.Checked then
      AuthToken := ''
    else
      AuthToken := ExistingToken;
  end;

  WebLink := BackendUrl;
  if WebLink = '' then
    WebLink := ExistingWeb;

  ConfigPath := GetMachineConfigPath;
  ForceDirectories(ExtractFileDir(ConfigPath));
  Lines :=
    'BlankTemplatePath=' + MakeRelativeToApp(BlankTemplate) + #13#10 +
    'REMOVE_MODIFIED_NOTES=True' + #13#10 +
    'FILTER_ANY=*' + #13#10 +
    'BOMtemplate=' + MakeRelativeToApp(BomTemplate) + #13#10 +
    'weblink=' + WebLink + #13#10 +
    'BackendUrl=' + BackendUrl + #13#10 +
    'AuthToken=' + AuthToken + #13#10 +
    'BOM_Folder=' + MakeRelativeToApp(OutputFolder) + #13#10 +
    'deliverables_folder=' + MakeRelativeToApp(OutputFolder) + #13#10 +
    'NumberingSchemeId=' + ExistingSchemeId + #13#10 +
    'NumberingContextDefaults=' + ExistingContextDefaults + #13#10 +
    'PartNumberProperty=PartNumber' + #13#10 +
    'RevisionProperty=Revision' + #13#10 +
    'DisplayCodeProperty=DisplayCode' + #13#10 +
    'NumberingApplyMode=active_config' + #13#10 +
    'AutoAssignGenericNames=' + ExistingAutoGeneric + #13#10 +
    'AutoAssignAnyNames=' + ExistingAutoAny + #13#10 +
    'MeshExportSizeLimitMb=' + ExistingMeshLimit + #13#10;

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
