# config.py — ChurchOS environment configuration
# James Koero · 2026
import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

def _require(key):
    v = os.environ.get(key)
    if not v:
        raise EnvironmentError(
            f"ChurchOS: required env var '{key}' is not set.")
    return v

class Config:
    SECRET_KEY              = _require("SECRET_KEY")
    JWT_SECRET_KEY          = _require("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _require("DATABASE_URL")
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_BLOCKLIST_ENABLED     = True
    JWT_BLOCKLIST_TOKEN_CHECKS= ["access", "refresh"]
    JWT_TOKEN_LOCATION        = ["headers"]
    JWT_HEADER_TYPE           = "Bearer"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE    = int(os.environ.get("DB_POOL_SIZE", 5))
    SQLALCHEMY_POOL_RECYCLE = 300
    FRONTEND_URL            = os.environ.get(
        "FRONTEND_URL", "https://churchos.vercel.app")
    MPESA_CONSUMER_KEY      = os.environ.get("MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET   = os.environ.get("MPESA_CONSUMER_SECRET", "")
    MPESA_SHORTCODE         = os.environ.get("MPESA_SHORTCODE", "")
    MPESA_PASSKEY           = os.environ.get("MPESA_PASSKEY", "")
    MPESA_CALLBACK_URL      = os.environ.get("MPESA_CALLBACK_URL", "")
    MPESA_ENV               = os.environ.get("MPESA_ENV", "sandbox")
    FLW_SECRET_KEY          = os.environ.get("FLW_SECRET_KEY", "")
    FLW_SECRET_HASH         = os.environ.get("FLW_SECRET_HASH", "")

class DevelopmentConfig(Config):
    DEBUG           = True
    SQLALCHEMY_ECHO = True
    FRONTEND_URL    = "http://localhost:3000"

class ProductionConfig(Config):
    DEBUG                = False
    PREFERRED_URL_SCHEME = "https"

class TestingConfig(Config):
    TESTING                 = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY          = "test-jwt-only"
    SECRET_KEY              = "test-secret-only"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)

config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     ProductionConfig,
}
