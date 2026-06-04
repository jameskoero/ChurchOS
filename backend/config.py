# config.py - ChurchOS
import os
from datetime import timedelta
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool

load_dotenv()


def _require(key):
    v = os.environ.get(key)
    if not v:
        raise EnvironmentError(
            f"Required env var '{key}' "
            f"is not set.")
    return v


class Config:
    SECRET_KEY = _require("SECRET_KEY")
    JWT_SECRET_KEY = _require(
        "JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _require(
        "DATABASE_URL")
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": NullPool,
        "connect_args": {
            "sslmode": "require",
            "connect_timeout": 10,
        },
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=30)
    JWT_BLOCKLIST_ENABLED = True
    JWT_BLOCKLIST_TOKEN_CHECKS = [
        "access", "refresh"]
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_TYPE = "Bearer"
    FRONTEND_URL = os.environ.get(
        "FRONTEND_URL",
        "https://churchos-app.vercel.app")
    MPESA_CONSUMER_KEY = os.environ.get(
        "MPESA_CONSUMER_KEY", "")
    MPESA_CONSUMER_SECRET = os.environ.get(
        "MPESA_CONSUMER_SECRET", "")
    MPESA_SHORTCODE = os.environ.get(
        "MPESA_SHORTCODE", "")
    MPESA_PASSKEY = os.environ.get(
        "MPESA_PASSKEY", "")
    MPESA_CALLBACK_URL = os.environ.get(
        "MPESA_CALLBACK_URL", "")
    MPESA_ENV = os.environ.get(
        "MPESA_ENV", "sandbox")
    FLW_SECRET_KEY = os.environ.get(
        "FLW_SECRET_KEY", "")
    FLW_SECRET_HASH = os.environ.get(
        "FLW_SECRET_HASH", "")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    SQLALCHEMY_ENGINE_OPTIONS = {}
    FRONTEND_URL = "http://localhost:3000"
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get(
            "DATABASE_URL",
            "sqlite:///dev.db"))


class ProductionConfig(Config):
    DEBUG = False
    PREFERRED_URL_SCHEME = "https"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = (
        "sqlite:///:memory:")
    JWT_SECRET_KEY = "test-only"
    SECRET_KEY = "test-only"
    SQLALCHEMY_ENGINE_OPTIONS = {}


# THIS DICT IS WHAT app.py NEEDS
config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     ProductionConfig,
}
