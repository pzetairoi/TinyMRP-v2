# app/extensions.py
import os
from flask_wtf import CSRFProtect
from mongoengine import connect

csrf = CSRFProtect()

def init_mongo(app):
    """
    Establish the MongoEngine connection using a named alias.
    All models should set meta = {"db_alias": DB_ALIAS}.
    """
    uri = app.config.get("MONGO_URI") or os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not configured")
    alias = app.config.get("MONGODB_ALIAS", "tinymrp-v2")
    # uuidRepresentation avoids PyMongo warnings in modern drivers
    connect(host=uri, alias=alias, uuidRepresentation="standard")
