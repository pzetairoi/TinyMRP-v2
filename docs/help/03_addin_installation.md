# SolidWorks Add-in Installation

This page covers installer setup, activation in SolidWorks, and first connection to TinyMRP.

## Before You Start

- SolidWorks installed on the workstation.
- .NET Framework 4.8 available.
- Local admin rights for installer and COM registration.
- TinyMRP access token from `/ui/addin/tokens`.

## Get The Installer

Use one of these:

- Web tools page: `/tools` -> `SolidWorks Setup` -> `Download latest`
- Landing download endpoint: `/downloads/addin`
- File drop used by server tools: `solidworks-addin/Windows Installer latest`

## Run The Installer

1. Close SolidWorks.
2. Run `TinyMRP_SolidWorksAddin_*.exe` as administrator.
3. Complete installer pages:
   - Output folder for exports
   - Template paths and backend URL
   - Optional auth token
   - Optional override/clear of existing settings

The installer registers `TinyMRP.SolidWorksAddin.dll` with `RegAsm`.

## Enable In SolidWorks

1. Open SolidWorks.
2. Go to `Tools > Add-Ins`.
3. Enable `TinyMRP SolidWorks Add-in` for:
   - `Active Add-ins`
   - `Start Up`

If startup is not checked, the add-in will not auto-load after restart.

## Open The Task Pane

- Use `View > Task Pane` if hidden.
- Click the TinyMRP icon in the right task pane.
- You should see tabs: `Publish/BOM`, `Tools`, `Numbering`, `Configuration`.

## First Connection (Recommended)

1. Open `Configuration` tab, `Quick Start`.
2. Set `Backend URL` (use your internal LAN URL, for example `http://tinymrp-lan.company.local`).
3. Paste token into `Auth token`.
4. Click `Test connection`.
5. Save settings.

## Where Settings Are Stored

Config file: `TinyMRP_config.txt`

Read/write precedence:

1. `%PROGRAMDATA%\TinyMRP\TinyMRP_config.txt`
2. Add-in install folder copy
3. `%LOCALAPPDATA%\TinyMRP\TinyMRP_config.txt`

If machine-level path is not writable, the add-in falls back to user-level path.

## Manual Register / Repair (If Needed)

If installer registration fails:

```powershell
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /codebase /tlb
```

To unregister:

```powershell
& "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe" "C:\Path\To\TinyMRP.SolidWorksAddin.dll" /unregister
```

## Silent Install (IT Deployment)

Example:

```powershell
TinyMRP_SolidWorksAddin_*.exe /VERYSILENT /SUPPRESSMSGBOXES /BACKENDURL="http://tinymrp-lan.company.local" /AUTHTOKEN="tmrp_xxx"
```
