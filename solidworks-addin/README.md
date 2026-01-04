# TinyMRP SolidWorks Add-in

Task pane add-in for SolidWorks that handles TinyMRP publish/BOM exports, tools, and part numbering.

## Requirements

- SolidWorks installed (interop DLLs in `$(ProgramFiles)\SOLIDWORKS Corp\SOLIDWORKS\api\redist`)
- .NET Framework 4.8
- Inno Setup (optional, only if you build the installer)

## Build

```powershell
dotnet msbuild solidworks-addin\TinyMRP.SolidWorksAddin.sln /p:Configuration=Release /p:Platform=x64
```

Output DLL:

`solidworks-addin/TinyMRP.SolidWorksAddin/bin/x64/Release/net48/TinyMRP.SolidWorksAddin.dll`

## Register / Unregister (manual)

```powershell
# Register
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /codebase /tlb

# Unregister
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /unregister
```

## Configuration

- Primary config file: `TinyMRP_config.txt` next to the add-in DLL.
- If the install folder is not writable, the add-in saves to:
  `%LOCALAPPDATA%\TinyMRP\TinyMRP_config.txt`.
- Relative paths in the config are resolved from the add-in directory.

Key settings in `TinyMRP_config.txt`:

- `BlankTemplatePath`, `BOMtemplate` - template paths
- `deliverables_folder`, `BOM_Folder` - output folder (same path used for deliverables + BOM)
- `weblink` - base URL for the TinyMRP web UI
- `BackendUrl` - API base URL (defaults to `weblink`)
- `AuthToken` - optional bearer token for API calls
- `NumberingSchemeId` - default scheme to select
- `NumberingContextDefaults` - default context fields for numbering

## Task pane tabs

- Publish/BOM: export deliverables, run BOM, progress + cancel.
- Tools: freeze/unfreeze, normalize units, hide reference geometry.
- Numbering: scheme selection, segment builder, preview and allocate PN+REV.
- Configuration: templates, paths, server settings.

## Numbering workflow (quick)

1. Open the Numbering tab and click **Refresh** to load schemes.
2. Select an existing scheme or build one with presets and segments.
3. Validate and **Save scheme** (requires admin/manager or `numbering.manage`).
4. Enter context fields and click **Preview next**.
5. Click **Allocate PN+REV** and choose where to apply it.

The add-in writes custom properties:

- `PartNumber`
- `Revision`
- `DisplayCode`
- `TinyMRP_SchemeId` (optional)

## Permissions

- Managing schemes requires admin/manager or permission `numbering.manage`.
- Preview/allocate is available to authenticated users.
