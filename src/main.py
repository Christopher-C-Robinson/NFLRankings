import data_fetcher
import calculations
import ranker

def main():
    # Fetch data
    offensive_data, defensive_data = data_fetcher.fetch_data()

    # Perform calculations
    offensive_scores = calculations.calculate_offensive_scores(offensive_data)
    defensive_scores = calculations.calculate_defensive_scores(defensive_data)

    # Generate rankings
    rankings = ranker.generate_rankings(offensive_scores, defensive_scores)

    # Output rankings
    ranker.output_rankings(rankings)

if __name__ == "__main__":
    main()
