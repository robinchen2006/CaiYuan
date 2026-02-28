from flask import Flask, session
import os
import logging
from logging.handlers import RotatingFileHandler
from database import init_db, close_db
from routes.auth import auth_bp
from routes.main import main_bp
from routes.admin import admin_bp
from routes.notes import notes_bp
from routes.upload import upload_bp

def create_app():
    app = Flask(__name__)
    app.secret_key = 'your-secret-key-change-in-production'
    app.config['UPLOAD_FOLDER'] = 'static/uploads'
    app.config['UPLOAD_TEMP_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max request size

    # Configure logging
    if not os.path.exists('logs'):
        os.makedirs('logs', exist_ok=True)

    file_handler = RotatingFileHandler('logs/caiyuan.log', maxBytes=102400, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('CaiYuan startup')

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['UPLOAD_TEMP_FOLDER'], exist_ok=True)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(notes_bp, url_prefix='/api')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    
    # Register teardown
    app.teardown_appcontext(close_db)

    # Context processor to make session available to all templates (though it usually is)
    @app.context_processor
    def inject_user():
        return dict(session=session)

    init_db(app)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=False, host='0.0.0.0', port=5000)
