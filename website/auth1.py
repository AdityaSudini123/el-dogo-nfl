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
mongoDB = cluster["ElDogoPuzzler2023"]
schedule_collection = mongoDB["weekly_schedule"]
results_collection = mongoDB["weekly_results"]
user_data_collection = mongoDB["user_data"]
user_picks_collection = mongoDB["user_weekly_picks"]

auth = Blueprint("auth", __name__)

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
                login_user(new_user, remember=True)
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

        # if email_exists:
        #     print('email exists')
        #     if user_mongo:
        #         if user_mongo['email'] == email1:
        #             print(user_mongo['email'])
        #             flash('Email is already in use.', category='error')
        # if username_exists:
        #     print('username exists')
        #     if user_mongo:
        #         if user_mongo['_id'] == username1:
        #             flash('Username is already in use.', category='error')
        else:
            new_user_mongodb = {"_id": username1, "email": email1, "password": generate_password_hash(password1, method="sha256")}
            user_data_collection.insert_one(new_user_mongodb)

            new_user = User(email=email1, username=username1, password=generate_password_hash(
                password1, method='sha256'))
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user, remember=True)
            flash('User created!')
            return redirect(url_for('views.home'))
    return render_template("signup.html")
    # flash(category='error', message='Sign ups are closed. Please login if you have an account, or try to sign up next season.')
    # return redirect(url_for('auth.login'))

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

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("views.home"))

@auth.route('/rules', methods=['GET', 'POST'])
@login_required
def rules():
    return(render_template('rules.html'))


