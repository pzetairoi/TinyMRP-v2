# TinyMRP LAN-Only Deployment Request (Template)

Use this as-is or copy into your ticketing system.

## Subject

TinyMRP v2 LAN-only server deployment on Windows workstation (no internet exposure)

## Request

Please provision and harden one internal workstation to host TinyMRP v2 for approximately 10 concurrent users.

## Host And Identity

- Hostname: `tinymrp-lan.company.local` (internal DNS only)
- Static IP: `<SERVER_IP>`
- OS: Windows 10/11 Pro or Enterprise
- Domain joined: Yes (preferred)
- Time sync: NTP/domain time

## Network And Firewall (Required)

- Inbound allow:
  - TCP `80` from authorized LAN subnets only: `<LAN_CIDR_LIST>`
- Inbound deny:
  - TCP `8000` (application backend) from all remote hosts
  - TCP `27017` (MongoDB) from all remote hosts
- External exposure:
  - No inbound NAT/public exposure
  - No internet-facing reverse proxy for this host

## Service Account And Permissions

- Create dedicated service account: `<DOMAIN>\tinymrp_svc` (or local equivalent)
- Grant rights:
  - Log on as a service
  - Read/execute on TinyMRP application folder
  - Read/write/modify on:
    - `C:\TinyMRP\data\deliverables`
    - `C:\TinyMRP\config`
    - `C:\TinyMRP\logs`
- Do not grant local administrator unless explicitly required

## Software Components

- Python 3.12 x64
- NGINX for Windows
- Approved service wrapper for NGINX startup management (for example NSSM or WinSW)
- MongoDB server:
  - Prefer separate supported server host; if local, lock bind/listen to localhost only
- TinyMRP application service (Waitress) running on `127.0.0.1:8000`

## Security Controls

- Endpoint protection enabled
- App/data path exclusions only if performance issues are proven
- Weekly OS patch window and monthly dependency review
- No developer debug server in production

## Backup And Recovery

- Nightly backup:
  - MongoDB database (logical or volume backup)
  - `C:\TinyMRP\data\deliverables`
  - `C:\TinyMRP\config`
- Retention: `<RETENTION_POLICY>`
- Recovery test frequency: quarterly

## Acceptance Tests

- From allowed LAN client:
  - `http://tinymrp-lan.company.local` loads successfully
  - Login works
  - Deliverable file access works for authorized users
- From disallowed segment:
  - Connection to `80` blocked
- From any remote host:
  - Direct `8000` and `27017` blocked
