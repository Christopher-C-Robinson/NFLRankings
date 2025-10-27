import pandas as pd

def calculate_offensive_scores(offensive_data):
    # Example calculation based on provided formula
    offensive_data['Offensive_Score'] = (offensive_data['Yds'] + offensive_data['TD']) / offensive_data['G']
    offensive_data.to_csv('data/processed/offensive_scores.csv', index=False)
    return offensive_data

def calculate_defensive_scores(defensive_data):
    # Example calculation based on provided formula
    defensive_data['Defensive_Score'] = (defensive_data['Yds'] + defensive_data['TD']) / defensive_data['G']
    defensive_data.to_csv('data/processed/defensive_scores.csv', index=False)
    return defensive_data
