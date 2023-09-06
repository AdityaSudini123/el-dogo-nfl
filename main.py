import datetime

from website import create_app
import time
from bs4 import BeautifulSoup
import requests
from pymongo import MongoClient
import schedule
import pandas as pd


cluster = MongoClient('mongodb+srv://AdityaSudini:Harry_Potter12345@cluster0.gsst9ye.mongodb.net/?retryWrites=true&w=majority')
mongoDB = cluster["ElDogoPuzzler2023"]

app = create_app()[0]
scheduler = create_app()[1]

def scheduledtask():
    schedule = mongoDB['week_1'].find_one({'_id': 'schedule'})
    weeknumber = schedule.pop('week_number')
    schedule.pop('_id')
    # allteams = [f'Week {weeknumber}']
    column1 = []
    allteams = []
    hometeams = []
    awayteams = []
    for game in schedule.values():
        column1.append(game['day'] + ", " + game['date'])
        column1.append(game['away team'])
        column1.append(game['home team'])

        awayteams.append(game['away team'])
        hometeams.append(game['home team'])

        allteams.append(game['away team'])
        allteams.append(game['home team'])
    all_docs = mongoDB['week_1'].find()
    user_docs = []
    list_of_ids = ['schedule', 'results', 'master_final', 'master_prelim']
    for doc in all_docs:
        if doc['_id'] not in list_of_ids:
            user_docs.append(doc)
    user_docs = sorted(user_docs, key=lambda d: d['_id'].lower())

    column1.append("Tie-Breaker")
    colsformaster = {}
    colsformaster[f'Week {weeknumber}'] = column1
    for document in user_docs:
        username = document.pop('_id')
        picks = document.pop('winners')
        confidences = document.pop('confidence')
        tiebreaker = document.pop('tie_breaker')
        colinmaster = []
        for row in column1:
            if row != "Tie-Breaker":
                if row[0:3] in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', "Sun"]:
                    colinmaster.append("")
                elif row in picks:
                    colinmaster.append(confidences[picks.index(f'{row}')])
                else:
                    colinmaster.append("0")
        colinmaster.append(tiebreaker)
        colsformaster[f'{username}'] = colinmaster
    colsformaster['_id'] = 'master_prelim'
    # colsformaster['week_number'] = weeknumber
    mykeys = colsformaster.keys()
    myvalues = colsformaster.values()
    # print(myvalues)
    # colsformaster[f'Week {weeknumber}'] = column1
    # print(colsformaster)

    findmaster = mongoDB['week_1'].find_one({"_id": "master_prelim"})
    if findmaster:
        mongoDB['week_1'].delete_one({'_id': 'master_prelim'})
    mongoDB['week_1'].insert_one(colsformaster)
    print("done")


if __name__ == '__main__':
    scheduler.add_job(id='test', func=scheduledtask, trigger='cron', day_of_week="tue", hour=19, minute=1)
    app.run(debug=True, port='0000', host='localhost', use_reloader=False)
    # app.run(debug=True, port='0000', host='localhost')

#     Personal Access token: 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 --> never expires apparently


