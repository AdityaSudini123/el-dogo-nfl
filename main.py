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

#     Personal Access token: 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 --> never expires apparently


