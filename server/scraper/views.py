from django.shortcuts import render
from django.http import JsonResponse
from .models import Team
import requests
from bs4 import BeautifulSoup

def fetch_team_rankings(request):
    # Fetch offensive and defensive statistics
    offensive_stats_url = "https://www.pro-football-reference.com/years/2024/"
    defensive_stats_url = "https://www.pro-football-reference.com/years/2024/opp.htm"

    offensive_stats = fetch_stats(offensive_stats_url)
    defensive_stats = fetch_stats(defensive_stats_url)

    # Calculate rankings
    teams = calculate_rankings(offensive_stats, defensive_stats)

    # Save rankings to database
    save_rankings_to_db(teams)

    # Fetch rankings from database
    rankings = Team.objects.all().order_by('ranking')

    # Return rankings as JSON response
    return JsonResponse({"rankings": list(rankings.values())})

def fetch_stats(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    stats_table = soup.find('table')
    stats = []
    for row in stats_table.find_all('tr')[1:]:
        cols = row.find_all('td')
        stats.append([col.text for col in cols])
    return stats

def calculate_rankings(offensive_stats, defensive_stats):
    teams = []
    for i in range(len(offensive_stats)):
        team_name = offensive_stats[i][0]
        offensive_value = calculate_offensive_value(offensive_stats[i])
        defensive_value = calculate_defensive_value(defensive_stats[i])
        ranking_value = offensive_value - defensive_value
        teams.append({"name": team_name, "ranking_value": ranking_value})
    teams.sort(key=lambda x: x["ranking_value"], reverse=True)
    for i, team in enumerate(teams):
        team["ranking"] = i + 1
    return teams

def calculate_offensive_value(stats):
    # Implement offensive calculation based on provided screenshot
    return float(stats[1]) * 0.5 + float(stats[2]) * 0.3 + float(stats[3]) * 0.2

def calculate_defensive_value(stats):
    # Implement defensive calculation based on provided screenshot
    return float(stats[1]) * 0.4 + float(stats[2]) * 0.4 + float(stats[3]) * 0.2

def save_rankings_to_db(teams):
    Team.objects.all().delete()
    for team in teams:
        Team.objects.create(
            name=team["name"],
            offensive_stats={},
            defensive_stats={},
            ranking=team["ranking"]
        )
