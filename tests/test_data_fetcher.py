import unittest
from src.data_fetcher import fetch_offensive_stats, fetch_defensive_stats, fetch_data

class TestDataFetcher(unittest.TestCase):

    def test_fetch_offensive_stats(self):
        df = fetch_offensive_stats()
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        self.assertIn('Team', df.columns)

    def test_fetch_defensive_stats(self):
        df = fetch_defensive_stats()
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        self.assertIn('Team', df.columns)

    def test_fetch_data(self):
        offensive_data, defensive_data = fetch_data()
        self.assertIsNotNone(offensive_data)
        self.assertFalse(offensive_data.empty)
        self.assertIn('Team', offensive_data.columns)
        self.assertIsNotNone(defensive_data)
        self.assertFalse(defensive_data.empty)
        self.assertIn('Team', defensive_data.columns)

if __name__ == '__main__':
    unittest.main()
