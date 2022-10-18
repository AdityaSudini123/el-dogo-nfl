from website import create_app
import time
from bs4 import BeautifulSoup
import requests
from pymongo import MongoClient
import schedule
import pandas as pd


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port='8080', host='localhost')


