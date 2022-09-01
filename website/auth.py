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
                home_confidence = []
                away_confidence = []
                for i in range(len(home_teams)):
                    home_confidence.append(request.form.get(f'home_team_{i}'))
                    # away_teams[i] refers to the confidence number
                    away_confidence.append(request.form.get(f'away_team_{i}'))
                    if home_confidence[i] != '0' and away_confidence[i] != '0':
                        flash(category='error', message='You cannot enter a value greater than 0 for both home and away teams')
                        return redirect(url_for('auth.select_picks'))
                teams_dict = {}
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
                             len=len(home_teams), week_number=week_number)

@auth.route("/mastersheet")
@login_required
def mastersheet():
    current_week_schedule = mongoDB['current_week'].find_one({'_id': 'schedule'})
    current_week_results = mongoDB['current_week'].find_one({'_id': 'results'})

    if not current_week_results:
        flash(category='error', message='Mastersheet not available yet')
        return redirect(url_for('views.home'))

    week_number = current_week_schedule['week_number']
    entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})
    if not entry_exists:
        flash('You must select your picks before viewing the score sheet', category='error')
        return redirect(
            url_for("auth.select_picks"))

    weekly_mastersheet = mongoDB['current_week'].find_one({'_id': 'mastersheet'})
    weekly_winner = weekly_mastersheet['weekly_winner']
    html_code = weekly_mastersheet['html_code']
    code_len = len(html_code)
    return render_template('mastersheet.html', html_code=html_code, len=code_len, weekly_winner=weekly_winner)

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

@auth.route('/master_archive_2', methods=['GET', 'POST'])
@login_required
def master_archive_2():
    master_exists = mongoDB['week_2'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_3', methods=['GET', 'POST'])
@login_required
def master_archive_3():
    master_exists = mongoDB['week_3'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_4', methods=['GET', 'POST'])
@login_required
def master_archive_4():
    master_exists = mongoDB['week_4'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_5', methods=['GET', 'POST'])
@login_required
def master_archive_5():
    master_exists = mongoDB['week_5'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_6', methods=['GET', 'POST'])
@login_required
def master_archive_6():
    master_exists = mongoDB['week_6'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_7', methods=['GET', 'POST'])
@login_required
def master_archive_7():
    master_exists = mongoDB['week_7'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_8', methods=['GET', 'POST'])
@login_required
def master_archive_8():
    master_exists = mongoDB['week_8'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_9', methods=['GET', 'POST'])
@login_required
def master_archive_9():
    master_exists = mongoDB['week_9'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_10', methods=['GET', 'POST'])
@login_required
def master_archive_10():
    master_exists = mongoDB['week_10'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_11', methods=['GET', 'POST'])
@login_required
def master_archive_11():
    master_exists = mongoDB['week_11'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_12', methods=['GET', 'POST'])
@login_required
def master_archive_12():
    master_exists = mongoDB['week_12'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_13', methods=['GET', 'POST'])
@login_required
def master_archive_13():
    master_exists = mongoDB['week_13'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_14', methods=['GET', 'POST'])
@login_required
def master_archive_14():
    master_exists = mongoDB['week_14'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_15', methods=['GET', 'POST'])
@login_required
def master_archive_15():
    master_exists = mongoDB['week_15'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_16', methods=['GET', 'POST'])
@login_required
def master_archive_16():
    master_exists = mongoDB['week_16'].find_one({'_id': 'mastersheet'})
    if master_exists:
        html_code = master_exists['html_code']

        return render_template('master_archive_1.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='Mastersheet is not available yet. Select a valid week number.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_17', methods=['GET', 'POST'])
@login_required
def master_archive_17():
    master_exists = mongoDB['week_17'].find_one({'_id': 'mastersheet'})
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

@auth.route('/personal_archive_2')
@login_required
def personal_archive_2():
    schedule = mongoDB['week_2'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_2'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_2'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_2.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_3')
@login_required
def personal_archive_3():
    schedule = mongoDB['week_3'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))
    results = mongoDB['week_3'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_3'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_3.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_4')
@login_required
def personal_archive_4():
    schedule = mongoDB['week_4'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_4'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_4'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_4.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_5')
@login_required
def personal_archive_5():
    schedule = mongoDB['week_5'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_5'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_5'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_5.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_6')
@login_required
def personal_archive_6():
    schedule = mongoDB['week_6'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_6'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_6'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_6.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_7')
@login_required
def personal_archive_7():
    schedule = mongoDB['week_7'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_7'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_7'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_7.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_8')
@login_required
def personal_archive_8():
    schedule = mongoDB['week_8'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_8'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_8'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_8.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_9')
@login_required
def personal_archive_9():
    schedule = mongoDB['week_9'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_9'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_9'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_9.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_10')
@login_required
def personal_archive_10():
    schedule = mongoDB['week_10'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_10'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_10'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_10.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_11')
@login_required
def personal_archive_11():
    schedule = mongoDB['week_11'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_11'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_11'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_11.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_12')
@login_required
def personal_archive_12():
    schedule = mongoDB['week_12'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_12'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_12'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_12.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_13')
@login_required
def personal_archive_13():
    schedule = mongoDB['week_13'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_13'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_13'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_13.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_14')
@login_required
def personal_archive_14():
    schedule = mongoDB['week_14'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_14'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_14'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_14.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_15')
@login_required
def personal_archive_15():
    schedule = mongoDB['week_15'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_15'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_15'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_15.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_16')
@login_required
def personal_archive_16():
    schedule = mongoDB['week_16'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_16'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_16'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_16.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_17')
@login_required
def personal_archive_17():
    schedule = mongoDB['week_17'].find_one({'_id': 'schedule'})
    all_games = []
    if schedule:
        for item in schedule.items():
            if 'game' in item[0]:
                all_games.append(item[1])
    else:
        flash(category='error', message='This week is not available to view yet')
        return redirect(url_for('views.home'))

    results = mongoDB['week_17'].find_one({'_id': 'results'})
    winners = []
    for item in results.items():
        if item[0] not in ['_id', 'week_number']:
            winners.append(item[1][1][0])
    results = winners

    player_selections = mongoDB['week_17'].find_one({'_id': current_user.username})
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

        return render_template('personal_archive_17.html', html_code=html_code, len=len(html_code))
    else:
        flash(category='error', message='You do not have an entry for this week')
        return redirect(url_for('views.home'))

@auth.route('/contact')
def contact():
    return render_template('contact.html')