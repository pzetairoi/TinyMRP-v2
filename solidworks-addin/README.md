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

Release builds increment `TinyMRP.SolidWorksAddin/BuildNumber.txt` once and display that integer in the add-in title. Debug builds and tests reuse the current number without incrementing it.

## Register / Unregister (manual)

```powershell
# Register
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /codebase /tlb

# Unregister
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /unregister
```

## Installer

The Inno Setup script is `solidworks-addin/installer.iss`. It copies the build
output and runs RegAsm. Silent install, for IT deployment:

```powershell
TinyMRP_SolidWorksAddin_*.exe /VERYSILENT /SUPPRESSMSGBOXES /BACKENDURL="https://mrp.company.local" /AUTHTOKEN="tmrp_xxx"
```

Add-in and task pane icons are generated from
`TinyMRP.SolidWorksAddin/Assets/logo.png`.

End users installing a released build, rather than building one, should follow
[`docs/help/03_addin_installation.md`](../docs/help/03_addin_installation.md) —
the same text the application shows under Help.

## Configuration

- Primary config file: `%PROGRAMDATA%\TinyMRP\TinyMRP_config.txt`.
- Read order: ProgramData -> install folder -> `%LOCALAPPDATA%\TinyMRP\TinyMRP_config.txt`.
- If ProgramData is not writable, the add-in falls back to LocalAppData.
- Relative paths in the config are resolved from the add-in directory.

Key settings in `TinyMRP_config.txt`:

- `BlankTemplatePath`, `BOMtemplate` - template paths
- `deliverables_folder`, `BOM_Folder` - output folder (same path used for deliverables + BOM)
- `weblink` - base URL for the TinyMRP web UI
- `BackendUrl` - API base URL (defaults to `weblink`)
- `AuthToken` - TinyMRP API token for API calls
- `NumberingSchemeId` - default scheme to select
- `NumberingContextDefaults` - default context fields for numbering
- `PartNumberProperty`, `RevisionProperty`, `DisplayCodeProperty` - legacy property names used for read-only compatibility
- `AutoAssignGenericNames` - auto-assign for Part1/Assembly1 names (True|False)
- `AutoAssignAnyNames` - allow auto-assign for any name (dangerous)
- `MeshExportSizeLimitMb` - maximum generated PLY/STL/3MF size; oversized output is skipped (default `50`)

Backend URL rules:

- Correct: `https://company.example.com`
- Correct: `https://mrp.company.local` — an internal name is still HTTPS
- Correct only where the deployment really is plain HTTP, such as the Windows
  LAN path: `http://tinymrp-lan.company.local`
- Wrong: `company.example.com/api`
- Wrong: `https://company.example.com/api`
- Wrong: `https://company.example.com/api/numbering`

**Always write the scheme.** Without one the add-in has to guess, and it now
guesses `https://` for everything except genuine loopback (`localhost`,
`127.0.0.1`, `::1`, `*.localhost`). It previously guessed `http://` for
`.local`, `.localdomain`, `.test` and `.test.local` on the assumption that such
names are development machines — which put the API token on the wire in clear
text on internal production deployments. An explicit `http://` is still
honoured, so plain-HTTP LAN installs are unaffected.

## Task pane tabs

- Publish/BOM: export deliverables, run BOM, progress + cancel.
- Tools: freeze/unfreeze, normalize units, hide reference geometry.
- Numbering: scheme selection, last-used number, preview, and allocate to a filename.
- Configuration: Quick Start + Advanced settings, templates, paths, server settings.

## What Publish/BOM writes

- Deliverables are exported under `deliverables_folder`.
- BOM export writes `*_FLATBOM.txt` and `*_TREEBOM.txt`, then zips them into
  `BOM_Folder\bom`.
- Those text files are UTF-8 **without** a byte-order mark. The TinyMRP importer
  also tolerates UTF-8 with a BOM (`utf-8-sig`) for files produced by older
  builds.
- Publish/BOM includes "Manage associated files…" and an optional
  "Create Upload Pack (ZIP)" toggle.
- Child documents opened during export are closed again automatically; only the
  root document stays open.
- The Numbering tab previews and allocates `PartNumber` + `Revision` through
  `/api/numbering/*`.

## Numbering workflow (quick)

1. Open the Numbering tab and click **Refresh** to load schemes.
2. Select an existing scheme and review the last part number used.
3. Click **Preview Partnumber**.
4. Click **Allocate and save/rename**. Unsaved documents prompt for a folder; saved documents are renamed.

## Add-in Quick Start

1. Create an API token in the web UI (`/ui/addin/tokens`).
2. Open the Configuration tab -> **Quick Start**.
3. Paste Backend URL + Auth token, then **Test connection**.
4. Pick a preset scheme, enter minimal context, and **Save settings**.

Token notes:

- Use a TinyMRP API token, not the web password.
- Paste the raw token into the add-in when you create it. The raw token cannot be recovered later because only its hash is stored.
- If the instance was recreated, or `SECRET_KEY` / `SECURITY_PASSWORD_SALT` changed, old API tokens will stop working. Generate a new raw API token and paste it into the add-in.

Number allocation does not create or modify SolidWorks custom properties. Generated part numbers are applied to the filename only. Associated-file metadata is stored in a `.tinymrp-associated-files.json` sidecar next to the SolidWorks document; legacy metadata properties are read for migration but never changed.

## Permissions

- Managing schemes requires admin/manager or permission `numbering.manage`.
- Preview/allocate is available to authenticated users.
