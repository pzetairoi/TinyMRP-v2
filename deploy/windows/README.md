# TinyMRP on Windows — LAN only

**The guide is [`docs/deployment/03-windows-lan.md`](../../docs/deployment/03-windows-lan.md).**
It covers both Windows options — Docker Desktop (recommended, one script) and
the native service these files support — with every parameter, the backup and
update procedures, and a symptom-first troubleshooting table.

This page is not a second copy of it. It says only what the files *in this
directory* are, so you can tell at a glance which one you need.

## What is here

| File | Purpose |
| --- | --- |
| `install_tinymrp_service.ps1` | Installs the TinyMRP Windows service (waitress behind nginx). Run from an elevated PowerShell. |
| `run_waitress_service.ps1` | The service entry point. Called by the service, not by you. |
| `configure_firewall_lan.ps1` | Applies the LAN-only firewall policy: opens the nginx port to your subnet, blocks 8000 and 27017 from the network. |
| `check_lan_access.ps1` | Diagnostic. Run it when other machines cannot reach the server — it checks binding, firewall profile, DNS and the live cookie/CSP headers. |
| `nginx.lan.conf` | nginx site to copy to `C:\nginx\conf\nginx.conf`. Set `server_name` and the deliverables `alias`. |
| `.env.windows.lan.example` | Configuration template. Four values are REQUIRED; the file says which. |
| `IT_REQUEST_TEMPLATE.md` | A ready-made ticket for whoever has to approve the install and open the firewall. |

## The two commands people actually come here for

```powershell
# install the service (elevated)
.\deploy\windows\install_tinymrp_service.ps1 -AppRoot C:\TinyMRP\app\tinymrp_v2 `
  -EnvFile C:\TinyMRP\config\.env.lan -ReplaceExisting

# other machines cannot reach it
.\deploy\windows\check_lan_access.ps1 -Port 80
```

## One setting decides whether it works

`TINYMRP_URL` in your env file — the address users type, **scheme included**.
On this path it is plain HTTP, so it must be `http://`, and it must carry the
port if you are not on 80:

```
TINYMRP_URL=http://tinymrp-lan.company.local
```

Declaring `https://` on a plain-HTTP deployment makes every login bounce
straight back to the login form with no error shown. That is the single most
common failure here, and the reason `check_lan_access.ps1` inspects the live
`Set-Cookie` and CSP headers.

Use the same address as the SolidWorks add-in backend URL, **with the scheme**.

## Not this path?

| You want | Go to |
| --- | --- |
| Windows with Docker Desktop — simpler, one script | [`docs/deployment/01-vm-docker.md`](../../docs/deployment/01-vm-docker.md) |
| A locked-down host where only `python run.py` is approved | [`docs/deployment/12-restricted-windows-flask.md`](../../docs/deployment/12-restricted-windows-flask.md) and [`deploy/windows-restricted/`](../windows-restricted/) |
| HTTPS on this LAN deployment | [`docs/deployment/08-networking-and-tls.md`](../../docs/deployment/08-networking-and-tls.md) |
