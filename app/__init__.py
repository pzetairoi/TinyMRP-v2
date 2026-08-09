from flask import Flask, app, request, g, jsonify
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
from app.services.timezone_utils import (
    local_date_value,
    local_input_value,
    resolve_timezone_name,
    format_display_ts,
    utc_now,
)





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
        with open(path, encoding="utf-8") as f:
            app.config["VITE_MANIFEST"] = _json.load(f)
    else:
        app.config["VITE_MANIFEST"] = None
    # Debug
    #print("VITE_MANIFEST loaded:", bool(app.config["VITE_MANIFEST"]), "path:", path)




def create_app(config_object=None):
    app = Flask(__name__)

    # Structured logging + request IDs (Phase 1) — first, so startup messages use it.
    from app.services.logging_setup import init_logging
    init_logging(app)
    import logging as _logging
    logger = _logging.getLogger("tinymrp.startup")

    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Application version (surfaced via /api/health). Env/config overrides win.
    if not (app.config.get("APP_VERSION") or os.getenv("APP_VERSION")):
        try:
            version_file = os.path.join(os.path.dirname(__file__), "..", "VERSION")
            with open(version_file, encoding="utf-8") as fh:
                app.config["APP_VERSION"] = fh.read().strip()
        except Exception:
            pass

    
    if config_object:
        app.config.from_object(config_object)

    try:
        from dotenv import load_dotenv
        # Allow selecting a specific env file (e.g. .env.dev, .env.docker)
        env_file = os.getenv("ENV_FILE")
        if env_file and os.path.exists(env_file):
            # When an explicit ENV_FILE is provided, let it override existing env vars
            load_dotenv(env_file, override=True)
            logger.info("Loaded env file: %s", env_file)
        else:
            load_dotenv()
            logger.info("Loaded default .env (if present)")
        logger.info(
            "Env check: SECRET_KEY set? %s; MONGO_URI present? %s",
            bool(os.getenv("SECRET_KEY")),
            bool(os.getenv("MONGO_URI")),
        )
    except Exception:
        logger.warning("Could not load env file(s), continuing without them")

    # There is one security model. The old compat mode is gone: it selected a
    # second set of CORS, CSRF, cookie and upload rules, and every branch that
    # read it now takes the strict path unconditionally.
    
        
    from app.services.processmeta import load_process_meta
    app.config["PROCESS_META"] = load_process_meta()

    # Hardware folder keywords (legacy fastener/library folders)
    default_hw_folders = [
        "toolbox",
        "fasteners",
        "fastener",
        "hardware"
        

    ]
 #   default_hw_folders = [
 #       "toolbox",
 #       "browser",
 #       "fasteners",
 #       "fastener",
 #       "hardware",
 #       "bolts",
 ##       "nuts",
  #      "washers",
  #      "screws",
  #      "rivets",
  #      "pins",
  #      "clips",
  #      "studs",
  #      "spacers",
  #      "standoffs",
  #      "inserts",
  #  ]
    env_hw = os.getenv("HARDWARE_FOLDERS") or os.getenv("HARDWARE_FOLDER") or ""
    if env_hw.strip():
        parts = [p.strip().lower() for p in re.split(r"[;,]", env_hw) if p.strip()]
        app.config["HARDWARE_FOLDERS"] = parts
    else:
        app.config.setdefault("HARDWARE_FOLDERS", default_hw_folders)

    # Flat pattern page label tokens (used to drop sheet metal flat pattern pages in binders)
    default_flat_pattern_page_names = [
        "flatpattern",
    ]
    env_flat = os.getenv("FLAT_PATTERN_PAGE_NAMES") or os.getenv("FLAT_PATTERN_PAGE_LABELS") or ""
    if env_flat.strip():
        parts = [p.strip().lower() for p in re.split(r"[;,]", env_flat) if p.strip()]
        app.config["FLAT_PATTERN_PAGE_NAMES"] = parts
    else:
        app.config.setdefault("FLAT_PATTERN_PAGE_NAMES", default_flat_pattern_page_names)


    # Load default config if not set
    # (Secrets are resolved below to avoid shipping insecure defaults.)
    
    app.config.setdefault("SECURITY_PASSWORD_HASH", "argon2")
    app.config.setdefault("SECURITY_PASSWORD_LENGTH_MIN", int(os.getenv("SECURITY_PASSWORD_LENGTH_MIN") or "12"))
    app.config.setdefault("SECURITY_RETURN_GENERIC_RESPONSES", True)
    # Flask-Security applies these through Werkzeug's cache-control mapping.
    # Token directives use None; bool values serialize as "private=True" and
    # "no-store=True" with current pinned Werkzeug releases.
    app.config.setdefault(
        "SECURITY_CACHE_CONTROL",
        {"private": None, "no-store": None},
    )
    app.config.setdefault("MONGO_URI", "mongodb://localhost:27017/tinymrp-v2")
    app.config.setdefault("SECURITY_REGISTERABLE", False)
    app.config.setdefault("SECURITY_RECOVERABLE", False)
    app.config.setdefault("SECURITY_CONFIRMABLE", False)
    app.config.setdefault(
        "ALLOW_PERMISSION_TEST_DATA",
        str(os.getenv("ALLOW_PERMISSION_TEST_DATA") or "false").strip().lower()
        in ("1", "true", "yes", "on"),
    )
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", False)
    app.config.setdefault("REMEMBER_COOKIE_HTTPONLY", True)
    app.config.setdefault("REMEMBER_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("REMEMBER_COOKIE_SECURE", False)
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", timedelta(minutes=30))
    app.config.setdefault("SESSION_REFRESH_EACH_REQUEST", True)
    for setting_name, fallback in (
        ("API_TOKEN_DEFAULT_TTL_DAYS", 90),
        ("API_TOKEN_MAX_TTL_DAYS", 365),
    ):
        raw_value = os.getenv(setting_name)
        if raw_value is None:
            raw_value = app.config.get(setting_name, fallback)
        try:
            parsed_value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{setting_name} must be a positive integer") from exc
        if parsed_value < 1:
            raise RuntimeError(f"{setting_name} must be a positive integer")
        app.config[setting_name] = parsed_value
    if app.config["API_TOKEN_DEFAULT_TTL_DAYS"] > app.config["API_TOKEN_MAX_TTL_DAYS"]:
        raise RuntimeError(
            "API_TOKEN_DEFAULT_TTL_DAYS cannot exceed API_TOKEN_MAX_TTL_DAYS"
        )
    # Cap "remember me" cookies (default Flask-Login is 365 days — far too long).
    try:
        app.config.setdefault(
            "REMEMBER_COOKIE_DURATION", timedelta(days=int(os.getenv("REMEMBER_COOKIE_DAYS") or "7"))
        )
    except Exception:
        app.config.setdefault("REMEMBER_COOKIE_DURATION", timedelta(days=7))
    app.config.setdefault("EXCEL_COMPILE_MAX_BYTES", int(os.getenv("EXCEL_COMPILE_MAX_BYTES") or "10485760"))
    app.config.setdefault("SECURITY_HEADERS_ENABLED", True)
    app.config.setdefault("FORCE_HTTPS", False)
    # /api/ready fails below this much free space on the deliverables volume.
    # A full disk corrupts imports mid-write, so it is better to drop out of
    # the load balancer than to accept work that cannot be completed.
    # 0 disables the check, matching the convention used by the upload limits.
    app.config.setdefault(
        "READINESS_MIN_FREE_DISK_MB",
        int(os.getenv("READINESS_MIN_FREE_DISK_MB") or "512"),
    )
    app.config.setdefault("UPLOAD_PACK_MAX_ZIP_MB", int(os.getenv("UPLOAD_PACK_MAX_ZIP_MB") or "1024"))
    app.config.setdefault("UPLOAD_PACK_MAX_FILE_MB", int(os.getenv("UPLOAD_PACK_MAX_FILE_MB") or "1024"))
    app.config.setdefault("UPLOAD_PACK_MAX_FILES", int(os.getenv("UPLOAD_PACK_MAX_FILES") or "5000"))
    app.config.setdefault(
        "EXTRA_FILES_ALLOWED",
        str(os.getenv("EXTRA_FILES_ALLOWED") or "true").strip().lower() in ("1", "true", "yes", "on"),
    )
    app.config["SESSION_COOKIE_SECURE"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Strict"

    # CORS allowlist (comma-separated, optional)
    app.config.setdefault("TINYMRP_ALLOWED_ORIGINS", os.getenv("TINYMRP_ALLOWED_ORIGINS") or "")

    # Upload caps (Flask rejects larger requests before reading)
    max_content_mb = os.getenv("TINYMRP_MAX_CONTENT_MB")
    if max_content_mb:
        try:
            max_content_mb = int(max_content_mb)
        except Exception:
            max_content_mb = None
    if not max_content_mb:
        max_content_mb = min(int(app.config.get("UPLOAD_PACK_MAX_ZIP_MB") or 200), 200)
    app.config.setdefault("MAX_CONTENT_LENGTH", int(max_content_mb) * 1024 * 1024)

    # Proxy size caps
    app.config.setdefault("FILES_PROXY_MAX_BYTES", int(os.getenv("FILES_PROXY_MAX_BYTES") or str(200 * 1024 * 1024)))
    
    app.config["TEMPLATES_AUTO_RELOAD"]=True # Enable auto-reload for templates in development
    
    # CSRF + logout config
    app.config.setdefault("WTF_CSRF_ENABLED", True)
    app.config.setdefault("SECURITY_LOGOUT_METHODS", ["POST"])  # explicit
    app.config.setdefault("SECURITY_POST_LOGOUT_VIEW", "/login")  # where to go after logout
    app.config.setdefault("SECURITY_POST_LOGIN_VIEW", "/app")
    
    #Arena file link base URL (for generating links to files in Arena from the UI)
    app.config.setdefault(
    "ARENA_FILE_LINK_BASE_URL",
    (os.getenv("ARENA_FILE_LINK_BASE_URL") or "").strip(),)
    
    # Simple files config (centralized)
    # One local root inside the container/host mount, one URL prefix served by nginx.
    files_local_root = (os.getenv("FILES_LOCAL_ROOT") or os.getenv("FILE_ROOT_LOCAL") or "").strip()
    files_url_prefix = (os.getenv("FILES_URL_PREFIX") or os.getenv("FILE_ROOT_HTTP")  or "").strip()
    files_upstream   = (os.getenv("FILES_UPSTREAM_BASE") or "").strip()
    files_upstream_allowed = (os.getenv("FILES_UPSTREAM_ALLOWED_HOSTS") or "").strip()
    files_public     = (os.getenv("FILES_PUBLIC_URLS") or "").strip().lower()
    accel_prefix     = (os.getenv("FILES_ACCEL_REDIRECT_PREFIX") or "").strip()
    allow_legacy     = (os.getenv("FILES_ALLOW_LEGACY_TOKENS") or "").strip().lower()

    # Canonical keys
    app.config["FILES_LOCAL_ROOT"]   = files_local_root
    app.config["FILES_URL_PREFIX"]   = files_url_prefix
    app.config["FILES_UPSTREAM_BASE"] = files_upstream
    app.config["FILES_UPSTREAM_ALLOWED_HOSTS"] = files_upstream_allowed
    app.config["FILE_HASH_MAX_BYTES"] = int(os.getenv("FILE_HASH_MAX_BYTES") or "0")
    app.config["FILES_PUBLIC_URLS"] = files_public in ("1", "true", "yes", "on")
    app.config["FILES_ACCEL_REDIRECT_PREFIX"] = accel_prefix
    app.config["FILES_ALLOW_LEGACY_TOKENS"] = allow_legacy in ("1", "true", "yes", "on")

    # Tokenized file URLs expire after this many seconds (0 disables expiry).
    try:
        app.config.setdefault(
            "FILES_TOKEN_TTL_SECONDS", int(os.getenv("FILES_TOKEN_TTL_SECONDS") or str(24 * 60 * 60))
        )
    except Exception:
        app.config.setdefault("FILES_TOKEN_TTL_SECONDS", 24 * 60 * 60)

    # Backward-compatible aliases used elsewhere in the codebase
    # (prefer the canonical FILES_* keys in new code)
    app.config["FILE_ROOT_LOCAL"] = files_local_root
    app.config["FILE_ROOT_HTTP"]  = files_url_prefix

    extra_root = (os.getenv("EXTRA_FILES_ROOT") or "").strip()
    if not extra_root and files_local_root:
        extra_root = files_local_root
    app.config["EXTRA_FILES_ROOT"] = extra_root

    #print("FILES: local=", app.config["FILE_ROOT_LOCAL"], "http=", app.config["FILE_ROOT_HTTP"])

    # Then override from environment if set (non-empty)
    for k in ("MONGO_URI",):
        v = os.getenv(k)
        if v and str(v).strip():  # only override if not empty
            app.config[k] = v

    # OPS-DBAUTH-01: Mongo auth is opt-in because enabling it on an existing
    # data volume requires creating users first. It was also silent, so
    # "unauthenticated" was the default AND invisible. Warn on every startup.
    # Deliberately a warning, not a hard failure: refusing to boot would break
    # every running deployment on upgrade, which is a worse outcome than a
    # loud, repeated log line. TINYMRP_REQUIRE_MONGO_AUTH=true opts in to
    # fail-closed for operators who want the guarantee.
    from app.services.mongo_auth import describe_mongo_auth

    mongo_auth_status = describe_mongo_auth(str(app.config.get("MONGO_URI") or ""))
    app.config["MONGO_AUTH_STATUS"] = mongo_auth_status
    if mongo_auth_status["risk"] != "ok":
        require_auth = str(
            os.getenv("TINYMRP_REQUIRE_MONGO_AUTH") or ""
        ).strip().lower() in ("1", "true", "yes", "on")
        if require_auth:
            raise RuntimeError(
                "TINYMRP_REQUIRE_MONGO_AUTH is set but "
                f"{mongo_auth_status['message']}"
            )
        if mongo_auth_status["risk"] == "unauthenticated":
            logger.warning("SECURITY: %s", mongo_auth_status["message"])
        else:
            logger.info("%s", mongo_auth_status["message"])

    # Secrets must be supplied. They are never generated and persisted.
    from app.services.runtime_secrets import resolve_runtime_secrets
    try:
        secret_key, password_salt = resolve_runtime_secrets(app, "strict")
    except RuntimeError as exc:
        raise RuntimeError(str(exc))

    app.config["SECRET_KEY"] = secret_key
    app.config["SECURITY_PASSWORD_SALT"] = password_salt

    # Keep env in sync for services that resolve secrets outside app context (in-process only).
    if not (os.getenv("SECRET_KEY") or "").strip():
        os.environ["SECRET_KEY"] = str(app.config.get("SECRET_KEY"))
    if not (os.getenv("SECURITY_PASSWORD_SALT") or "").strip():
        os.environ["SECURITY_PASSWORD_SALT"] = str(app.config.get("SECURITY_PASSWORD_SALT"))

    # Plain MongoEngine connect – capture the connection object
    app.config.setdefault("MONGODB_ALIAS", "tinymrp-v2")
    # Opt-in request profiler (optimizationplan.txt). Registers nothing unless
    # TINYMRP_PROFILE is set, so production pays no cost for its existence.
    #
    # MUST run before the Mongo client is created: pymongo applies a globally
    # registered listener only to clients built AFTER registration. Wired later
    # it installs cleanly, logs every request, and reports zero operations
    # forever - which looks like a healthy application rather than a broken
    # profiler.
    try:
        from app.services.request_profile import init_request_profiling

        init_request_profiling(app)
    except Exception:
        app.logger.exception("Failed to initialise request profiling")

    init_mongo(app)
    try:
        db_conn = get_connection(alias=app.config.get("MONGODB_ALIAS", "tinymrp-v2"))
    except Exception:
        db_conn = connect(host=app.config["MONGO_URI"], alias=app.config.get("MONGODB_ALIAS", "tinymrp-v2"))

    # Override settings from persisted app settings if available.
    try:
        from app.services.app_settings import get_app_settings, resolve_file_sources
        from app.services.processmeta import load_process_meta
        settings = get_app_settings(create=False)
        file_sources = resolve_file_sources(settings, config=app.config)
        if file_sources:
            app.config["FILE_SOURCES"] = file_sources
            primary_source = next((src for src in file_sources if src.get("active")), file_sources[0])
            primary_root = str(primary_source.get("local_root") or "").strip()
            primary_url = str(primary_source.get("url_prefix") or "").strip()
            if primary_root:
                app.config["FILES_LOCAL_ROOT"] = primary_root
                app.config["FILE_ROOT_LOCAL"] = primary_root
                if not app.config.get("EXTRA_FILES_ROOT"):
                    app.config["EXTRA_FILES_ROOT"] = primary_root
            if primary_url:
                app.config["FILES_URL_PREFIX"] = primary_url
                app.config["FILE_ROOT_HTTP"] = primary_url
        if settings and getattr(settings, "hardware_folders", None):
            hw_tokens = [str(x).strip().lower() for x in (settings.hardware_folders or []) if str(x).strip()]
            if hw_tokens:
                app.config["HARDWARE_FOLDERS"] = hw_tokens
        if settings and getattr(settings, "flat_pattern_page_names", None):
            fp_tokens = [str(x).strip().lower() for x in (settings.flat_pattern_page_names or []) if str(x).strip()]
            if fp_tokens:
                app.config["FLAT_PATTERN_PAGE_NAMES"] = fp_tokens
        if settings is not None:
            app.config["APP_TIMEZONE"] = resolve_timezone_name()
            app.config["DEFAULT_TIMEZONE"] = resolve_timezone_name()
            app.config["PROCESS_META"] = load_process_meta(overrides=getattr(settings, "process_meta", None) or None)
            app.config["ARENA_FILE_LINK_BASE_URL"] = (getattr(settings, "arena_file_link_base_url", "")
                                                      or app.config.get("ARENA_FILE_LINK_BASE_URL", "") or ""
    ).strip()
        if settings:
            if getattr(settings, "upload_pack_max_zip_mb", None) is not None:
                app.config["UPLOAD_PACK_MAX_ZIP_MB"] = int(settings.upload_pack_max_zip_mb or 0)
            if getattr(settings, "upload_pack_max_file_mb", None) is not None:
                app.config["UPLOAD_PACK_MAX_FILE_MB"] = int(settings.upload_pack_max_file_mb or 0)
            if getattr(settings, "upload_pack_max_files", None) is not None:
                app.config["UPLOAD_PACK_MAX_FILES"] = int(settings.upload_pack_max_files or 0)
    except Exception:
        pass

    # Optional TOTP two-factor authentication (Phase 1; default OFF).
    # Enable with SECURITY_TWO_FACTOR_ENABLED=true and provide SECURITY_TOTP_SECRETS
    # (a stable random string used to encrypt per-user TOTP keys at rest).
    two_factor_enabled = str(os.getenv("SECURITY_TWO_FACTOR_ENABLED") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )
    if two_factor_enabled:
        totp_secret = (os.getenv("SECURITY_TOTP_SECRETS") or "").strip()
        if not totp_secret:
            raise RuntimeError(
                "SECURITY_TWO_FACTOR_ENABLED is set but SECURITY_TOTP_SECRETS is missing. "
                "Generate one with: python -c \"from passlib import totp; print(totp.generate_secret())\""
            )
        else:
            app.config["SECURITY_TWO_FACTOR"] = True
            app.config.setdefault("SECURITY_TWO_FACTOR_ENABLED_METHODS", ["authenticator"])
            app.config.setdefault(
                "SECURITY_TWO_FACTOR_REQUIRED",
                str(os.getenv("SECURITY_TWO_FACTOR_REQUIRED") or "").strip().lower()
                in ("1", "true", "yes", "on"),
            )
            app.config.setdefault("SECURITY_TOTP_SECRETS", {"1": totp_secret})
            app.config.setdefault("SECURITY_TOTP_ISSUER", "TinyMRP")
            app.config.setdefault("SECURITY_TWO_FACTOR_RESCUE_MAIL", "")
            app.config.setdefault("SECURITY_TWO_FACTOR_ALWAYS_VALIDATE", False)
            logger.info(
                "Two-factor authentication enabled (required=%s)",
                app.config.get("SECURITY_TWO_FACTOR_REQUIRED"),
            )

    # IMPORTANT: pass (db_connection, User, Role)
    datastore = MongoEngineUserDatastore(db_conn, User, Role)
    global security
    security = Security(app, datastore)

    # Rate limiting (Phase 1) — after Security so auth endpoints exist to decorate.
    try:
        from app.services.rate_limit import init_rate_limiting
        init_rate_limiting(app)
    except Exception:
        logger.exception("Rate limiting initialization failed; continuing WITHOUT rate limits")

    try:
        from flask_login import user_logged_in, user_logged_out

        @user_logged_in.connect_via(app)
        def _audit_login(_sender, user=None, **_extra):
            if user is None:
                return
            try:
                user.last_login_at = utc_now()
                user.last_login_ip = (
                    request.headers.get("X-Forwarded-For")
                    or request.headers.get("X-Real-IP")
                    or request.remote_addr
                    or ""
                )
                user.last_login_ua = request.headers.get("User-Agent") or ""
                user.updated_at = utc_now()
                user.save()
            except Exception:
                pass
            try:
                from app.services.audit import log_action
                log_action("auth.login", resource_type="user", resource=str(getattr(user, "email", "") or ""))
            except Exception:
                pass
            logger.info("auth.login user=%s", str(getattr(user, "email", "") or ""))

        @user_logged_out.connect_via(app)
        def _audit_logout(_sender, user=None, **_extra):
            if user is None:
                return
            try:
                from app.services.audit import log_action
                log_action("auth.logout", resource_type="user", resource=str(getattr(user, "email", "") or ""))
            except Exception:
                pass
            logger.info("auth.logout user=%s", str(getattr(user, "email", "") or ""))
    except Exception:
        pass
    
    # Register CSRF error handler on the app instance
    def handle_csrf_error(e):
        return render_template("csrf_error.html", reason=e.description), 400
    app.register_error_handler(CSRFError, handle_csrf_error)

    # Register a 403 handler that names the missing permission when the
    # denial came from require_permission()/permissions_required() (which
    # stash the AuthorizationDecision on g.authz_denial before aborting).
    # Object-level/scope denials never reach this - those stay non-disclosing
    # 404s at their own call sites, by design.
    def handle_forbidden(e):
        from app.services.security_mode import is_api_request

        decision = getattr(g, "authz_denial", None)
        if decision is not None and getattr(decision, "reason_code", None) == "missing_permission":
            message = f"Missing permission: {decision.permission}"
        else:
            message = "You don't have access to this action."
        if is_api_request(request.path):
            payload = {"error": "forbidden"}
            if decision is not None and getattr(decision, "reason_code", None) == "missing_permission":
                payload["missing_permission"] = decision.permission
            return jsonify(payload), 403
        return render_template("access_denied.html", message=message), 403
    app.register_error_handler(403, handle_forbidden)

    # CSRF
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

        @app.before_request
        def _csp_nonce():
            # One fresh nonce per response. secrets.token_urlsafe is CSPRNG-backed;
            # a guessable nonce would defeat the policy entirely.
            import secrets

            g.csp_nonce = secrets.token_urlsafe(16)
            return None

        @app.context_processor
        def _csp_nonce_context():
            # Templates use <script nonce="{{ csp_nonce() }}">. Returns "" when
            # no request context has run, so rendering never raises.
            return {"csp_nonce": lambda: getattr(g, "csp_nonce", "")}

        @app.after_request
        def _security_headers(resp):
            resp.headers.setdefault("X-Content-Type-Options", "nosniff")
            resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
            # Explicitly disable the legacy XSS auditor (modern guidance; CSP is the control).
            resp.headers.setdefault("X-XSS-Protection", "0")
            resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            if request.is_secure:
                resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

            allow_frame_embedding = bool(getattr(g, "allow_frame_embedding", False))
            if not allow_frame_embedding:
                resp.headers.setdefault("X-Frame-Options", "DENY")

            files_prefix = (app.config.get("FILES_URL_PREFIX") or "").strip()
            img_src = ["'self'", "data:", "blob:", "https:"]
            connect_src = ["'self'"]
            # Only an ABSOLUTE origin belongs in a CSP source list. FILES_URL_PREFIX
            # is normally a same-origin path such as "/deliverables", and a path is
            # not a valid host: browsers reject the whole source with
            # "Couldn't parse invalid host /deliverables" and drop it. Same-origin
            # paths are already covered by 'self', so adding them achieved nothing
            # except a console warning on every page load.
            if files_prefix and "://" in files_prefix:
                from urllib.parse import urlsplit

                parsed = urlsplit(files_prefix)
                if parsed.scheme and parsed.netloc:
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                    img_src.append(origin)
                    connect_src.append(origin)
            # 'unsafe-inline' is still required by the legacy Jinja admin pages.
            # Once those inline scripts move to static files, set
            # TINYMRP_CSP_ALLOW_INLINE=false to drop it (burn-down: plan Phase 1.5).
            allow_inline = str(os.getenv("TINYMRP_CSP_ALLOW_INLINE") or "true").strip().lower() in (
                "1", "true", "yes", "on",
            )
            inline_token = ["'unsafe-inline'"] if allow_inline else []

            # Per-response nonce for the inline-script burn-down. Templates opt in
            # with <script nonce="{{ csp_nonce() }}">; a nonced script keeps
            # working after 'unsafe-inline' is dropped, so templates can migrate
            # one at a time instead of in one risky change.
            #
            # Note browsers IGNORE 'unsafe-inline' when a nonce is present, so
            # the nonce is only emitted once inline is disallowed. Adding it
            # while allow_inline is true would break every not-yet-migrated
            # template at once — the exact big-bang this is meant to avoid.
            nonce_token = []
            if not allow_inline:
                nonce_token = [f"'nonce-{getattr(g, 'csp_nonce', '')}'"]

            script_src = ["'self'", *inline_token, *nonce_token, "https://cdn.jsdelivr.net"]

            # style-src is deliberately decoupled from script-src.
            #
            # The 86 inline style= attributes in the templates are static CSS -
            # column widths, max-heights - and the few dynamic ones interpolate
            # only formatted numbers. None can execute code: style= carries no
            # script, and `expression()` died with IE. Rewriting them all to
            # classes would be a large visual-regression risk across 14
            # templates for no security gain.
            #
            # A nonce does not cover style ATTRIBUTES either (only <style>
            # blocks), so dropping 'unsafe-inline' here would break the layout
            # without a full rewrite. script-src is where XSS actually lands,
            # and it can now be tightened on its own.
            style_src = ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]
            if not allow_frame_embedding:
                csp = " ".join([
                    "default-src 'self';",
                    "base-uri 'self';",
                    "object-src 'none';",
                    "frame-ancestors 'none';",
                    f"script-src {' '.join(script_src)};",
                    f"style-src {' '.join(style_src)};",
                    f"img-src {' '.join(img_src)};",
                    "font-src 'self' data: https://cdn.jsdelivr.net;",
                    f"connect-src {' '.join(connect_src)};",
                ])
                csp = " ".join([csp, "form-action 'self';", "upgrade-insecure-requests;"])
                resp.headers.setdefault("Content-Security-Policy", csp)

                # Optional report-only probe for the 'unsafe-inline' burn-down.
                # Emits the STRICTER policy (no 'unsafe-inline') alongside the
                # enforced one, so browsers report what would break without
                # actually breaking it. Set TINYMRP_CSP_REPORT_URI to collect.
                # This is how to size the migration before flipping
                # TINYMRP_CSP_ALLOW_INLINE=false for real.
                if allow_inline and str(
                    os.getenv("TINYMRP_CSP_REPORT_ONLY_STRICT") or ""
                ).strip().lower() in ("1", "true", "yes", "on"):
                    nonce = getattr(g, "csp_nonce", "")
                    strict_script = ["'self'", f"'nonce-{nonce}'", "https://cdn.jsdelivr.net"]
                    # style-src keeps 'unsafe-inline' HERE TOO, deliberately.
                    # The probe exists to size ONE migration: dropping
                    # 'unsafe-inline' from script-src. Tightening style-src as
                    # well produced hundreds of violations per page load from
                    # PrimeReact injecting <style> elements at runtime and from
                    # style="" attributes, none of which a nonce can ever
                    # cover. That noise buried the only signal worth reading -
                    # whether any SCRIPT violation exists - and made a clean
                    # result look like a failed one.
                    strict_style = ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"]
                    ro = " ".join([
                        "default-src 'self';",
                        "base-uri 'self';",
                        "object-src 'none';",
                        "frame-ancestors 'none';",
                        f"script-src {' '.join(strict_script)};",
                        f"style-src {' '.join(strict_style)};",
                        f"img-src {' '.join(img_src)};",
                        "font-src 'self' data: https://cdn.jsdelivr.net;",
                        f"connect-src {' '.join(connect_src)};",
                    ])
                    report_uri = (os.getenv("TINYMRP_CSP_REPORT_URI") or "").strip()
                    if report_uri:
                        ro = " ".join([ro, f"report-uri {report_uri};"])
                    resp.headers.setdefault("Content-Security-Policy-Report-Only", ro)
            return resp

    # CORS handling (dynamic allowlist; safe by default)
    from app.services.security_mode import (
        API_AUTH_BEARER,
        API_AUTH_HEALTH,
        API_AUTH_PUBLIC_SHARE,
        API_AUTH_SESSION,
        api_auth_policy,
        extract_token_value,
        is_api_request,
        resolve_cors_origin,
        session_csrf_allowed,
    )

    @app.before_request
    def _cors_preflight():
        if request.method != "OPTIONS":
            return None
        if not request.headers.get("Origin"):
            return None
        origin, allow_credentials = resolve_cors_origin()
        if not origin:
            return ("", 403)
        resp = app.make_response("", 204)
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-Auth-Token, Authentication-Token, X-Requested-With, X-CSRFToken"
        resp.headers["Access-Control-Max-Age"] = "600"
        if allow_credentials:
            resp.headers["Access-Control-Allow-Credentials"] = "true"
        return resp

    @app.after_request
    def _cors_headers(resp):
        origin, allow_credentials = resolve_cors_origin()
        if origin:
            resp.headers.setdefault("Access-Control-Allow-Origin", origin)
            resp.headers.setdefault("Vary", "Origin")
            resp.headers.setdefault("Access-Control-Expose-Headers", "Content-Length, Content-Range, Content-Type")
            if allow_credentials:
                resp.headers.setdefault("Access-Control-Allow-Credentials", "true")
        return resp

    from app.services.api_auth import api_error_response
    from app.services.api_tokens import touch_last_used, verify_token

    def _authenticate_presented_api_token(token_value: str):
        token = verify_token(token_value)
        if not token:
            return None
        user = token.user_id
        g.api_user = user
        g.api_token_id = str(token.id)
        touch_last_used(token)
        # Flask-Login-backed authorization still exists in several integration
        # endpoints. Populate its request-local user without creating a cookie.
        try:
            security.login_manager._update_request_context_with_user(user)
        except Exception:
            g._login_user = user
        return user

    @app.before_request
    def _api_authentication_policy_guard():
        if not is_api_request(request.path):
            return None
        policy = api_auth_policy()
        if policy in {API_AUTH_HEALTH, API_AUTH_PUBLIC_SHARE}:
            return None

        token_value = extract_token_value()
        if token_value:
            user = _authenticate_presented_api_token(token_value)
            if not user:
                return api_error_response(
                    "invalid_token",
                    "The API bearer token is invalid, expired, or revoked.",
                )

        has_session = bool(
            getattr(current_user, "is_authenticated", False)
            and not getattr(g, "api_token_id", None)
        )
        has_bearer = bool(getattr(g, "api_token_id", None))

        if policy == API_AUTH_BEARER:
            if not has_bearer:
                return api_error_response(
                    "token_required",
                    "A valid API bearer token is required.",
                )
            return None

        if policy == API_AUTH_SESSION:
            if has_bearer:
                return api_error_response(
                    "session_required",
                    "This browser API requires an authenticated same-origin session.",
                )
            if not has_session:
                return api_error_response(
                    "authentication_required",
                    "Authentication required.",
                )
            return None

        if not (has_session or has_bearer):
            return api_error_response(
                "authentication_required",
                "A browser session or valid API bearer token is required.",
            )
        return None

    # Session CSRF guard (origin/referer check for unsafe methods)
    from flask_security import current_user

    @app.before_request
    def _session_csrf_guard():
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return None
        if getattr(g, "api_token_id", None):
            return None
        if not getattr(current_user, "is_authenticated", False):
            return None
        if session_csrf_allowed():
            return None
        if is_api_request(request.path):
            return api_error_response(
                "csrf_failed",
                "The request origin did not match this TinyMRP instance.",
                status=400,
            )
        return render_template("csrf_error.html", reason="CSRF origin check failed"), 400

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

    # Ensure Parts-list custom/materialized-field indexes exist once at boot
    # instead of on every /api/parts_lazy request (was adding create_index
    # round-trips to the first search after every process start/restart).
    try:
        from app.services.field_config import ensure_active_part_field_indexes
        ensure_active_part_field_indexes()
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

    from app.views.part_shares import bp as part_shares_bp
    app.register_blueprint(part_shares_bp)

    # Help page
    from app.views.help import bp as help_bp
    app.register_blueprint(help_bp)
    
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
    
    # Upload Pack + extra files API
    from app.views.upload_pack import bp as upload_pack_bp
    app.register_blueprint(upload_pack_bp)
    try:
        csrf.exempt(upload_pack_bp)
    except Exception:
        pass
    
    # Register file serving blueprints
    from app.views.files import bp as files_api_bp
    app.register_blueprint(files_api_bp)

    # Drawing markup layers + review threads (SPA JSON API)
    from app.views.part_drawing_markups import bp as part_drawing_markups_bp
    app.register_blueprint(part_drawing_markups_bp)
    try:
        csrf.exempt(part_drawing_markups_bp)
    except Exception:
        pass

    from app.views.fileserve import bp as fileserve_bp
    app.register_blueprint(fileserve_bp)

    from app.views.extra_fileserve import bp as extra_fileserve_bp
    app.register_blueprint(extra_fileserve_bp)
    
    from app.views.processmeta import bp as processmeta_bp
    app.register_blueprint(processmeta_bp)

    from app.views.api_health import bp as api_health_bp
    app.register_blueprint(api_health_bp)
    try:
        csrf.exempt(api_health_bp)
    except Exception:
        pass

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

    from app.views.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp)
    try:
        csrf.exempt(notifications_bp)
    except Exception:
        pass

    from app.views.field_config import bp as field_config_bp
    app.register_blueprint(field_config_bp)
    try:
        csrf.exempt(field_config_bp)
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





    # Expensive-route rate limits, applied HERE and not in init_rate_limiting:
    # that runs before any blueprint exists, so the lookup would find nothing
    # and skip every route in silence (OPS-RATE-01).
    if app.config.get("RATE_LIMIT_ENABLED"):
        try:
            from app.services.rate_limit import apply_expensive_limits

            apply_expensive_limits(app)
        except Exception:
            app.logger.exception("Failed to apply expensive-route rate limits")

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
        current_profile = None
        current_roles = []
        current_permissions = []
        try:
            from flask_login import current_user
            if getattr(current_user, "is_authenticated", False):
                from app.services.user_profile import profile_for_user, permissions_for_user, role_names_for_user
                current_profile = profile_for_user(current_user)
                current_roles = role_names_for_user(current_user)
                current_permissions = permissions_for_user(current_user)
        except Exception:
            current_profile = None
            current_roles = []
            current_permissions = []
        def display_ts(value, fmt="%Y-%m-%d %H:%M:%S %Z"):
            return format_display_ts(value, fmt=fmt)
        def local_date_input(value):
            return local_date_value(value)
        def local_dt_input(value):
            return local_input_value(value)
        def permission_boundary(resource_type: str) -> str:
            try:
                from app.services.field_policies import response_context
                from flask_login import current_user

                return response_context(resource_type, current_user)
            except Exception:
                return ""
        def can_use_order_kind(kind: str, permission: str) -> bool:
            try:
                from app.services.authorization import order_kind_allowed
                from flask_login import current_user

                return order_kind_allowed(current_user, kind, permission)
            except Exception:
                return False
        def can_transition_order_status(current: str, target: str) -> bool:
            try:
                from app.services.biz_utils import can_transition_order

                return target == current or can_transition_order(current, target)
            except Exception:
                return False
        # Permission-test impersonation: targets for the account menu and the
        # banner shown while acting as somebody else. Empty on any instance
        # without ALLOW_PERMISSION_TEST_DATA, so the UI stays hidden.
        impersonation_targets = []
        impersonating_as = ""
        try:
            from flask_login import current_user

            from app.services import impersonation as _imp

            if _imp.impersonator_id():
                impersonating_as = str(getattr(current_user, "email", "") or "")
            else:
                impersonation_targets = [
                    str(user.email) for user in _imp.available_targets(current_user)
                ]
        except Exception:
            impersonation_targets = []
            impersonating_as = ""
        return dict(
            files_base=fb,
            has_perm=has_perm,
            impersonation_targets=impersonation_targets,
            impersonating_as=impersonating_as,
            current_user_profile=current_profile,
            current_user_roles=current_roles,
            current_user_permissions=current_permissions,
            display_ts=display_ts,
            local_date_input=local_date_input,
            local_dt_input=local_dt_input,
            permission_boundary=permission_boundary,
            can_use_order_kind=can_use_order_kind,
            can_transition_order_status=can_transition_order_status,
            app_timezone_name=resolve_timezone_name(),
        )

    from .cli import init_app as init_cli
    init_cli(app)
    
    # ACL default (overridable via env)
    app.config.setdefault("ACL_ENFORCED", True)
    
    return app
