import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from config import Config

from flask_login import LoginManager

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

def create_app():
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    from app import models

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        from flask import flash, redirect, request, url_for

        flash("Your session expired or the form was invalid. Please try again.", "danger")
        return redirect(request.referrer or url_for("main.login"))

    from app.routes import main
    csrf.exempt(main)
    app.register_blueprint(main)

    try:
        from app.doctor_routes import doctors
        app.register_blueprint(doctors)
    except ImportError:
        pass

    try:
        from app.medicine_routes import medicines
        app.register_blueprint(medicines)
    except ImportError:
        pass

    try:
        from app.patient_routes import patients
        app.register_blueprint(patients)
    except ImportError:
        pass

    return app
