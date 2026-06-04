import os
from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from models import db, bcrypt, User
from config import config

migrate = Migrate()
jwt = JWTManager()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Extensions
    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config.get('FRONTEND_URL', '*'),
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Register blueprints
    from routes.auth import auth_bp
    from routes.members import members_bp
    from routes.attendance import attendance_bp
    from routes.finance import finance_bp
    from routes.events import events_bp
    from routes.users import users_bp
    from routes.dashboard import dashboard_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(members_bp, url_prefix='/api/members')
    app.register_blueprint(attendance_bp, url_prefix='/api/attendance')
    app.register_blueprint(finance_bp, url_prefix='/api/finance')
    app.register_blueprint(events_bp, url_prefix='/api/events')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired', 'code': 'TOKEN_EXPIRED'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token', 'code': 'INVALID_TOKEN'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization token required', 'code': 'TOKEN_MISSING'}), 401

    # Health check
    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'app': 'ChurchOS', 'version': '2.0.0'}), 200

    # Serve React frontend in production
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        import os
        from flask import send_from_directory
        build_dir = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'build')
        if path and os.path.exists(os.path.join(build_dir, path)):
            return send_from_directory(build_dir, path)
        return send_from_directory(build_dir, 'index.html')

    # Create tables and seed admin
    with app.app_context():
        db.create_all()
        _seed_admin()

    return app


def _seed_admin():
    """Create default admin user if none exists."""
    if not User.query.filter_by(role='admin').first():
        admin = User(
            username='admin',
            email='admin@mrh.church',
            full_name='System Administrator',
            role='admin',
            is_active=True
        )
        admin.set_password('Admin@2026')
        db.session.add(admin)
        db.session.commit()
        print('✅ Default admin created: admin / Admin@2026')
