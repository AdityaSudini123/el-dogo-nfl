import csv
import datetime
import pytz
import flask_login
import numpy
from pymongo import MongoClient
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, send_file
import website.scraper
from . import db
from website.models import User
from website.models import Schedule
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from website.scraper import schedule_scraper, result_scraper
import sqlite3 as sl
import pandas as pd


cluster = MongoClient('mongodb+srv://AdityaSudini:Harry_Potter12345@cluster0.gsst9ye.mongodb.net/?retryWrites=true&w=majority')
mongoDB = cluster["ElDogoPuzzler2023"]
schedule_collection = mongoDB["weekly_schedule"]
results_collection = mongoDB["weekly_results"]
user_data_collection = mongoDB["user_data"]
user_picks_collection = mongoDB["user_weekly_picks"]

auth = Blueprint("auth", __name__)

@login_required
@auth.route("/main", methods=['GET', 'POST'])
def main():
    return render_template('main.html')


@auth.route("/sign-up", methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email1 = request.form.get("email1")
        email2 = request.form.get("email2")
        username1 = request.form.get("username1")
        username2 = request.form.get("username2")
        password1 = request.form.get("password1")
        password2 = request.form.get("password2")
        # ID IS NOT USERNAME IN THE SQL ALCHEMY TABLE
        user_in_mongo = mongoDB['user_data'].find_one({'_id': username1})
        username_exists = User.query.filter_by(username=username1).first()

        if username_exists and user_in_mongo == None:
            # Deletes the user from the SQLAlchemy database as well, so that there is no error
            User.query.filter_by(username=username1).delete()
            if username1 != username2:
                flash('Please make sure that your username is entered correctly both times', category='error')
                return render_template("signup.html")
            elif email1 != email2:
                flash('Please make sure that your email is entered correctly both times', category='error')
                return render_template("signup.html")
            elif password1 != password2:
                flash('Please make sure that your passwords match', category='error')
                return render_template("signup.html")
            elif len(username1) < 2:
                flash('Username is too short', category='error')
                return render_template("signup.html")
            elif len(password1) < 6:
                flash('Password is too short', category='error')
                return render_template("signup.html")
            elif len(email1) < 4:
                flash('The email you entered seems too short to be a valid email', category='error')
                return render_template("signup.html")
            else:
                new_user_mongodb = {"_id": username1, "email": email1,
                                    "password": generate_password_hash(password1, method="sha256")}
                user_data_collection.insert_one(new_user_mongodb)

                new_user = User(email=email1, username=username1, password=generate_password_hash(
                    password1, method='sha256'))
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user, remember=False)
                flash('User created!')
                return redirect(url_for('views.home'))

        elif user_in_mongo:
            flash('Username is already in use.', category='error')
            return render_template("signup.html")
        elif username1 != username2:
            flash('Please make sure that your username is entered correctly both times', category='error')
            return render_template("signup.html")
        elif email1 != email2:
            flash('Please make sure that your email is entered correctly both times', category='error')
            return render_template("signup.html")
        elif password1 != password2:
            flash('Please make sure that your passwords match', category='error')
            return render_template("signup.html")
        elif len(username1) < 2:
            flash('Username is too short', category='error')
            return render_template("signup.html")
        elif len(password1) < 6:
            flash('Password is too short', category='error')
            return render_template("signup.html")
        elif len(email1) < 4:
            flash('The email you entered seems too short to be a valid email', category='error')
            return render_template("signup.html")
        else:
            new_user_mongodb = {"_id": username1, "email": email1, "password": generate_password_hash(password1, method="sha256")}
            user_data_collection.insert_one(new_user_mongodb)

            new_user = User(email=email1, username=username1, password=generate_password_hash(
                password1, method='sha256'))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=False)
            flash('User created!')
            return redirect(url_for('views.home'))
    return render_template("signup.html")

@auth.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")

        user_exists = User.query.filter_by(username=username).first()
        user_exists_in_mongo = mongoDB['user_data'].find_one({'_id': username})
        if user_exists_in_mongo:
            user_password = user_exists_in_mongo['password']
            if user_exists:
                if check_password_hash(user_password, password):
                    login_user(user_exists, remember=False)
                    return redirect(url_for('views.home'))
                if not check_password_hash(user_exists.password, password):
                    flash(category='error', message='Incorrect Password')
            elif not user_exists:
                if check_password_hash(user_exists_in_mongo['password'], password):
                    new_user = User(email=email, username=username, password=generate_password_hash(
                        password, method='sha256'))
                    db.session.add(new_user)
                    db.session.commit()
                    login_user(new_user, remember=False)
                    return redirect(url_for('views.home'))
                else:
                    flash(category='error', message='Your password was entered incorrectly. Please try again.')
        elif user_exists:
            if check_password_hash(user_exists.password, password):
                # flash(f'Current logged in as {username}', category='success')
                login_user(user_exists, remember=False)
                return redirect(url_for('views.home'))
            if not check_password_hash(user_exists.password, password):
                flash(category='error', message='Incorrect Password')
        else:
            flash('Username does not exist.', category='error')

    return render_template("login.html")

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("views.home"))

@auth.route('/rules', methods=['GET', 'POST'])
@login_required
def rules():
    return render_template('rules.html', username=current_user.username)

@auth.route("/select_picks", methods=['GET', 'POST'])
@login_required
def select_picks():
    pst = pytz.timezone('America/Los_Angeles')
    dt = datetime.datetime.now(pst)
    # Monday = 0, Tuesday = 1 and so on
    # if (dt.weekday() == 1 and dt.time() > datetime.time(19, 0, 0, 0, tzinfo=pytz.timezone('America/Los_Angeles'))):
    #     flash('Picks are currently closed', 'error')
    #     return redirect(url_for('views.home'))
    if dt.weekday() == 2 and dt.time() > datetime.time(19, 0, 0, 0, tzinfo=pytz.timezone('America/Los_Angeles')):
        flash('Picks are currently closed', 'error')
        return redirect(url_for('views.home'))
    elif dt.weekday() == 3:
        flash('Picks are currently closed', 'error')
        return redirect(url_for('views.home'))
    elif dt.weekday() == 4:
        flash('Picks are currently closed', 'error')
        return redirect(url_for('views.home'))
    elif dt.weekday() == 5:
        flash('Picks are currently closed', 'error')
        return redirect(url_for('views.home'))
    elif (dt.weekday() == 6 and dt.time() < datetime.time(19, 0, 0, 0, tzinfo=pytz.timezone('America/Los_Angeles'))):
        flash('Picks are currently closed', 'error')
        return redirect(url_for('views.home'))
    else:
        weekly_schedule = mongoDB['week_2'].find_one({'_id': 'schedule'})
        # week_number = weekly_schedule['week_number']
        week_number = 2
        entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})
        if entry_exists:
            flash('You have already submitted picks for this week', 'error')
            return redirect(url_for('views.home'))
        if weekly_schedule:
            home_teams = []
            away_teams = []
            game_days = []
            for i in range(1, len(weekly_schedule)-1):
                home_teams.append(weekly_schedule[f'game_{i}']['home team'])
                away_teams.append(weekly_schedule[f'game_{i}']['away team'])
                game_days.append(weekly_schedule[f'game_{i}']['day'])

            total_possible = 0
            for i in range(len(home_teams) + 1):
                total_possible += i

            possible_score = int(float(len(home_teams) / 2) * float(1 + len(home_teams)))

            teams_dict = {}
            if request.method == 'POST':
                # confirmuser = request.form.get("confirmuser")
                # if confirmuser != current_user.username:
                #     logout_user()
                #     flash('You were logged into someone else\'s account. Please login and try again.', 'error')
                #     return redirect(url_for('auth.login'))
                for i in range(len(home_teams)):
                    home_confidence = []
                    away_confidence = []
                    total_score = 0
                    for i in range(len(home_teams)):
                        confidence_home = request.form.get(f'home_team_{i}')
                        if confidence_home == '':
                            confidence_home = '0'
                            home_confidence.append(confidence_home)
                            total_score += int(confidence_home)
                        else:
                            home_confidence.append(confidence_home)
                        # away_teams[i] refers to the confidence number
                        confidence_away = request.form.get(f'away_team_{i}')
                        if confidence_away == '':
                            confidence_away = '0'
                            away_confidence.append(confidence_away)
                            total_score += int(confidence_away)
                        else:
                            away_confidence.append(confidence_away)

                    for i in range(len(home_confidence)):
                        if home_confidence[i] == '0':
                            if away_confidence[i] == '0':
                                flash(category='error', message='Your picks have not been submitted. Please review the rules and ensure your '
                                              'picks are entered correctly.')
                                return redirect(url_for('auth.select_picks'))
                        elif home_confidence[i] != '0':
                            if away_confidence[i] != '0':
                                flash(category='error', message='Your picks have not been submitted. Please review the rules and ensure your '
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
                    picks = list(winners_dict.values())
                    picks2 = ['']
                    for i in range(1, len(picks)+1):
                        picks2.append(picks[i-1])
                        if picks2[i] == picks2[i-1]:
                            flash('Your picks have not been submitted. Please review the rules and ensure your picks are entered correctly', 'error')
                            return redirect(url_for('auth.select_picks'))
                tie_breaker = request.form.get('tie_breaker')
                new_entry = {"_id": current_user.username, "week_number": week_number, "winners": list(winners_dict.keys()),
                             "confidence": list(winners_dict.values()), "tie_breaker": tie_breaker, 'time': datetime.datetime.now()}
                mongoDB[f'week_{week_number}'].insert_one(new_entry)
                flash(category='success', message='User verified and picks submitted!')
                return redirect(url_for('views.home'))
        if not weekly_schedule:
            flash(category='error', message='Schedule is not available yet')
            return redirect(url_for('views.home'))
    return render_template("select_picks_test.html", name=current_user.email, home_teams=home_teams, away_teams=away_teams,
                           len=len(home_teams), week_number=week_number, game_days=game_days, possible_score=possible_score,
                           total_possible=total_possible)

@auth.route('/download', methods=['GET', 'POST'])
def download():
    # if request.method == 'POST':
        # games = db.session.query(Schedule).filter_by(schedulenum='week1_1').first()
        # user = User.query.filter_by(username='current_user.username').first()
        # if games:
        #     print(games.date)

        # weeknumber = request.form.get('masternumber')
        # scheduleexists = mongoDB[f'week_{weeknumber}'].find_one({'_id': 'schedule'})
        # if scheduleexists:
        #     mydf = pd.DataFrame(scheduleexists)
        #     columns_to_drop = ['_id', 'week_number']
        #     mydf.drop(columns=columns_to_drop, inplace=True)
        #     columns = mydf.columns
        #     mydf2 = mydf.iloc[[0, 1, 3, 4], :].T
        #     numofgames = mydf2.shape[0]
        #     gamenums = []
        #     dates = []
        #     days = []
        #     away_teams = []
        #     home_teams = []
        #     for i in range(numofgames):
        #         schedulenum = f'week{weeknumber}_{i+1}'
        #         gamenum = i+1
        #         date = mydf2.iloc[i, 0]
        #         day = mydf2.iloc[i, 1]
        #         away_team = mydf2.iloc[i, 2]
        #         home_team = mydf2.iloc[i, 3]
        #         gamenums.append(gamenum)
        #         dates.append(date)
        #         days.append(day)
        #         away_teams.append(away_team)
        #         home_teams.append(home_team)
                # game = Schedule(schedulenum=schedulenum, gamenum=gamenum, date=date, day=day, away_team=away_team, home_team=home_team)
                # db.session.add(game)
                # db.session.commit()



            # mydict = mydf3.to_dict(orient='series')
            # print(mydict)
            # mydf4 = pd.DataFrame(mydict)
            # print(mydf4)
            # return render_template('download.html')
            # return send_file(excel_file, as_attachment=True)
        # else:
        #     flash('The mastersheet for the week you have entered is not availble yet', 'error')
        #     return render_template('download.html')
    return render_template('test.html')

@auth.route('/contact')
def contact():
    return render_template('contact.html')

@auth.route('/personal_archive_1')
@login_required
def personal_archive_1():
    player_picks = mongoDB['week_1'].find_one({'_id': current_user.username})
    if not player_picks:
        flash('You have not made picks for this week', 'error')
        return redirect(url_for('auth.select_picks'))

    weekly_schedule = mongoDB['week_1'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
    week_number = weekly_schedule['week_number']

    home_teams = []
    away_teams = []
    game_days = []
    for i in range(1, len(weekly_schedule)-1):
        home_teams.append(weekly_schedule[f'game_{i}']['home team'])
        away_teams.append(weekly_schedule[f'game_{i}']['away team'])
        game_days.append(weekly_schedule[f'game_{i}']['day'])

    if player_picks:
        winners = player_picks['winners']
        confidence = player_picks['confidence']
        tie_breaker = player_picks['tie_breaker']
        home_confidence = []
        away_confidence = []
        for i in range(len(home_teams)):
            if home_teams[i] in winners:
                home_confidence.append(confidence[i])
                away_confidence.append('0')
            elif away_teams[i] in winners:
                away_confidence.append(confidence[i])
                home_confidence.append('0')

    return render_template('personal_archive_1.html', len=len(home_teams), home_teams=home_teams,
                           away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker, username=current_user.username)


@auth.route("/mastersheet")
@login_required
def mastersheet():
    master_prelim = mongoDB['week_1'].find_one({'_id': 'master_prelim'})
    if master_prelim:
        master_prelim.pop('_id')
        mydf = pd.DataFrame(master_prelim)
        tableheads = list(mydf.columns)
        len_tableheads = len(tableheads)
        tablerows = []
        tablelen = mydf.shape[0]
        for i in range(tablelen):
            tablerows.append(list(mydf.iloc[i, :]))
        rowlen = len(tablerows[0])

        return render_template('mastersheet_test.html', tableheads=tableheads, len_tableheads=len_tableheads, tablelen=tablelen, tablerows=tablerows, rowlen=rowlen)
    else:
        flash(category='error', message='mastersheet is not available yet')
        return redirect(url_for('views.home'))

@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        user_exists = mongoDB['user_data'].find_one({'_id': username})
        if user_exists:
            if user_exists['email'] == email:
                flash(category='success', message='User validated')
                return redirect(url_for('auth.change_password'))
            else:
                flash(category='error', message='Email does not exist')
                return render_template('forgot_password.html')
        else:
            flash(category='error', message='Username does not exist')
            return render_template('login.html')
    return render_template('forgot_password.html')

@auth.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if len(new_password) < 7:
            flash(category='error', message='Password must be longer than 7 characters')
            return redirect(url_for('change_password'))
        elif new_password != confirm_password:
            flash(category='error', message='Passwords do not match')
        else:
            password = generate_password_hash(password=new_password, method='sha256')
            update = {"$set": {"password": password}}
            mongoDB['user_data'].update_one({'_id': username}, update=update)
            flash(category='success', message='Password succesfully changed')
            return redirect(url_for('auth.login'))
    return render_template('change_password.html')



