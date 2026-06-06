import os
from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from models import db, bcrypt, User, Church
from config import config
from datetime import datetime, timedelta

migrate = Migrate()
jwt = JWTManager()


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('FRONTEND_URL', '*'),
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    from routes.auth       import auth_bp
    from routes.members    import members_bp
    from routes.attendance import attendance_bp
    from routes.finance    import finance_bp
    from routes.events     import events_bp
    from routes.users      import users_bp
    from routes.dashboard  import dashboard_bp
    from routes.churches   import churches_bp
    app.register_blueprint(auth_bp,       url_prefix='/api/auth')
    app.register_blueprint(members_bp,    url_prefix='/api/members')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(finance_bp,    url_prefix='/api/finance')
    app.register_blueprint(events_bp,     url_prefix='/api/events')
    app.register_blueprint(users_bp,      url_prefix='/api/users')
    app.register_blueprint(dashboard_bp,  url_prefix='/api/dashboard')
    app.register_blueprint(churches_bp,   url_prefix='/api/churches')

    @jwt.expired_token_loader
    def expired(h, p):
        return jsonify({'error': 'Token expired', 'code': 'TOKEN_EXPIRED'}), 401

    @jwt.invalid_token_loader
    def invalid(e):
        return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401

    @jwt.unauthorized_loader
    def missing(e):
        return jsonify({'error': 'Token required', 'code': 'TOKEN_MISSING'}), 401

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'app': 'ChurchOS', 'version': '2.0.0'}), 200

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        from flask import send_from_directory
        build = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'build')
        if path and os.path.exists(os.path.join(build, path)):
            return send_from_directory(build, path)
        return send_from_directory(build, 'index.html')

    with app.app_context():
        db.create_all()
        _seed()
    return app


def _seed():
    church = Church.query.first()
    if not church:
        church = Church(
            name='Migosi Main Altar',
            county='Kisumu', sub_county='Kisumu Central',
            denomination='Full Gospel Churches of Kenya',
            size='Large (200-1,000 members)',
            member_prefix='CHR', subscription_plan='trial',
            trial_ends_at=datetime.utcnow() + timedelta(days=30),
            is_active=True
        )
        db.session.add(church)
        db.session.flush()
    if not User.query.filter_by(role='admin').first():
        admin = User(
            username='admin', email='admin@churchos.app',
            full_name='System Administrator', role='admin',
            church_id=church.id, is_active=True
        )
        admin.set_password('Admin@2026')
        db.session.add(admin)
    db.session.commit()
