from website import create_app
import time
from bs4 import BeautifulSoup
import requests
from pymongo import MongoClient
import schedule
import pandas as pd


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port='0000', host='localhost')

#     Personal Access token: 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 --> expires on nov 30 2023


