import unittest
import pandas as pd
from src.ranker import generate_rankings, output_rankings

class TestRanker(unittest.TestCase):

    def setUp(self):
        # Sample data for testing
        self.offensive_scores = pd.DataFrame({
            'Team': ['Team A', 'Team B', 'Team C'],
            'Offensive_Score': [100, 90, 80]
        })
        self.defensive_scores = pd.DataFrame({
            'Team': ['Team A', 'Team B', 'Team C'],
            'Defensive_Score': [50, 60, 70]
        })

    def test_generate_rankings(self):
        rankings = generate_rankings(self.offensive_scores, self.defensive_scores)
        self.assertIn('Total_Score', rankings.columns)
        self.assertIn('Rank', rankings.columns)
        self.assertEqual(rankings['Total_Score'].iloc[0], 150)
        self.assertEqual(rankings['Rank'].iloc[0], 1.0)

    def test_output_rankings(self):
        rankings = generate_rankings(self.offensive_scores, self.defensive_scores)
        output_rankings(rankings)
        # Check if the output file is created
        self.assertTrue(os.path.exists('data/processed/team_rankings.csv'))

if __name__ == '__main__':
    unittest.main()
