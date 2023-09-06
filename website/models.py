from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func



class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=False)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))

class Schedule(db.Model):
    schedulenum = db.Column(db.String(150), primary_key=True)
    gamenum = db.Column(db.Integer, unique=True)
    date = db.Column(db.String(200), unique=False)
    day = db.Column(db.String(200), unique=False)
    away_team = db.Column(db.String(200), unique=True)
    home_team = db.Column(db.String(200), unique=True)





