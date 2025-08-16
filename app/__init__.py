from flask import Flask
from mongoengine import connect
from flask_security import Security, MongoEngineUserDatastore
from .models.auth import User, Role



from flask_wtf import CSRFProtect   # CSRF protection for forms
csrf = CSRFProtect()  # Initialize CSRF protection

from flask import render_template # For rendering templates
from flask_wtf.csrf import CSRFError # CSRF error handling

from .extensions import csrf, init_mongo # Import CSRF and MongoDB init



security = None

import os, json
def _load_vite_manifest(app):
    manifest_path = os.path.join(app.static_folder, "parts-ui", "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            app.config["VITE_MANIFEST"] = json.load(f)
    else:
        app.config["VITE_MANIFEST"] = None


def create_app(config_object=None):
    app = Flask(__name__)
    if config_object:
        app.config.from_object(config_object)

    try:
        from dotenv import load_dotenv; load_dotenv()
        print("Loaded .env file successfully")
        print(f".env loaded? SECRET_KEY set: {bool(os.getenv('SECRET_KEY'))}; "
      f"MONGO_URI present: {bool(os.getenv('MONGO_URI'))}")
        print("App SECRET_KEY prefix:", str(os.getenv('SECRET_KEY'))[:8])
        
         
    except Exception:
        print("ddid not work loading .env file, continuing without it")
        pass

    # Load default config if not set
    app.config.setdefault("SECRET_KEY", "change-me")
    app.config.setdefault("SECURITY_PASSWORD_SALT", "change-me-too")
    app.config.setdefault("SECURITY_PASSWORD_HASH", "argon2")
    app.config.setdefault("MONGO_URI", "mongodb://localhost:27017/tinymrp-v2")
    app.config.setdefault("SECURITY_REGISTERABLE", False)
    app.config.setdefault("SECURITY_RECOVERABLE", False)
    app.config.setdefault("SECURITY_CONFIRMABLE", False)
    
    app.config["TEMPLATES_AUTO_RELOAD"]=True # Enable auto-reload for templates in development
    
    # CSRF + logout config
    app.config.setdefault("WTF_CSRF_ENABLED", True)
    app.config.setdefault("SECURITY_LOGOUT_METHODS", ["POST"])  # explicit
    app.config.setdefault("SECURITY_POST_LOGOUT_VIEW", "/login")  # where to go after logout

    csrf.init_app(app)
    
    # Then override from environment if set (non-empty)
    for k in ("SECRET_KEY", "SECURITY_PASSWORD_SALT", "MONGO_URI"):
        v = os.getenv(k)
        if v:  # only override if not empty
            app.config[k] = v
            
    # Final safety net for local dev
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = secrets.token_urlsafe(32)

    # Plain MongoEngine connect – capture the connection object
    db_conn = connect(host=app.config["MONGO_URI"])

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

    # Mongo
    app.config.setdefault("MONGODB_ALIAS", "tinymrp-v2")
    init_mongo(app)

    
    # Register blueprints
    from .views.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from .views.admin import bp as admin_bp
    app.register_blueprint(admin_bp)
    
    from .views.admin_roles import bp as admin_roles_bp
    app.register_blueprint(admin_roles_bp)
    
    # Load Vite manifest for static files
    _load_vite_manifest(app)
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
    

    from .cli import init_app as init_cli
    init_cli(app)
    return app
