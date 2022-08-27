import csv
from pymongo import MongoClient
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
import website.scraper
from . import db
from website.models import User
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from website.scraper import schedule_scraper, result_scraper
import sqlite3 as sl
import pandas as pd

cluster = MongoClient('mongodb+srv://AdityaSudini:Harry_Potter12345@cluster0.gsst9ye.mongodb.net/?retryWrites=true&w=majority')
mongoDB = cluster["MaxJules"]
schedule_collection = mongoDB["weekly_schedule"]
results_collection = mongoDB["weekly_results"]
user_data_collection = mongoDB["user_data"]
user_picks_collection = mongoDB["user_weekly_picks"]

auth = Blueprint("auth", __name__)

@auth.route("/main", methods=['GET', 'POST'])
def main():
    return render_template('main.html')

@auth.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")

        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            if check_password_hash(user_exists.password, password):
                flash('Logged in successfully!', category='success')
                login_user(user_exists, remember=True)
                print(current_user.username)
                return redirect(url_for('views.home'))

        else:
            flash('Email does not exist.', category='error')

    return render_template("login.html")


@auth.route("/sign-up", methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get("email")
        username = request.form.get("username")
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")

        email_exists = User.query.filter_by(email=email).first()
        username_exists = User.query.filter_by(username=username).first()

        if email_exists:
            flash('Email is already in use.', category='error')
        elif username_exists:
            flash('Username is already in use.', category='error')
        elif password1 != password2:
            flash('Password don\'t match!', category='error')
        elif len(username) < 2:
            flash('Username is too short.', category='error')
        elif len(password1) < 6:
            flash('Password is too short.', category='error')
        elif len(email) < 4:
            flash("Email is invalid.", category='error')
        else:
            new_user_mongodb = {
                "_id": username,
                "email": email,
                "password": generate_password_hash(password1, method="sha256")
            }
            user_data_collection.insert_one(new_user_mongodb)

            new_user = User(email=email, username=username, password=generate_password_hash(
                password1, method='sha256'))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('User created!')
            return redirect(url_for('views.home'))
    return render_template("signup.html")

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("views.home"))

@auth.route("/select_picks", methods=['GET', 'POST'])
@login_required
def select_picks():
    weekly_schedule = mongoDB['current_week'].find_one({'_id': 'schedule'})
    week_number = weekly_schedule['week_number']
    weekly_schedule.pop("_id")
    weekly_schedule.pop("week_number")
    home_teams = []
    away_teams = []
    game_day = []
    teams = []
    for item in weekly_schedule.items():
        teams.append(item[1])
    for team in teams:
        home_teams.append(team[0])
        away_teams.append(team[1])

    entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})

    if request.method == 'POST':
        if not entry_exists:
            player_entry = {}
            for i in range(len(home_teams)):
                # home_teams[i] refers to winner via the fixture number in the index
                game_winner = request.form.get(str(home_teams[i]))
                # away_teams[i] refers to the confidence number
                game_confidence = request.form.get(str(away_teams[i]))
                player_entry[game_winner] = game_confidence

            chosen_teams = []
            chosen_confidence = []
            for entry in player_entry.items():
                team = entry[0]
                confidence = entry[1]
                chosen_teams.append(team)
                chosen_confidence.append(confidence)
            new_entry = {"_id": current_user.username, "week_number": week_number, "winners": chosen_teams,
                         "confidence": chosen_confidence}
            mongoDB[f'week_{week_number}'].insert_one(new_entry)
            return redirect(url_for('views.home'))
        else:
            flash('You have already made your picks', category='error')
            return redirect(url_for('views.home'))

    return render_template("select_picks.html", name=current_user.email, home_teams=home_teams, away_teams=away_teams,
                             len=len(home_teams), week_number=week_number)

@auth.route("/scoresheet")
@login_required
def scoresheet():
    current_week_schedule = mongoDB['current_week'].find_one({'_id': 'schedule'})
    week_number = current_week_schedule['week_number']
    current_week_results = mongoDB['current_week'].find_one({'_id': 'results'})
    current_week_results = current_week_results['winners']
    winning_teams = []
    winning_team_scores = []
    for item in current_week_results.items():
        winning_teams.append(item[0])
        winning_team_scores.append(item[1])
    teams = []
    for item in current_week_schedule.values():
        teams.append(item)
    teams = teams[2:]

    home_teams = []
    away_teams = []
    for team in teams:
        home_teams.append(team[0])
        away_teams.append(team[1])
    all_teams = []
    for i in range(len(home_teams)):
        all_teams.append(home_teams[i])
        all_teams.append(away_teams[i])


    entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})

    while not entry_exists:
        flash('You must select your picks before viewing the score sheet', category='error')
        return redirect(
            url_for("auth.select_picks", name=current_user.email, home_teams=home_teams, away_teams=away_teams,
                    dates=dates, len=len(home_teams), week_number=week_number))
    if entry_exists:
        player_selections = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
        player_selections.pop('_id')
        player_selections.pop('week_number')

        teams_selected = player_selections['winners']
        confidence_entered = player_selections['confidence']

        player_picks = {}
        for i in range(len(teams_selected)):
            player_picks[teams_selected[i]] = confidence_entered[i]

        total = 0
        for i in range(len(winning_teams)):
            if teams_selected[i] == winning_teams[i]:
                total += int(player_picks[teams_selected[i]])

    html_code = mongoDB['current_week'].find_one({'_id': 'mastersheet'})
    html_code = html_code['html_code']
    code_len = len(html_code)

    return render_template('scoresheet.html', html_code=html_code, len=code_len)

@auth.route('/rules')
@login_required
def rules():

    return render_template('rules.html')

@auth.route('/archives')
@login_required
def archives():
    html_code = mongoDB['current_week'].find_one({'_id': 'mastersheet'})
    html_code = html_code['html_code']
    code_len = len(html_code)

    all_collection_names = mongoDB.list_collection_names()
    valid_collection_names = []
    for collection_name in all_collection_names:
        if collection_name not in ['user_weekly_picks', 'user_data', 'current_week']:
            valid_collection_names.append(collection_name)
    number_of_collections = len(valid_collection_names)


    return render_template('archives.html', html_code=html_code, len=code_len)

@auth.route('/contact')
def contact():
    return render_template('contact.html')