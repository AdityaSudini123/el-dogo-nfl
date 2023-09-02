from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from pymongo import MongoClient

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    with app.app_context():
        app.config['SECRET_KEY'] = "helloworld"
        app.config['SESSION_PERMANENT'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///database.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)

        from .views import views
        from .auth import auth

        app.register_blueprint(views, url_prefix="/")
        app.register_blueprint(auth, url_prefix="/")

        from .models import User
        create_database(app)

        login_manager = LoginManager()
        login_manager.login_view = "auth.login"
        login_manager.init_app(app)

        @login_manager.user_loader
        def load_user(id):
            user_data = User.query.get(int(id))
            return user_data
    return app

def create_database(app):
    if not path.exists("website/database.db"):
        db.create_all(app=app)
        print("Created database!")