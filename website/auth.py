import csv
import datetime

import flask_login
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
        if user_exists_in_mongo:
            user_password = user_exists_in_mongo['password']
            if user_exists:
                if check_password_hash(user_password, password):
                    login_user(user_exists, remember=True)
                    flash(f'Current logged in as {username}', category='success')
                    return redirect(url_for('views.home'))
                if not check_password_hash(user_exists.password, password):
                    flash(category='error', message='Incorrect Password')
            elif not user_exists:
                if check_password_hash(user_exists_in_mongo['password'], password):
                    new_user = User(email=email, username=username, password=generate_password_hash(
                        password, method='sha256'))
                    db.session.add(new_user)
                    db.session.commit()
                    login_user(new_user, remember=True)
                    flash(f'Current logged in as {username}', category='success')
                    return redirect(url_for('views.home'))
                else:
                    flash(category='error', message='Your password was entered incorrectly. Please try again.')
        elif user_exists:
            if check_password_hash(user_exists.password, password):
                flash(f'Current logged in as {username}', category='success')
                login_user(user_exists, remember=True)
                return redirect(url_for('views.home'))
            if not check_password_hash(user_exists.password, password):
                flash(category='error', message='Incorrect Password')
        else:
            flash('Username does not exist.', category='error')

    return render_template("login.html")


@auth.route("/sign-up", methods=['GET', 'POST'])
def sign_up():
    # if request.method == 'POST':
    #     email = request.form.get("email")
    #     username = request.form.get("username")
    #     password1 = request.form.get("password1")
    #     password2 = request.form.get("password2")
    #
    #     email_exists = User.query.filter_by(email=email).first()
    #     username_exists = User.query.filter_by(username=username).first()
    #     user_mongo = mongoDB['user_data'].find_one({'_id': username})
    #
    #     if email_exists:
    #         if user_mongo:
    #             if user_mongo['email'] == email:
    #                 flash('Email is already in use.', category='error')
    #     elif username_exists:
    #         if user_mongo:
    #             if user_mongo['_id'] == username:
    #                 flash('Username is already in use.', category='error')
    #     elif password1 != password2:
    #         flash('Passwords don\'t match!', category='error')
    #     elif len(username) < 2:
    #         flash('Username is too short.', category='error')
    #     elif len(password1) < 6:
    #         flash('Password is too short.', category='error')
    #     elif len(email) < 4:
    #         return render_template("signup.html")
    #     else:
    #         new_user_mongodb = {"_id": username, "email": email, "password": generate_password_hash(password1, method="sha256")}
    #         user_data_collection.insert_one(new_user_mongodb)
    #
    #         new_user = User(email=email, username=username, password=generate_password_hash(
    #             password1, method='sha256'))
    #         db.session.add(new_user)
    #         db.session.commit()
    #         login_user(new_user, remember=True)
    #         flash('User created!')
    #         return redirect(url_for('views.home'))
    # return render_template("signup.html")
    flash(category='error', message='Sign ups are closed. Please login if you have an account, or try to sign up next season.')
    return redirect(url_for('auth.login'))


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
@flask_login.fresh_login_required
def select_picks():
    # flash(category='error', message='Picks are now closed')
    # return redirect(url_for('views.home'))
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

    total_possible = 0
    for i in range(len(home_teams) + 1):
        total_possible += i

    possible_score = int(float(len(home_teams) / 2) * float(1 + len(home_teams)))
    entry_exists = mongoDB[f'week_{week_number}'].find_one({"_id": current_user.username})
    teams_dict = {}
    if request.method == 'POST':
        if entry_exists:
            flash('You have already made your picks', category='error')
            return redirect(url_for('views.home'))
        else:
            player_entry = {}
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
                            print('2')
                            flash(category='error',
                                  message='Your picks have not been submitted. Please review the rules and ensure your '
                                          'picks are entered correctly.')
                            return redirect(url_for('auth.select_picks'))
                    elif home_confidence[i] != '0':
                        if away_confidence[i] != '0':
                            print('3')
                            flash(category='error',
                                  message='Your picks have not been submitted. Please review the rules and ensure your '
                                          'picks are entered correctly.')
                            return redirect(url_for('auth.select_picks'))
                if total_score > possible_score:
                    print('4')
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
                         "confidence": list(winners_dict.values()), "tie_breaker": tie_breaker, 'time': datetime.datetime.now()}
            mongoDB[f'week_{week_number}'].insert_one(new_entry)
            flash(category='success', message='Congrats! Your picks for the week have been submitted')
            return redirect(url_for('views.home'))
    return render_template("select_picks.html", name=current_user.email, home_teams=home_teams, away_teams=away_teams,
                           len=len(home_teams), week_number=week_number, game_days=game_days, possible_score=possible_score,
                           total_possible=total_possible)

# @auth.route("/mastersheet")
# @login_required
# def mastersheet():
#     masterhseet_exists = mongoDB['current_week'].find_one({'_id': 'mastersheet'})
#     prelim_master_exists = mongoDB['current_week'].find_one({'_id': 'prelim_mastersheet'})
#
#     if  masterhseet_exists:
#         table_rows_new = masterhseet_exists['table_rows_new']
#         table_len = masterhseet_exists['table_len']
#         submitted_ids_sorted = masterhseet_exists['submitted_ids_sorted']
#         id_len = masterhseet_exists['id_len']
#         player_totals = masterhseet_exists['player_totals']
#         tie_breakers = masterhseet_exists['tie_breakers']
#         winning_player = masterhseet_exists['winning_player']
#         return render_template('mastersheet(old).html', table_rows_new=table_rows_new, table_len=table_len,
#                            user_ids=submitted_ids_sorted, id_len=id_len, player_totals=player_totals,
#                            tie_breakers=tie_breakers, winning_player=winning_player)
#     elif prelim_master_exists:
#         table_rows_new = prelim_master_exists['table_rows_new']
#         row_len = len(table_rows_new[0][0])
#         submitted_ids_sorted = prelim_master_exists['user_ids']
#         submitted_ids_sorted.insert(0, f'Week 1')
#
#         id_len = prelim_master_exists['id_len']
#         return render_template('prelim_mastersheet.html', table_rows_new=table_rows_new,
#                            user_ids=submitted_ids_sorted, id_len=id_len, row_len=row_len)
#     else:
#         flash(category='error', message='Mastersheet is not yet available')
#         return redirect(url_for('views.home'))

@auth.route('/contact')
def contact():
    return render_template('contact.html')

@auth.route('/master_archive_1', methods=['GET', 'POST'])
@login_required
def master_archive_1():
    final_exists = mongoDB['week_1'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 1')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_1.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_2', methods=['GET', 'POST'])
@login_required
def master_archive_2():
    final_exists = mongoDB['week_2'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 2')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_1.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_3', methods=['GET', 'POST'])
@login_required
def master_archive_3():
    final_exists = mongoDB['week_3'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 3')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_1.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_4', methods=['GET', 'POST'])
@login_required
def master_archive_4():
    final_exists = mongoDB['week_4'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 4')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_1.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_5', methods=['GET', 'POST'])
@login_required
def master_archive_5():
    final_exists = mongoDB['week_5'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 5')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_1.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_6', methods=['GET', 'POST'])
@login_required
def master_archive_6():
    final_exists = mongoDB['week_6'].find_one('final_master')
    week_6_schedule = mongoDB['week_6'].find_one({'_id': 'schedule'})
    number_of_games = len(week_6_schedule) - 2
    total_possible = sum(range(number_of_games + 1))
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 6')
        tie_breaker_index = str(len(column_1) - 1)
        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            deduction = total_possible - result[1][1]
            message = f'Winner was {result[1][0]} with {result[1][1]} points (-{deduction})'
        return render_template('master_archive_6.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_7', methods=['GET', 'POST'])
@login_required
def master_archive_7():
    final_exists = mongoDB['week_7'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 7')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_7.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_8', methods=['GET', 'POST'])
@login_required
def master_archive_8():
    final_exists = mongoDB['week_8'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 8')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_8.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_9', methods=['GET', 'POST'])
@login_required
def master_archive_9():
    final_exists = mongoDB['week_9'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 9')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_9.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_10', methods=['GET', 'POST'])
@login_required
def master_archive_10():
    final_exists = mongoDB['week_10'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 10')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_10.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_11', methods=['GET', 'POST'])
@login_required
def master_archive_11():
    final_exists = mongoDB['week_11'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 11')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_11.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_12', methods=['GET', 'POST'])
@login_required
def master_archive_12():
    final_exists = mongoDB['week_12'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 12')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_12.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_13', methods=['GET', 'POST'])
@login_required
def master_archive_13():
    final_exists = mongoDB['week_13'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 13')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_13.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_14', methods=['GET', 'POST'])
@login_required
def master_archive_14():
    final_exists = mongoDB['week_14'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 14')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_14.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_15', methods=['GET', 'POST'])
@login_required
def master_archive_15():
    final_exists = mongoDB['week_15'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 15')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_15.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_16', methods=['GET', 'POST'])
@login_required
def master_archive_16():
    final_exists = mongoDB['week_16'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 16')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This week\'s winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_1.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/master_archive_17', methods=['GET', 'POST'])
@login_required
def master_archive_17():
    final_exists = mongoDB['week_17'].find_one('final_master')
    if final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        column_headers.insert(0, 'Week 17')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            message = f'This weeks winner is {result[1][0]} with {result[1][1]} points'
        return render_template('master_archive_17.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
    else:
        flash(category='error', message='Mastersheet is not available yet.')
        return redirect(url_for('views.home'))

@auth.route('/personal_archive_1')
@login_required
def personal_archive_1():
    weekly_schedule = mongoDB['week_1'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
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
    player_picks = mongoDB['week_1'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template('personal_archive_1.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_2')
@login_required
def personal_archive_2():
    weekly_schedule = mongoDB['week_2'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
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
    player_picks = mongoDB['week_2'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template('personal_archive_2.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_3')
@login_required
def personal_archive_3():
    # week_number = 3
    # weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    # if not weekly_schedule:
    #     flash(category='error', message='Archive is not available yet')
    #     return redirect(url_for('views.home'))
    # weekly_schedule.pop("_id")
    # weekly_schedule.pop("week_number")
    # home_teams = []
    # away_teams = []
    # game_days = []
    # teams = []
    # for item in weekly_schedule.items():
    #     teams.append(item[1])
    # for team in teams:
    #     home_teams.append(team[0])
    #     away_teams.append(team[1])
    #     game_days.append(team[2])
    # player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
    # if player_picks:
    #     winners = player_picks['winners']
    #     confidence = player_picks['confidence']
    #     tie_breaker = player_picks['tie_breaker']
    #     home_confidence = []
    #     away_confidence = []
    #     for i in range(len(home_teams)):
    #         if home_teams[i] in winners:
    #             home_confidence.append(confidence[i])
    #             away_confidence.append('0')
    #         elif away_teams[i] in winners:
    #             away_confidence.append(confidence[i])
    #             home_confidence.append('0')
    # else:
    #     flash(category='error', message='You have not made any picks yet')
    #
    #     return redirect(url_for('auth.select_picks'))
    flash(category='error', message='Personal archive for this week is not available')
    return redirect(url_for('views.home'))
    # return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
    #                        game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
    #                        tie_breaker=tie_breaker)

@auth.route('/personal_archive_4')
@login_required
def personal_archive_4():
    # week_number = 4
    # weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    # if not weekly_schedule:
    #
    #     flash(category='error', message='Archive is not available yet')
    #     return redirect(url_for('views.home'))
    # weekly_schedule.pop("_id")
    # weekly_schedule.pop("week_number")
    # home_teams = []
    # away_teams = []
    # game_days = []
    # teams = []
    # for item in weekly_schedule.items():
    #     teams.append(item[1])
    # for team in teams:
    #     home_teams.append(team[0])
    #     away_teams.append(team[1])
    #     game_days.append(team[2])
    # player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
    # if player_picks:
    #     winners = player_picks['winners']
    #     confidence = player_picks['confidence']
    #     tie_breaker = player_picks['tie_breaker']
    #     home_confidence = []
    #     away_confidence = []
    #     for i in range(len(home_teams)):
    #         if home_teams[i] in winners:
    #             home_confidence.append(confidence[i])
    #             away_confidence.append('0')
    #         elif away_teams[i] in winners:
    #             away_confidence.append(confidence[i])
    #             home_confidence.append('0')
    # else:
    #     flash(category='error', message='You have not made any picks yet')
    #     return redirect(url_for('auth.select_picks'))
    flash(category='error', message='Personal archive for this week is not available')
    return redirect(url_for('views.home'))
    # return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
    #                        game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
    #                        tie_breaker=tie_breaker)

@auth.route('/personal_archive_5')
@login_required
def personal_archive_5():
    # week_number = 5
    # weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    # if not weekly_schedule:
    #
    #     flash(category='error', message='Archive is not available yet')
    #     return redirect(url_for('views.home'))
    # weekly_schedule.pop("_id")
    # weekly_schedule.pop("week_number")
    # home_teams = []
    # away_teams = []
    # game_days = []
    # teams = []
    # for item in weekly_schedule.items():
    #     teams.append(item[1])
    # for team in teams:
    #     home_teams.append(team[0])
    #     away_teams.append(team[1])
    #     game_days.append(team[2])
    # player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
    # if player_picks:
    #     winners = player_picks['winners']
    #     confidence = player_picks['confidence']
    #     tie_breaker = player_picks['tie_breaker']
    #     home_confidence = []
    #     away_confidence = []
    #     for i in range(len(home_teams)):
    #         if home_teams[i] in winners:
    #             home_confidence.append(confidence[i])
    #             away_confidence.append('0')
    #         elif away_teams[i] in winners:
    #             away_confidence.append(confidence[i])
    #             home_confidence.append('0')
    # else:
    #     flash(category='error', message='You have not made any picks yet')
    #     return redirect(url_for('auth.select_picks'))
    flash(category='error', message='Personal archive for this week is not available')
    return redirect(url_for('views.home'))
    # return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
    #                        game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
    #                        tie_breaker=tie_breaker)

@auth.route('/personal_archive_6')
@login_required
def personal_archive_6():
    week_number = 6
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_7')
@login_required
def personal_archive_7():
    week_number = 7
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_8')
@login_required
def personal_archive_8():
    week_number = 8
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_9')
@login_required
def personal_archive_9():
    week_number = 9
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_10')
@login_required
def personal_archive_10():
    week_number = 10
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_11')
@login_required
def personal_archive_11():
    week_number = 11
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_12')
@login_required
def personal_archive_12():
    week_number = 12
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_13')
@login_required
def personal_archive_13():
    week_number = 13
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_14')
@login_required
def personal_archive_14():
    week_number = 14
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_15')
@login_required
def personal_archive_15():
    week_number = 15
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_16')
@login_required
def personal_archive_16():
    week_number = 16
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route('/personal_archive_17')
@login_required
def personal_archive_17():
    week_number = 17
    weekly_schedule = mongoDB[f'week_{week_number}'].find_one({'_id': 'schedule'})
    if not weekly_schedule:
        flash(category='error', message='Archive is not available yet')
        return redirect(url_for('views.home'))
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
    player_picks = mongoDB[f'week_{week_number}'].find_one({'_id': current_user.username})
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
    else:
        flash(category='error', message='You have not made any picks yet')
        return redirect(url_for('auth.select_picks'))
    return render_template(f'personal_archive_{week_number}.html', len=len(home_teams), home_teams=home_teams, away_teams=away_teams,
                           game_days=game_days, home_confidence=home_confidence, away_confidence=away_confidence,
                           tie_breaker=tie_breaker)

@auth.route("/mastersheet")
@login_required
def mastersheet():
    week_number_for_final_master = mongoDB['current_week'].find_one({'_id': 'schedule'})['week_number']
    week_number_for_final_master = week_number_for_final_master - 1
    final_master_week = mongoDB[f'week_{week_number_for_final_master}'].find_one({'_id': 'schedule'})
    number_of_game_for_final_mastersheet = len(final_master_week) - 2

    prelim_exists = mongoDB['current_week'].find_one({'_id': 'prelim_master'})
    final_exists = mongoDB['current_week'].find_one({'_id': 'final_master'})
    current_week = mongoDB['current_week'].find_one({'_id': 'schedule'})
    number_of_games = len(current_week) - 2
    total_possible = sum(range(number_of_game_for_final_mastersheet + 1))
    if prelim_exists:
        table_rows = prelim_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        week_number = prelim_exists['table_rows'][0][0]

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-1]]
        table_footer[0].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-1]
        column_1 = column_1[1:-1]
        column_headers.insert(0, week_number)
        tie_breaker_index = str(len(column_1) - 1)
        return render_template('mastersheet.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index, table_footer=table_footer
                               )
    elif final_exists:
        table_rows = final_exists['table_rows']
        column_1 = []
        table_rows_final = []
        for row in table_rows:
            column_1.append(row[0])
            table_rows_final.append(row[1:])

        column_headers = table_rows_final[0]
        table_footer = [table_rows_final[-2], table_rows_final[-1]]
        table_footer[0].insert(0, 'TOTAL')
        table_footer[1].insert(0, 'Tie-Breaker')
        table_rows_final = table_rows_final[1:-2]
        column_1 = column_1[1:-2]
        week_number = final_exists['table_rows'][0][0]
        column_headers.insert(0, f'week {week_number_for_final_master}')
        tie_breaker_index = str(len(column_1) - 1)

        result = final_exists['result']
        if result[0] == 'tie':
            message = f"Tie between {result[1][0]} and {result[1][1]}"
        elif result[0] == 'winner':
            deduction = total_possible - result[1][1]
            message = f"Congratulations to this week\'s winner \"{result[1][0]}\" with {result[1][1]} points (-{deduction})!"

        return render_template('mastersheet.html', column_1=column_1, column_1_len=len(column_1),
                               row_len=len(table_rows[0]), table_rows_final=table_rows_final,
                               column_headers=column_headers, tie_breaker_index=tie_breaker_index,
                               table_footer=table_footer, message=message, footer_len=len(table_footer))
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




