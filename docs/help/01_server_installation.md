# Server and web app installation

This section explains how to install and run the TinyMRP server and web app. It is written for non-IT users and assumes you have someone with basic server access.

## Before you begin

You will need:

- A Windows or Linux server (or a workstation for testing).
- An internet connection for the first setup.
- Access to the deliverables folder where SolidWorks exports files.
- A browser (Chrome, Edge, or Firefox).

**Tip:** If you are not sure which installation method to use, ask your IT contact to set up the Docker method. It is usually the simplest to keep stable.

## Option A: Recommended installation (Docker Compose)

This method runs the app, database, and file service together.

### Step 1: Get the project files

1) Download or clone the TinyMRP repository to a folder on the server.
2) Keep this folder for future updates.

### Step 2: Prepare the environment file

1) Copy an example env file (for example `.env.server.example`) to `.env`.
2) Open `.env` in a text editor.
3) Fill in the required values. At minimum you must set:
   - `SECRET_KEY`
   - `SECURITY_PASSWORD_SALT`
   - `MONGO_URI`
   - `DELIVERABLES_DIR` or `FILES_LOCAL_ROOT` (where deliverables are stored)
   - `HTTP_PORT` (the port users will open in their browser)

**Common mistake:** Pointing `DELIVERABLES_DIR` to a local folder on your PC instead of the shared folder where deliverables are exported.

### Step 3: Start the stack

1) Open a terminal in the project folder.
2) Run:
   - `docker compose up -d --build`
3) Wait until the containers are running.

### Step 4: Create the first admin user

1) Run the commands below:
   - `docker compose exec app flask --app run.py user seed-roles`
   - `docker compose exec app flask --app run.py user create --email admin@yourcompany.com --password <password>`
   - `docker compose exec app flask --app run.py user grant-admin --email admin@yourcompany.com`
2) The admin can now log in and create other users.

### Step 5: Open the web app

1) Open your browser.
2) Go to `http://<server>:<HTTP_PORT>` (for example `http://192.168.1.10:5000`).
3) Log in with the admin account you created.

## Option B: Local development install (advanced)

This is intended for developers. It is not the recommended production setup.

1) Install Python and Node.js.
2) Install Python requirements: `pip install -r requirements.txt`.
3) Install frontend dependencies: `npm install` in the `frontend/` folder.
4) Run the backend: `python run.py`.
5) Run the frontend build: `npm run build` (or `npm run dev` for development).

## File storage and deliverables

TinyMRP expects deliverables to be stored in a folder structure like this:

- `deliverables/png/` (preview images)
- `deliverables/pdf/` (drawings)
- `deliverables/dxf/`
- `deliverables/step/`
- `deliverables/3mf/`
- `deliverables/ply/`
- `deliverables/stl/`

Each file should follow the naming pattern:

- `PARTNUMBER_REV_REVISION.ext`

For example:

- `ABC-100_REV_A.pdf`
- `ABC-100_REV_A.png`
- `ABC-100_REV_.pdf` (empty revision is allowed)

**What this means:** If you publish a part and later change the revision, the file name changes. TinyMRP uses this to keep revisions separate.

## Logging in and permissions

- Users must log in to see the app.
- Roles control which menus and actions are visible.
- The admin can create roles and assign permissions in the Admin Dashboard.

## Updating the server later

1) Pull the latest code changes into the server folder.
2) Re-run `docker compose up -d --build`.
3) If the database schema changes, follow the release notes.

**Tip:** Schedule updates during low usage hours.
