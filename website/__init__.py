from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from pymongo import MongoClient
from flask_apscheduler import APScheduler

db = SQLAlchemy()

class Config:
    SCHEDULER_API_ENABLED = True

def create_app():
    app = Flask(__name__)
    with app.app_context():

        app.config['SECRET_KEY'] = "helloworld"
        app.config['SESSION_PERMANENT'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///database.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        app.config.from_object(Config())
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()

        db.init_app(app)

        from .views import views
        from .auth_test import auth

        app.register_blueprint(views, url_prefix="/")
        app.register_blueprint(auth, url_prefix="/")

        from .models import User
        from .models import Schedule
        create_database(app)

        login_manager = LoginManager()
        login_manager.login_view = "auth.login"
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(id):
            user_data = User.query.get(int(id))
            return user_data
    return app, scheduler

def create_database(app):
    if not path.exists("website/database.db"):
        db.create_all(app=app)
        print("Created database!")