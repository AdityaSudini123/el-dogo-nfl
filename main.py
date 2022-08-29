from website import create_app
import time
from bs4 import BeautifulSoup
import requests
from pymongo import MongoClient
import schedule
import pandas as pd

app = create_app()

cluster = MongoClient('mongodb+srv://AdityaSudini:Harry_Potter12345@cluster0.gsst9ye.mongodb.net/?retryWrites=true&w=majority')
db = cluster["MaxJules"]
schedule_collection = db["weekly_schedule"]
results_collection = db["weekly_results"]

def weekly_schedule():
    current_week = 1
    webpage = f'https://www.pro-football-reference.com/years/2021/week_{current_week}.htm'
    webpage_url = requests.get(webpage).text
    bs = BeautifulSoup(webpage_url, 'html.parser')

    winning_teams_list = bs.find_all('tr', class_='winner')
    losing_teams_list = bs.find_all('tr', class_='loser')
    # week_number = bs.find_all('div', class_='section_heading')
    # week_number_int = int((week_number[1].text[-1]))


    game_schedule = {'_id': 'schedule'}
    game_schedule['week_number'] = current_week
    counter = 0
    team1 = []
    team2 = []
    for team in winning_teams_list:
        team1.append(team.a.text)
    for team in losing_teams_list:
        team2.append(team.a.text)
    for i in range(len(team1)):
        counter += 1
        game_schedule[f'game_{counter}'] = [team1[i], team2[i]]

    schedule_exists = db[f'week_{current_week}'].find_one({'_id': 'schedule'})
    if not schedule_exists:
        db[f'week_{current_week}'].insert_one(game_schedule)
        db['current_week'].insert_one(game_schedule)

    while schedule_exists:
        current_week += 1
        new_cluster = db[f'week_{current_week}']
        webpage = f'https://www.pro-football-reference.com/years/2021/week_{current_week}.htm'
        webpage_url = requests.get(webpage).text
        bs = BeautifulSoup(webpage_url, 'html.parser')

        winning_teams_list = bs.find_all('tr', class_='winner')
        losing_teams_list = bs.find_all('tr', class_='loser')
        # week_number = bs.find_all('div', class_='section_heading')
        # week_number_int = int((week_number[1].text[-1]))

        game_schedule = {'_id': 'schedule'}
        game_schedule['week_number'] = current_week
        counter = 0
        team1 = []
        team2 = []
        for team in winning_teams_list:
            team1.append(team.a.text)
        for team in losing_teams_list:
            team2.append(team.a.text)
        for i in range(len(team1)):
            counter += 1
            game_schedule[f'game_{counter}'] = [team1[i], team2[i]]

        schedule_exists = db[f'week_{current_week}'].find_one({'_id': 'schedule'})
        if not schedule_exists:
            new_cluster.insert_one(game_schedule)
            db['current_week'].delete_one({'_id': 'schedule'})
            db['current_week'].insert_one(game_schedule)

schedule.every().hour.at(':25').do(weekly_schedule)

def weekly_results():
    current_week = 1
    webpage = f'https://www.pro-football-reference.com/years/2021/week_{current_week}.htm'
    webpage_url = requests.get(webpage).text
    bs = BeautifulSoup(webpage_url, 'html.parser')

    winning_teams_list = bs.find_all('tr', class_='winner')
    losing_teams_list = bs.find_all('tr', class_='loser')
    # week_number = bs.find_all('div', class_='section_heading')
    # week_number_int = int((week_number[1].text[-1]))

    winner_scores = []
    for team in winning_teams_list:
        winner_scores.append(team.find('td', class_='right').text)
    loser_scores = []
    for team in losing_teams_list:
        loser_scores.append(team.find('td', class_='right').text)

    winners = []
    losers = []
    for team in winning_teams_list:
        winners.append(team.a.text)
    for team in losing_teams_list:
        losers.append(team.a.text)

    winner_results = {}
    loser_results = {}
    for i in range(len(winners)):
        winner_results[winners[i]] = winner_scores[i]
        loser_results[losers[i]] = loser_scores[i]

    game_results = {'_id': 'results'}
    game_results['week_number'] = current_week
    game_results['winners'] = winner_results
    game_results['losers'] = loser_results
    result_exists = db[f'week_{current_week}'].find_one({'_id': 'results'})
    if not result_exists:
        db[f'week_{current_week}'].insert_one(game_results)
        db['current_week'].insert_one(game_results)

    while result_exists:
        current_week += 1
        webpage = f'https://www.pro-football-reference.com/years/2021/week_{current_week}.htm'
        webpage_url = requests.get(webpage).text
        bs = BeautifulSoup(webpage_url, 'html.parser')

        winning_teams_list = bs.find_all('tr', class_='winner')
        losing_teams_list = bs.find_all('tr', class_='loser')
        # week_number = bs.find_all('div', class_='section_heading')
        # week_number_int = int((week_number[1].text[-1]))

        winner_scores = []
        for team in winning_teams_list:
            winner_scores.append(team.find('td', class_='right').text)
        loser_scores = []
        for team in losing_teams_list:
            loser_scores.append(team.find('td', class_='right').text)

        winners = []
        losers = []
        for team in winning_teams_list:
            winners.append(team.a.text)
        for team in losing_teams_list:
            losers.append(team.a.text)

        winner_results = {}
        loser_results = {}
        for i in range(len(winners)):
            winner_results[winners[i]] = winner_scores[i]
            loser_results[losers[i]] = loser_scores[i]

        game_results = {'_id': 'results'}
        game_results['week_number'] = current_week
        game_results['winners'] = winner_results
        game_results['losers'] = loser_results

        result_exists = db[f'week_{current_week}'].find_one({'_id': 'results'})
        if not result_exists:
            db[f'week_{current_week}'].insert_one(game_results)
            db['current_week'].delete_one({'_id': 'results'})
            db['current_week'].insert_one(game_results)

schedule.every().hour.at(':30').do(weekly_results)

def create_mastersheet():
    current_week = db['current_week'].find_one({'_id': 'schedule'})
    week_number = current_week['week_number']
    current_week.pop('_id')
    current_week.pop('week_number')
    team_list = []
    for item in current_week.items():
        for team in item[1]:
            team_list.append(team)
    myDF = pd.DataFrame()
    team_list.append('TOTAL')
    myDF.index = team_list

    current_week_results = db['current_week'].find_one({'_id': 'results'})
    current_week_winners = current_week_results['winners'].keys()

    users = db['user_data'].find()
    user_ids = []
    for user in users:
        user_ids.append(user['_id'])

    current_week_docs = db[f'week_{week_number}'].find()
    forbidden = ['schedule', 'results']
    player_scores = []
    for document in current_week_docs:
        if not document['_id'] in forbidden:
            username = document['_id']
            teams_selected = document['winners']
            confidence = document['confidence']

            counter = 0
            player_total = 0
            for team in myDF.index[0:-1]:
                if team in teams_selected:
                    myDF.loc[team, username] = confidence[counter]
                    counter += 1
                    if team in current_week_winners:
                        player_total += int(myDF.loc[team, username])
                else:
                    myDF.loc[team, username] = '0'
            player_scores.append(player_total)
    myDF.loc['TOTAL'] = player_scores
    myDF_to_html = myDF.to_html()
    html_code = myDF_to_html.split('\n')

    html_code_exists = db['current_week'].find_one({'_id': 'mastersheet'})

    if html_code_exists:
        db['current_week'].delete_one({'_id': 'mastersheet'})
        db['current_week'].insert_one({'_id': 'mastersheet', 'html_code': html_code})
        db[f'week_{week_number}'].insert_one({'_id': 'mastersheet', 'html_code': html_code})
    else:
        db['current_week'].insert_one({'_id': 'mastersheet', 'html_code': html_code})
        db[f'week_{week_number}'].insert_one({'_id': 'mastersheet', 'html_code': html_code})

schedule.every().hour.at(':32').do(create_mastersheet)


if __name__ == '__main__':
    app.run(debug=True, port='8090', host='localhost')
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)


