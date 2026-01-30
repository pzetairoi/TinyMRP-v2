from flask import Flask, app, request
from mongoengine import connect, get_connection
from flask_security import Security, MongoEngineUserDatastore
from .models.auth import User, Role



from flask_wtf import CSRFProtect   # CSRF protection for forms
csrf = CSRFProtect()  # Initialize CSRF protection

from flask import render_template # For rendering templates
from flask_wtf.csrf import CSRFError # CSRF error handling

from .extensions import csrf, init_mongo # Import CSRF and MongoDB init



security = None

import os
import re
import secrets
import json as _json
from datetime import timedelta





def _find_manifest(static_folder: str):
    cands = [
        os.path.join(static_folder, "parts-ui", "manifest.json"),
        os.path.join(static_folder, "parts-ui", ".vite", "manifest.json"),
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return None

def _load_vite_manifest(app):
    path = _find_manifest(app.static_folder)
    app.config["VITE_MANIFEST_PATH"] = path
    if path:
        with open(path, "r", encoding="utf-8") as f:
            app.config["VITE_MANIFEST"] = _json.load(f)
    else:
        app.config["VITE_MANIFEST"] = None
    # Debug
    #print("VITE_MANIFEST loaded:", bool(app.config["VITE_MANIFEST"]), "path:", path)




def create_app(config_object=None):
    app = Flask(__name__)
    
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    
    if config_object:
        app.config.from_object(config_object)

    try:
        from dotenv import load_dotenv
        # Allow selecting a specific env file (e.g. .env.dev, .env.docker)
        env_file = os.getenv("ENV_FILE")
        if env_file and os.path.exists(env_file):
            # When an explicit ENV_FILE is provided, let it override existing env vars
            load_dotenv(env_file, override=True)
            print("Loaded env file:", env_file)
        else:
            load_dotenv()
            print("Loaded default .env (if present)")
        print(f"Env check: SECRET_KEY set? {bool(os.getenv('SECRET_KEY'))}; "
              f"MONGO_URI present? {bool(os.getenv('MONGO_URI'))}")
    except Exception:
        print("did not work loading env file(s), continuing without them")
        pass
    
        
    from app.services.processmeta import load_process_meta
    app.config["PROCESS_META"] = load_process_meta()

    # Hardware folder keywords (legacy fastener/library folders)
    default_hw_folders = [
        "toolbox",
        "browser",
        "fasteners",
        "fastener",
        "hardware",
        "bolts",
        "nuts",
        "washers",
        "screws",
        "rivets",
        "pins",
        "clips",
        "studs",
        "spacers",
        "standoffs",
        "inserts",
    ]
    env_hw = os.getenv("HARDWARE_FOLDERS") or os.getenv("HARDWARE_FOLDER") or ""
    if env_hw.strip():
        parts = [p.strip().lower() for p in re.split(r"[;,]", env_hw) if p.strip()]
        app.config["HARDWARE_FOLDERS"] = parts
    else:
        app.config.setdefault("HARDWARE_FOLDERS", default_hw_folders)


    # Load default config if not set
    app.config.setdefault("SECRET_KEY", "change-me")
    app.config.setdefault("SECURITY_PASSWORD_SALT", "change-me-too")
    app.config.setdefault("SECURITY_PASSWORD_HASH", "argon2")
    app.config.setdefault("MONGO_URI", "mongodb://localhost:27017/tinymrp-v2")
    app.config.setdefault("SECURITY_REGISTERABLE", False)
    app.config.setdefault("SECURITY_RECOVERABLE", False)
    app.config.setdefault("SECURITY_CONFIRMABLE", False)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)
    app.config.setdefault("REMEMBER_COOKIE_HTTPONLY", True)
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_SECURE", False)
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(minutes=30))
    app.config.setdefault("SESSION_REFRESH_EACH_REQUEST", True)
    app.config.setdefault("EXCEL_COMPILE_MAX_BYTES", int(os.getenv("EXCEL_COMPILE_MAX_BYTES") or "10485760"))
    app.config.setdefault("SECURITY_HEADERS_ENABLED", True)
    app.config.setdefault("FORCE_HTTPS", False)
    
    app.config["TEMPLATES_AUTO_RELOAD"]=True # Enable auto-reload for templates in development
    
    # CSRF + logout config
    app.config.setdefault("WTF_CSRF_ENABLED", True)
    app.config.setdefault("SECURITY_LOGOUT_METHODS", ["POST"])  # explicit
    app.config.setdefault("SECURITY_POST_LOGOUT_VIEW", "/login")  # where to go after logout
    
    # Simple files config (centralized)
    # One local root inside the container/host mount, one URL prefix served by nginx.
    files_local_root = (os.getenv("FILES_LOCAL_ROOT") or os.getenv("FILE_ROOT_LOCAL") or "").strip()
    files_url_prefix = (os.getenv("FILES_URL_PREFIX") or os.getenv("FILE_ROOT_HTTP")  or "").strip()
    files_upstream   = (os.getenv("FILES_UPSTREAM_BASE") or "").strip()
    files_public     = (os.getenv("FILES_PUBLIC_URLS") or "").strip().lower()
    accel_prefix     = (os.getenv("FILES_ACCEL_REDIRECT_PREFIX") or "").strip()
    allow_legacy     = (os.getenv("FILES_ALLOW_LEGACY_TOKENS") or "").strip().lower()

    # Canonical keys
    app.config["FILES_LOCAL_ROOT"]   = files_local_root
    app.config["FILES_URL_PREFIX"]   = files_url_prefix
    app.config["FILES_UPSTREAM_BASE"] = files_upstream
    app.config["FILE_HASH_MAX_BYTES"] = int(os.getenv("FILE_HASH_MAX_BYTES") or "0")
    app.config["FILES_PUBLIC_URLS"] = files_public in ("1", "true", "yes", "on")
    app.config["FILES_ACCEL_REDIRECT_PREFIX"] = accel_prefix
    app.config["FILES_ALLOW_LEGACY_TOKENS"] = allow_legacy in ("1", "true", "yes", "on")

    # Backward-compatible aliases used elsewhere in the codebase
    # (prefer the canonical FILES_* keys in new code)
    app.config["FILE_ROOT_LOCAL"] = files_local_root
    app.config["FILE_ROOT_HTTP"]  = files_url_prefix

    #print("FILES: local=", app.config["FILE_ROOT_LOCAL"], "http=", app.config["FILE_ROOT_HTTP"])




    csrf.init_app(app)
    
    # Then override from environment if set (non-empty)
    for k in ("SECRET_KEY", "SECURITY_PASSWORD_SALT", "MONGO_URI"):
        v = os.getenv(k)
        if v:  # only override if not empty
            app.config[k] = v
            
    # Final safety net for local dev
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_urlsafe(32)
    if app.config.get("SECRET_KEY") in ("change-me", "changeme"):
        print("Warning: SECRET_KEY uses a default value. Set SECRET_KEY in the environment.")
    if app.config.get("SECURITY_PASSWORD_SALT") in ("change-me-too", "changeme"):
        print("Warning: SECURITY_PASSWORD_SALT uses a default value. Set SECURITY_PASSWORD_SALT in the environment.")
    # Keep env in sync for services that resolve secrets outside app context
    if not os.getenv("SECRET_KEY") and app.config.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = str(app.config.get("SECRET_KEY"))
    if not os.getenv("SECURITY_PASSWORD_SALT") and app.config.get("SECURITY_PASSWORD_SALT"):
        os.environ["SECURITY_PASSWORD_SALT"] = str(app.config.get("SECURITY_PASSWORD_SALT"))

    # Plain MongoEngine connect – capture the connection object
    app.config.setdefault("MONGODB_ALIAS", "tinymrp-v2")
    init_mongo(app)
    try:
        db_conn = get_connection(alias=app.config.get("MONGODB_ALIAS", "tinymrp-v2"))
    except Exception:
        db_conn = connect(host=app.config["MONGO_URI"], alias=app.config.get("MONGODB_ALIAS", "tinymrp-v2"))

    # IMPORTANT: pass (db_connection, User, Role)
    datastore = MongoEngineUserDatastore(db_conn, User, Role)
    global security
    security = Security(app, datastore)
    
    # Register CSRF error handler on the app instance
    def handle_csrf_error(e):
        return render_template("csrf_error.html", reason=e.description), 400
    app.register_error_handler(CSRFError, handle_csrf_error)
    
    # CSRF
    app.config.setdefault("WTF_CSRF_ENABLED", True)
    csrf.init_app(app)

    if bool(app.config.get("FORCE_HTTPS")):
        app.config["PREFERRED_URL_SCHEME"] = "https"
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["REMEMBER_COOKIE_SECURE"] = True

        @app.before_request
        def _force_https():
            try:
                from flask import request, redirect
                if not request.is_secure:
                    url = request.url.replace("http://", "https://", 1)
                    return redirect(url, code=301)
            except Exception:
                return None

    if bool(app.config.get("SECURITY_HEADERS_ENABLED")):
        @app.after_request
        def _security_headers(resp):
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("X-Frame-Options", "DENY")
            resp.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
            resp.headers.setdefault("X-XSS-Protection", "1; mode=block")
            resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            if request.is_secure:
                resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

            files_prefix = (app.config.get("FILES_URL_PREFIX") or "").strip()
            img_src = ["'self'", "data:", "blob:", "https:"]
            connect_src = ["'self'"]
            if files_prefix:
                img_src.append(files_prefix)
                connect_src.append(files_prefix)
            csp = " ".join([
                "default-src 'self';",
                "base-uri 'self';",
                "object-src 'none';",
                "frame-ancestors 'none';",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;",
                f"img-src {' '.join(img_src)};",
                "font-src 'self' data: https://cdn.jsdelivr.net;",
                f"connect-src {' '.join(connect_src)};",
            ])
            resp.headers.setdefault("Content-Security-Policy", csp)
            return resp

    try:
        from app.services.metrics import init_metrics
        init_metrics(app)
    except Exception:
        pass

    # Mongo initialized earlier
    try:
        from app.services.numbering_presets import ensure_presets
        ensure_presets()
    except Exception:
        pass
    
    # Load manifest ONCE at startup
    _load_vite_manifest(app)

    
    # Register blueprints
    from .views.main import bp as main_bp
    app.register_blueprint(main_bp)

    from .views.branding import bp as branding_bp
    app.register_blueprint(branding_bp)
    
    from .views.admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    
    from .views.admin_roles import bp as admin_roles_bp
    app.register_blueprint(admin_roles_bp)
    
    from .views.admin_jobs import bp as admin_jobs_bp
    app.register_blueprint(admin_jobs_bp)

    from .views.admin_suppliers import bp as admin_suppliers_bp
    app.register_blueprint(admin_suppliers_bp)

    from .views.admin_customers import bp as admin_customers_bp
    app.register_blueprint(admin_customers_bp)

    from .views.admin_orders import bp as admin_orders_bp
    app.register_blueprint(admin_orders_bp)

    # Tools pages (templates, Excel BOM builder)
    from .views.tools import bp as tools_bp
    app.register_blueprint(tools_bp)

    # Admin audit log
    from .views.admin_audit import bp as admin_audit_bp
    app.register_blueprint(admin_audit_bp)
    

    # register blueprints for ui
    from app.views.ui import bp as ui_bp
    app.register_blueprint(ui_bp)
    
    #Bom and parts APIs
    from app.views.parts import bp as parts_api_bp
    from app.views.bom_tree import bp as bom_tree_api_bp
    from app.views.whereused import bp as whereused_api_bp
    app.register_blueprint(parts_api_bp)
    app.register_blueprint(bom_tree_api_bp)
    app.register_blueprint(whereused_api_bp)
    csrf.exempt(whereused_api_bp)

    from app.views.dashboard import bp as dashboard_api_bp
    app.register_blueprint(dashboard_api_bp)
    
    # Importer views for BOM uploads
    from app.views.importer import bp as importer_bp
    app.register_blueprint(importer_bp)
    
    # Register file serving blueprints
    from app.views.files import bp as files_api_bp
    app.register_blueprint(files_api_bp)

    from app.views.fileserve import bp as fileserve_bp
    app.register_blueprint(fileserve_bp)
    
    from app.views.processmeta import bp as processmeta_bp
    app.register_blueprint(processmeta_bp)

    from app.views.numbering import bp as numbering_bp
    app.register_blueprint(numbering_bp)
    try:
        csrf.exempt(numbering_bp)
    except Exception:
        pass

    from app.views.me import bp as me_bp
    app.register_blueprint(me_bp)
    try:
        csrf.exempt(me_bp)
    except Exception:
        pass

    from app.views.auth_api import bp as auth_api_bp
    app.register_blueprint(auth_api_bp)
    try:
        csrf.exempt(auth_api_bp)
    except Exception:
        pass

    # Business APIs (jobs/suppliers/customers/orders)
    from app.views.api_jobs import bp as jobs_api_bp
    from app.views.api_suppliers import bp as suppliers_api_bp
    from app.views.api_customers import bp as customers_api_bp
    from app.views.api_orders import bp as orders_api_bp
    app.register_blueprint(jobs_api_bp)
    app.register_blueprint(suppliers_api_bp)
    app.register_blueprint(customers_api_bp)
    app.register_blueprint(orders_api_bp)
    try:
        csrf.exempt(jobs_api_bp)
        csrf.exempt(suppliers_api_bp)
        csrf.exempt(customers_api_bp)
        csrf.exempt(orders_api_bp)
    except Exception:
        pass
    
    # File proxy (for HTTP file roots)
    from .files_proxy import files_proxy
    app.register_blueprint(files_proxy)

    # Doc packs API
    from app.views.docpacks import bp as docpacks_bp
    app.register_blueprint(docpacks_bp)
    # This is an API endpoint hit from the SPA; exempt from CSRF
    try:
        csrf.exempt(docpacks_bp)
    except Exception:
        pass





    # Make files_base available in all templates for the frontend runtime
    @app.context_processor
    def inject_files_base():
        fb = ""
        if app.config.get("FILES_PUBLIC_URLS"):
            fb = (app.config.get("FILE_ROOT_HTTP") or app.config.get("FILES_URL_PREFIX") or "").rstrip("/")
        # expose a has_perm helper for templates
        try:
            from app.services.acl import user_has_permission
            def has_perm(p: str) -> bool:
                try:
                    from flask_login import current_user
                    # Admin sees everything
                    for r in (getattr(current_user, 'roles', []) or []):
                        if getattr(r, 'name', '') == 'admin':
                            return True
                    return user_has_permission(current_user, p)
                except Exception:
                    return False
        except Exception:
            def has_perm(p: str) -> bool:
                return False
        return dict(files_base=fb, has_perm=has_perm)

    from .cli import init_app as init_cli
    init_cli(app)
    
    # ACL default (overridable via env)
    app.config.setdefault("ACL_ENFORCED", True)
    
    return app
