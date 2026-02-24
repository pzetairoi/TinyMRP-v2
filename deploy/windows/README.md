# TinyMRP Windows LAN-Only Deployment (Simple Mode)

This guide is for a private office/home LAN with no internet exposure.

Goal:

- Users browse `http://tinymrp-lan.company.local`
- NGINX is the only public service port (`80`)
- TinyMRP app and MongoDB stay private on localhost

## What You Need To Download First

1. Python 3.12 (64-bit)  
https://www.python.org/downloads/windows/

2. MongoDB Community Server (Windows)  
https://www.mongodb.com/download-center/community

3. NGINX for Windows (zip)  
https://nginx.org/en/download.html

4. Optional: Git for Windows  
https://git-scm.com/download/win

## Install Software First

1. Install Python 3.12 and enable `Add python.exe to PATH`.
2. Install MongoDB as a Windows service.
3. Unzip NGINX into `C:\nginx`.

## Check Prerequisites (Do Not Skip)

Open PowerShell:

```powershell
py -0p
python --version
Get-Service MongoDB
Test-Path C:\nginx\nginx.exe
```

If any command fails, fix that before continuing.

## Step-By-Step Setup

Open **PowerShell as Administrator**.

### 1) Set your paths

```powershell
$AppRoot   = "C:\TinyMRP\app\tinymrp_v2"
$DataRoot  = "C:\TinyMRP\data\deliverables"
$ConfigDir = "C:\TinyMRP\config"
$EnvFile   = "C:\TinyMRP\config\.env.lan"
$HostName  = "tinymrp-lan.company.local"
$LanCIDR   = "192.168.0.0/24"
```

### 2) Create folders

```powershell
New-Item -ItemType Directory -Force -Path $DataRoot,$ConfigDir | Out-Null
```

### 3) Verify repo location

Your `$AppRoot` must contain `requirements.txt`, `run.py`, and `deploy\windows`.

```powershell
Test-Path "$AppRoot\requirements.txt"
Test-Path "$AppRoot\run.py"
Test-Path "$AppRoot\deploy\windows\install_tinymrp_service.ps1"
```

All must return `True`.

### 4) Create Python venv and install dependencies

```powershell
cd $AppRoot
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt waitress
```

### 5) Create app env file

```powershell
Copy-Item "$AppRoot\deploy\windows\.env.windows.lan.example" $EnvFile -Force
notepad $EnvFile
```

Set these values in the file:

- `SECRET_KEY` = long random value
- `SECURITY_PASSWORD_SALT` = long random value
- `MONGO_URI=mongodb://127.0.0.1:27017/tinymrp-v2`
- `FILES_LOCAL_ROOT=C:/TinyMRP/data/deliverables`
- `TINYMRP_ALLOWED_ORIGINS=http://tinymrp-lan.company.local`

Keep:

- `TINYMRP_SECURITY_MODE=compat`
- `FORCE_HTTPS=false`
- `FILES_PUBLIC_URLS=false`

### 6) Ensure MongoDB is running

```powershell
Start-Service MongoDB
Get-Service MongoDB
```

Status must be `Running`.

### 7) Configure NGINX (HTTP only)

```powershell
Copy-Item "$AppRoot\deploy\windows\nginx.lan.conf" "C:\nginx\conf\nginx.conf" -Force
notepad "C:\nginx\conf\nginx.conf"
```

Edit in `nginx.conf`:

- `server_name tinymrp-lan.company.local;`
- `alias C:/TinyMRP/data/deliverables/;` (change if your path differs)

Start NGINX:

```powershell
cd C:\nginx
.\nginx.exe -t
.\nginx.exe
```

### 8) Install TinyMRP app service

```powershell
cd $AppRoot
.\deploy\windows\install_tinymrp_service.ps1 `
  -AppRoot $AppRoot `
  -EnvFile $EnvFile `
  -ServiceName "TinyMRP-App" `
  -DisplayName "TinyMRP Application Service" `
  -ReplaceExisting
```

### 9) Apply LAN-only firewall

```powershell
cd $AppRoot
.\deploy\windows\configure_firewall_lan.ps1 `
  -LanRemoteRanges $LanCIDR `
  -HttpPort 80
```

### 10) Seed roles and admin user

```powershell
cd $AppRoot
$env:ENV_FILE = $EnvFile
.\.venv\Scripts\flask.exe --app run.py user seed-roles
.\.venv\Scripts\flask.exe --app run.py user create --email admin@yourcompany.com --password "ChangeThisNow!"
.\.venv\Scripts\flask.exe --app run.py user grant-admin --email admin@yourcompany.com
```

### 11) Test locally

Open in browser:

- `http://localhost/healthz`
- `http://localhost/`

### 12) Test from another LAN PC

Add DNS/hosts entry for:

- `tinymrp-lan.company.local -> <server_ip>`

Then test:

```powershell
Test-NetConnection <server_ip> -Port 80
Test-NetConnection <server_ip> -Port 8000
Test-NetConnection <server_ip> -Port 27017
```

Expected:

- `80` reachable
- `8000` blocked
- `27017` blocked

## SolidWorks Add-in URL

Use this backend URL in installer/config:

`http://tinymrp-lan.company.local`

## Common Errors

1. `Could not open requirements.txt`  
You are in wrong folder. Fix `$AppRoot`.

2. Bad CIDR format  
Wrong: `192.168.0.111/24`  
Right single PC: `192.168.0.111/32`  
Right subnet: `192.168.0.0/24`

3. Service/firewall commands fail  
Run PowerShell as Administrator.

