import requests
from bs4 import BeautifulSoup
import pandas as pd

def fetch_offensive_stats():
    url = "https://www.pro-football-reference.com/years/2024/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', {'id': 'team_stats'})
    df = pd.read_html(str(table))[0]
    df.to_csv('data/raw/offensive_stats.csv', index=False)
    return df

def fetch_defensive_stats():
    url = "https://www.pro-football-reference.com/years/2024/opp.htm"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', {'id': 'team_stats'})
    df = pd.read_html(str(table))[0]
    df.to_csv('data/raw/defensive_stats.csv', index=False)
    return df

def fetch_data():
    offensive_data = fetch_offensive_stats()
    defensive_data = fetch_defensive_stats()
    return offensive_data, defensive_data
