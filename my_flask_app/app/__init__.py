import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import URL
from werkzeug.middleware.proxy_fix import ProxyFix


def required_env(name):
    value = os.environ.get(name, "")
    if not value or value.startswith("REPLACE_WITH_"):
        raise RuntimeError(f"Required environment variable {name} is missing or a placeholder")
    return value


app = Flask(__name__)
app.config["SECRET_KEY"] = required_env("FLASK_SECRET_KEY")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true",
    SESSION_COOKIE_SAMESITE="Lax",
)
trusted_hosts = os.environ.get("TRUSTED_HOSTS", "")
if trusted_hosts:
    app.config["TRUSTED_HOSTS"] = [host.strip() for host in trusted_hosts.split(",") if host.strip()]
proxy_hops = int(os.environ.get("PROXY_HOPS", "0"))
if proxy_hops < 0:
    raise RuntimeError("PROXY_HOPS must not be negative")
if proxy_hops:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxy_hops, x_proto=proxy_hops,
                          x_host=0, x_port=0, x_prefix=0)
app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    "postgresql+psycopg2",
    username=required_env("DB_USER"),
    password=required_env("DB_PASSWORD"),
    host=os.environ.get("DB_HOST", "postgres"),
    port=int(os.environ.get("DB_PORT", "5432")),
    database=required_env("DB_NAME"),
)
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

from app import routes
