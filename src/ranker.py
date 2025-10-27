import pandas as pd

def generate_rankings(offensive_scores, defensive_scores):
    # Merge offensive and defensive scores
    combined_scores = pd.merge(offensive_scores, defensive_scores, on='Team')
    
    # Calculate total score
    combined_scores['Total_Score'] = combined_scores['Offensive_Score'] + combined_scores['Defensive_Score']
    
    # Rank teams based on total score
    combined_scores['Rank'] = combined_scores['Total_Score'].rank(ascending=False)
    
    # Sort by rank
    combined_scores = combined_scores.sort_values(by='Rank')
    
    return combined_scores

def output_rankings(rankings):
    # Output rankings to a CSV file
    rankings.to_csv('data/processed/team_rankings.csv', index=False)
    
    # Print rankings to console
    print(rankings)
