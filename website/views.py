from flask import Blueprint, render_template
from flask_login import login_required, current_user
from website.scraper import schedule_scraper

views = Blueprint("views", __name__)

@views.route("/")
@views.route("/home")
@login_required
def home():
    return render_template("home.html", name=current_user.username)
