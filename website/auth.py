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
        if user_exists:
            if check_password_hash(user_exists.password, password):
                flash(f'Logged in as {username}', category='success')
                login_user(user_exists, remember=True)
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
        home_teams.append(team[0])
        away_teams.append(team[1])
        game_days.append(team[2])

    possible_score = int(float(len(home_teams)/2)*float(1 + len(home_teams)))
    entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})
    teams_dict = {}
    if request.method == 'POST':
        if not entry_exists:
            player_entry = {}
            for i in range(len(home_teams)):
                home_confidence = []
                away_confidence = []
                total_score = 0
                for i in range(len(home_teams)):
                    confidence_home =request.form.get(f'home_team_{i}')
                    home_confidence.append(confidence_home)
                    total_score += int(confidence_home)
                    # away_teams[i] refers to the confidence number
                    confidence_away = request.form.get(f'away_team_{i}')
                    away_confidence.append(confidence_away)
                    total_score += int(confidence_away)
                    if home_confidence[i] != '0' and away_confidence[i] != '0':
                        flash(category='error', message='You cannot enter a value greater than 0 for both home and away teams')
                        return redirect(url_for('auth.select_picks'))

                if total_score > possible_score:
                    flash(category='error', message='please re-enter your picks')
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
            return redirect(url_for('views.home'))
        else:
            flash('You have already made your picks', category='error')
            return redirect(url_for('views.home'))

    return render_template("select_picks.html", name=current_user.email, home_teams=home_teams, away_teams=away_teams,
                             len=len(home_teams), week_number=week_number, game_days=game_days)

@auth.route("/mastersheet")
@login_required
def mastersheet():
    current_week = mongoDB['current_week'].find_one({'_id': 'schedule'})
    week_number = current_week['week_number']
    current_week.pop('_id')
    current_week.pop('week_number')

    results = mongoDB['current_week'].find_one({'_id': 'results'})
    results.pop('_id')
    winners = []
    for result in results.items():
        winners.append(result[1][1][0])

    team_list = []
    for item in current_week.items():
        teams = item[1]
        team_names = teams[0:2]
        team_list.append(team_names)
    new_list = []
    for item in team_list:
        for i in item:
            new_list.append(i)
    team_list = new_list
    team_list.append('TOTAL')
    team_list.append('TIE-BREAKER')

    current_week_documents = mongoDB[f'week_{week_number}'].find()
    submitted_ids = []
    user_documents = []
    for document in current_week_documents:
        if document['_id'] not in ['schedule', 'results', 'mastersheet']:
            user_documents.append(document)
            submitted_ids.append(document['_id'])

    users = []
    selected_winners = []
    confidence = []
    tie_breakers = []
    for document in user_documents:
        users.append(document['_id'])
        selected_winners.append(document['winners'])
        confidence.append(document['confidence'])
        tie_breakers.append(document['tie_breaker'])

    player_totals = []
    for i in range(len(selected_winners)):
        player_total = 0
        for team in selected_winners[i]:
            if team in winners:
                player_total += int(confidence[i][selected_winners[i].index(team)])
        player_totals.append(player_total)

    submitted_ids_sorted = sorted(submitted_ids, key=str.lower)
    submitted_ids_sorted.insert(0, '')
    user_documents_sorted = sorted(user_documents, key=lambda d: d['_id'].lower())

    table_rows = []
    for i in range(len(team_list)-2):
        row = []
        team = team_list[0:-2][i]
        row.append(team)
        for doc in user_documents_sorted:
            confidence_counter = 0
            if team in doc['winners']:
                row.append(doc['confidence'][confidence_counter])
                confidence_counter += 1
            else:
                row.append('0')
        table_rows.append(row)
    table_len = int(len(table_rows)/2)
    id_len = len(submitted_ids_sorted)

    away_teams = table_rows[1::2]
    home_teams = table_rows[::2]
    table_rows_new = []
    for i in range(len(home_teams)):
        table_rows_new.append([away_teams[i], home_teams[i]])

    player_totals.insert(0, 'TOTAL')
    tie_breakers.insert(0, 'TIE-BREAKER')

    return render_template('mastersheet.html', table_rows_new=table_rows_new, table_len=table_len,
                           user_ids=submitted_ids_sorted, id_len=id_len, player_totals=player_totals,
                           tie_breakers=tie_breakers)


    # current_week_schedule = mongoDB['current_week'].find_one({'_id': 'schedule'})
    # current_week_results = mongoDB['current_week'].find_one({'_id': 'results'})
    #
    # if not current_week_results:
    #     flash(category='error', message='Mastersheet not available yet')
    #     return redirect(url_for('views.home'))
    #
    # week_number = current_week_schedule['week_number']
    # entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})
    # if not entry_exists:
    #     flash('You must select your picks before viewing the score sheet', category='error')
    #     return redirect(
    #         url_for("auth.select_picks"))
    #
    # weekly_mastersheet = mongoDB['current_week'].find_one({'_id': 'mastersheet'})
    # weekly_winner = weekly_mastersheet['weekly_winner']
    # html_code = weekly_mastersheet['html_code']
    # code_len = len(html_code)
    # return render_template('mastersheet.html', html_code=html_code, len=code_len, weekly_winner=weekly_winner)
    # html code:
    # {% for i in range(0, len) %}
    #     {{html_code[i] | safe}}
    # {% endfor %}
    # <br>
    # <h3>This weeks winner: {{weekly_winner}}</h3>

@auth.route('/master_archive_1', methods=['GET', 'POST'])
@login_required
def master_archive_1():
    master_exists = mongoDB['week_1'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
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