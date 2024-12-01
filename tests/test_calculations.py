import unittest
import pandas as pd
from src.calculations import calculate_offensive_scores, calculate_defensive_scores

class TestCalculations(unittest.TestCase):

    def setUp(self):
        # Sample data for testing
        self.offensive_data = pd.DataFrame({
            'Yds': [4000, 3500, 3000],
            'TD': [30, 25, 20],
            'G': [16, 16, 16]
        })
        self.defensive_data = pd.DataFrame({
            'Yds': [3000, 3500, 4000],
            'TD': [20, 25, 30],
            'G': [16, 16, 16]
        })

    def test_calculate_offensive_scores(self):
        result = calculate_offensive_scores(self.offensive_data)
        self.assertIn('Offensive_Score', result.columns)
        self.assertEqual(result['Offensive_Score'].iloc[0], (4000 + 30) / 16)

    def test_calculate_defensive_scores(self):
        result = calculate_defensive_scores(self.defensive_data)
        self.assertIn('Defensive_Score', result.columns)
        self.assertEqual(result['Defensive_Score'].iloc[0], (3000 + 20) / 16)

if __name__ == '__main__':
    unittest.main()
