from bs4 import BeautifulSoup
import requests
import sqlite3 as sl


def schedule_scraper():
    # this is for NFL
    website = 'https://www.pro-football-reference.com/years/2022/week_1.htm'
    url = requests.get(website).text

    soup = BeautifulSoup(url, 'html.parser')

    game_summaries = soup.find_all('div', class_='game_summary nohover')

    week_number_prelim = soup.find_all('div', class_='section_heading')
    week_number = week_number_prelim[1].text

    dates_prelim = []
    teams_prelim = []
    for game in game_summaries:
        dates_prelim.append(game.find_all('tr', class_='date'))
        teams_prelim.append(game.find_all('a'))

    teams = []
    for team in teams_prelim:
        for i in team:
            if i.text != 'Preview':
                teams.append(i.text)

    home_teams = teams[::2]
    away_teams = teams[1::2]
    dates = []

    for date in dates_prelim:
        for i in date:
            dates.append(i.text)

    return (teams, home_teams, away_teams, dates, week_number)

def result_scraper():
    # website = 'https://www.pro-football-reference.com/years/2021/week_1.htm'
    # url = requests.get(website).text
    # soup = BeautifulSoup(url, 'lxml')
    #
    # winning_teams = soup.find_all('tr', class_='winner')
    # winners = []
    # for team in winning_teams:
    #     winners.append(team.a.text)
    winners = ['Los Angeles Rams', 'New Orleans Saints', 'Cleveland Browns', 'San Francisco 49ers', 'Pittsburgh Steelers',
               'Philadelphia Eagles', 'Indianapolis Colts', 'New England Patriots', 'Baltimore Ravens',
               'Jacksonville Jaguars', 'Kansas City Chiefs', 'Green Bay Packers', 'New York Giants', 'Las Vegas Raiders',
               'Tampa Bay Buccaneers', 'Denver Broncos']
    return winners


#
# conn = sl.connect('database.db')
# stmt1 = "SELECT * FROM Entries"
# curs = conn.cursor()
# executed1 = curs.execute(stmt1)
# for i in executed1:
#     print(i)
# conn.close()
