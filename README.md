# TinyMRP v2

**Lean, MongoDB-backed MRP starter** focused on Bills of Materials (BOM), work orders, and a simple parts browser.  
This is a from-scratch rebuild of TinyMRP with modern auth and a Mongo-first data model for tree-shaped BOMs.

> Original project: [pzetairoi/TinyMRP](https://github.com/pzetairoi/TinyMRP) — “Lean inventory and MRP system based on python.”  
> This v2 modernizes the stack and removes the SQLite/Excel config used in the legacy app. :contentReference[oaicite:1]{index=1}

---

## What’s in v2 (today)

- **Auth**: Flask-Security (login, roles, permissions), Argon2 hashing
- **Admin**: Users list/create, roles & permissions editor
- **Parts browser** (BOM-centric): DataTables (Bootstrap 5) with global + per-column filters; server-side querying in MongoDB
- **Clean UI**: Bootstrap 5 base layout + public landing page
- **Dev-first**: Conda env, `.env` config, CSRF everywhere

Roadmap: password reset, BOM tree explorer, work orders, MRP run.

---

## Tech Stack

- **Backend**: Python 3.12, Flask 3.x, MongoEngine 0.29.x (on PyMongo 4.x)
- **Auth**: Flask-Security-Too 5.6.x
- **DB**: MongoDB 6/7 (Atlas or local)
- **Frontend**: Bootstrap 5.3, DataTables 2.x + jQuery 3.7
- **Dev**: Conda (Windows/macOS/Linux), `python-dotenv`

---

## Quick start (Windows with Conda)

```powershell
# 1) Clone
git clone https://github.com/<you>/<your-new-repo>.git tinymrp_v2
cd tinymrp_v2

# 2) Environment
conda create -n tinymrp-v2 python=3.12 pip -y
conda activate tinymrp-v2

# 3) Install
pip install -r requirements.txt

# 4) Configure (.env in project root)
# generate secrets: python -c "import secrets;print(secrets.token_urlsafe(32))"
# copy/paste your values:
# SECRET_KEY=...
# SECURITY_PASSWORD_SALT=...
# MONGO_URI=mongodb://localhost:27017/tinymrp_v2

# 5) Run
python run.py   # visit http://127.0.0.1:5000

# 6) Create first user (then grant yourself admin)
flask --app run.py user create
flask --app run.py user grant-admin --email you@example.com
