# SolidWorks Add-in UI Redesign Tests

## Automated tests (no SolidWorks required)
- `dotnet test solidworks-addin\TinyMRP.SolidWorksAddin.Tests\TinyMRP.SolidWorksAddin.Tests.csproj`

## Manual checklist (SolidWorks)
1) Open SolidWorks and enable the TinyMRP task pane.
2) Go to **Numbering** tab.
3) Verify the top command strip is visible without scrolling.
4) Quick setup
   - Select a preset scheme.
   - Enter only required context fields (others stay hidden).
   - Click **Preview Next** and confirm the preview fields populate.
5) Allocate and apply
   - Click **Allocate & Apply**.
   - Confirm PartNumber/Revision/DisplayCode properties are written.
6) Auto-rename (safe)
   - Check **Auto-rename file after allocation**.
   - Keep **Safe (recommended)** mode.
   - Click **Allocate + Apply + Rename**.
   - Confirm file is renamed and references are updated when possible.
7) Rename dry run
   - Expand **Advanced**.
   - Click **Dry run rename** and verify current/proposed path are shown.
8) Advanced allocation
   - Use **Allocate (advanced)** with a revision action if needed.
9) Logging
   - Verify `%LOCALAPPDATA%\TinyMRP\logs\addin.log` contains rename steps and outcomes.
