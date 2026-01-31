# SolidWorks add-in installation

This section explains how to install the TinyMRP SolidWorks add-in.

## What you need

- SolidWorks installed on the workstation.
- Windows user with permission to install software.
- The TinyMRP add-in installer (`TinyMRP_SolidWorksAddin_*.exe`).
- A TinyMRP access token (from the Tokens page in the web app).

**Tip:** If you do not have an installer, ask your admin to build or provide it.

## Step-by-step: install the add-in

1) Close SolidWorks if it is open.
2) Run the installer file.
3) Accept the prompts. The installer registers the add-in with SolidWorks.
4) When finished, open SolidWorks.

## Step-by-step: enable the add-in in SolidWorks

1) In SolidWorks, go to `Tools > Add-Ins`.
2) Find "TinyMRP SolidWorks Add-in" in the list.
3) Check "Active Add-ins" to enable it now.
4) Check "Start Up" so it loads every time.

**Common mistake:** Enabling only "Active Add-ins" means it will not load on next restart.

## Step-by-step: open the task pane

1) Look on the right side for the task pane.
2) Click the TinyMRP icon.
3) If the pane is hidden, use `View > Task Pane` to show it.

## Step-by-step: configure the connection

1) Open the Configuration tab in the add-in.
2) Set the Server URL (for example `http://server:5000`).
3) Paste your access token from the Tokens page.
4) Click "Test connection" (or the equivalent button).
5) Save the settings.

**What this button does:** Test connection checks that the server and token are valid.

## Where settings are saved

The add-in stores its settings in a configuration file and uses it when SolidWorks opens. If settings are missing, the add-in may open with empty fields.

## If installation fails

- Restart the computer and try again.
- Check that SolidWorks is installed correctly.
- Ask your IT team to run the installer as an administrator.

