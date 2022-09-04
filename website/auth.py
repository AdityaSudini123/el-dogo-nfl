import csv
import numpy
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
        username = request.form.get("username")

        user_exists = User.query.filter_by(username=username).first()
        user_exists_in_mongo = mongoDB['user_data'].find_one({'_id': username})
        if user_exists:
            if check_password_hash(user_exists.password, password):
                flash(f'Logged in as {username}', category='success')
                login_user(user_exists, remember=True)
                return redirect(url_for('views.home'))
            if not check_password_hash(user_exists.password, password):
                flash(category='error', message='Incorrect Password')
        elif not user_exists:
            if user_exists_in_mongo:
                if check_password_hash(user_exists_in_mongo['password'], password):
                    new_user = User(email=email, username=username, password=generate_password_hash(
                        password, method='sha256'))
                    db.session.add(new_user)
                    db.session.commit()
                    login_user(new_user, remember=True)
                    flash(category='success', message=f'Logged in as {username}')
                    return redirect(url_for('views.home'))
                else:
                    flash(category='error', message='Your password was entered incorrectly. Please try again.')
            else:
                flash('Username does not exist.', category='error')

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
            flash('Passwords don\'t match!', category='error')
        elif len(username) < 2:
            flash('Username is too short.', category='error')
        elif len(password1) < 6:
            flash('Password is too short.', category='error')
        elif len(email) < 4:
            return render_template("signup.html")
        else:
            new_user_mongodb = {"_id": username, "email": email, "password": generate_password_hash(password1, method="sha256")}
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

@auth.route('/rules', methods=['GET', 'POST'])
@login_required
def rules():
    return render_template('rules.html')

@auth.route("/select_picks", methods=['GET', 'POST'])
@login_required
def select_picks():
    weekly_schedule = mongoDB['current_week'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Schedule is not available yet')
        return redirect(url_for('views.home'))

    week_number = weekly_schedule['week_number']
    weekly_schedule.pop("_id")
    weekly_schedule.pop("week_number")
    home_teams = []
    away_teams = []
    game_days = []
    teams = []
    for item in weekly_schedule.items():
        teams.append(item[1])
    for team in teams:
        print(team)
        home_teams.append(team[0])
        away_teams.append(team[1])
        game_days.append(team[2])

    possible_score = int(float(len(home_teams) / 2) * float(1 + len(home_teams)))
    entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})
    teams_dict = {}
    if request.method == 'POST':
        if not entry_exists:
            player_entry = {}
            for i in range(len(home_teams)):
                all_confidence = []
                home_confidence = []
                away_confidence = []
                total_score = 0
                for i in range(len(home_teams)):
                    confidence_home = request.form.get(f'home_team_{i}')
                    if confidence_home == '':
                        home_confidence.append('0')
                    else:
                        home_confidence.append(confidence_home)
                        all_confidence.append(confidence_home)
                        total_score += int(confidence_home)
                    # away_teams[i] refers to the confidence number
                    confidence_away = request.form.get(f'away_team_{i}')
                    if confidence_away == '':
                        away_confidence.append('0')
                    else:
                        away_confidence.append(confidence_away)
                        all_confidence.append(confidence_away)
                        total_score += int(confidence_away)

                if len(all_confidence) != len(set(all_confidence)):
                    flash(category='error', message='Your picks have not been submitted. Please review the rules and ensure your '
                                          'picks are entered correctly.')
                    return redirect(url_for('auth.select_picks'))

                for i in range(len(home_confidence)):
                    if home_confidence[i] == '0':
                        if away_confidence[i] == '0':
                            flash(category='error',
                                  message='Your picks have not been submitted. Please review the rules and ensure your '
                                          'picks are entered correctly.')
                            return redirect(url_for('auth.select_picks'))
                    elif home_confidence[i] != '0':
                        if away_confidence[i] != '0':
                            flash(category='error',
                                  message='Your picks have not been submitted. Please review the rules and ensure your '
                                          'picks are entered correctly.')
                            return redirect(url_for('auth.select_picks'))
                if total_score > possible_score:
                    flash(category='error', message='Your picks have not been submitted. Please review the rules and ensure your '
                                          'picks are entered correctly.')
                    return redirect(url_for('auth.select_picks'))

                for i in range(len(home_teams)):
                    teams_dict[home_teams[i]] = home_confidence[i]
                    teams_dict[away_teams[i]] = away_confidence[i]
                winners_dict = {}
                for item in teams_dict.items():
                    if item[1] != '0':
                        winners_dict[item[0]] = item[1]
            tie_breaker = request.form.get('tie_breaker')
            new_entry = {"_id": current_user.username, "week_number": week_number, "winners": list(winners_dict.keys()),
                         "confidence": list(winners_dict.values()), "tie_breaker": tie_breaker}
            mongoDB[f'week_{week_number}'].insert_one(new_entry)
            flash(category='success', message='Congrats! Your picks for the week have been submitted')
            return redirect(url_for('views.home'))
        else:
            flash('You have already made your picks', category='error')
            return redirect(url_for('views.home'))

    return render_template("select_picks.html", name=current_user.email, home_teams=home_teams, away_teams=away_teams,
                           len=len(home_teams), week_number=week_number, game_days=game_days, possible_score=possible_score)

@auth.route("/mastersheet")
@login_required
def mastersheet():
    masterhseet_exists = mongoDB['current_week'].find_one({'_id': 'mastersheet'})
    if not masterhseet_exists:
        flash(category='error', message='Mastersheet is not yet available')
        return redirect(url_for('views.home'))
    table_rows_new = masterhseet_exists['table_rows_new']
    table_len = masterhseet_exists['table_len']
    submitted_ids_sorted = masterhseet_exists['submitted_ids_sorted']
    id_len = masterhseet_exists['id_len']
    player_totals = masterhseet_exists['player_totals']
    tie_breakers = masterhseet_exists['tie_breakers']
    winning_player = masterhseet_exists['winning_player']

    return render_template('mastersheet.html', table_rows_new=table_rows_new, table_len=table_len,
                           user_ids=submitted_ids_sorted, id_len=id_len, player_totals=player_totals,
                           tie_breakers=tie_breakers, winning_player=winning_player)

@auth.route('/master_archive_1', methods=['GET', 'POST'])
@login_required
def master_archive_1():
    master_exists = mongoDB['week_1'].find_one({'_id': 'mastersheet'})
    if master_exists:
        table_rows_new = master_exists['table_rows_new']
        table_len = master_exists['table_len']
        submitted_ids_sorted = master_exists['submitted_ids_sorted']
        id_len = master_exists['id_len']
        player_totals = master_exists['player_totals']
        tie_breakers = master_exists['tie_breakers']

        return render_template('master_archive_1.html', table_rows_new=table_rows_new, table_len=table_len,
                               user_ids=submitted_ids_sorted, id_len=id_len, player_totals=player_totals,
                               tie_breakers=tie_breakers)
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_1')
@login_required
def personal_archive_1():
    schedule = mongoDB['week_1'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_1'].find_one({'_id': 'results'})
    if not results:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_1'].find_one({'_id': current_user.username})
    if player_selections:
        teams_selected = player_selections['winners']
        confidence = player_selections['confidence']
        pd.set_option('display.max_columns', None)
        myDF = pd.DataFrame()
        myDF['Matchup'] = all_games
        myDF['Your selection'] = teams_selected
        myDF['Confidence Assigned'] = confidence
        myDF['Outcome'] = results
        points_collected = []
        total = 0
        for i in range(len(teams_selected)):
            if teams_selected[i] == results[i]:
                total += int(confidence[i])
                points_collected.append(f'+{confidence[i]}')
            else:
                points_collected.append('+0')
        myDF['Points collected'] = points_collected
        html_code = myDF.to_html()
        html_code = html_code.split('\n')

        return render_template('personal_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/contact')
def contact():
    return render_template('contact.html')


