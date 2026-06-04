# wsgi.py - ChurchOS WSGI entry point
import os
from app import create_app

config_name = os.environ.get(
    "FLASK_ENV", "production")

config_map = {
    "development": "config.DevelopmentConfig",
    "production":  "config.ProductionConfig",
    "testing":     "config.TestingConfig",
}

app = create_app(
    config_map.get(
        config_name,
        "config.ProductionConfig"))


@app.teardown_appcontext
def shutdown_session(exception=None):
    from extensions import db
    db.session.remove()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
