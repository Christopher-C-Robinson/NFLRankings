# Automate NFL Team Ranking Calculation Project

## Objective
Automate the current manual process of ranking NFL teams based on offensive and defensive statistics using a custom calculation. The aim is to create a system that pulls data, runs calculations, and outputs rankings automatically, removing biases and focusing purely on team performance.

## Current Process
1. Gathering team statistics from Pro Football Reference:
   - Offensive stats: [2024 NFL Standings & Team Stats](https://www.pro-football-reference.com/years/2024/)
   - Defensive stats: [2024 NFL Opposition & Defensive Statistics](https://www.pro-football-reference.com/years/2024/opp.htm)
2. Using a custom calculation to determine each team's ranking based on offensive and defensive outputs.
   - Offensive calculation example: See attached screenshot (Screenshot 2024-10-16 at 6.30.58 PM.png).
   - Defensive calculation example: See attached screenshot (Screenshot 2024-10-16 at 6.31.48 PM.png).
3. Ranking each team based on the values from the calculations.

## Goal for Automation
- Create a script or tool that can:
  1. Automatically fetch the offensive and defensive statistics from Pro Football Reference.
  2. Run the statistics through the provided calculation formulas.
  3. Rank the teams based purely on the computed values.

## Requirements
- Use the offensive and defensive calculations as provided in the screenshots.
- Develop a ranking system that updates automatically based on the most recent data.
- Ensure the solution is scalable to include more statistics or different variations of calculations if needed.

## Tech Stack Suggestions
- Data scraping: Python (Beautiful Soup, Requests) or an API if available.
- Automation and scheduling: Python scripts with a scheduler (like cron jobs).
- Data handling: Pandas or similar data analysis libraries.

## Suggested Project Structure
```
project-root/
    ├── README.md
    ├── requirements.txt
    ├── data/
    │   ├── raw/
    │   └── processed/
    ├── src/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── data_fetcher.py  # Module for scraping or fetching data
    │   ├── calculations.py  # Module for performing the team ranking calculations
    │   ├── ranker.py        # Module for creating the ranking output
    │   └── utils.py         # Helper functions and utilities
    ├── config/
    │   └── config.yaml      # Configuration file (e.g., URLs, thresholds)
    ├── notebooks/
    │   └── exploration.ipynb  # Jupyter notebook for data exploration
    ├── tests/
    │   ├── __init__.py
    │   ├── test_data_fetcher.py
    │   ├── test_calculations.py
    │   └── test_ranker.py
    ├── scripts/
    │   └── run_pipeline.sh  # Script to automate the entire pipeline
    └── logs/
        └── app.log          # Log file for monitoring execution
```

## Setup Instructions
1. Clone the repository:
   ```
   git clone https://github.com/Christopher-C-Robinson/NFLRankings.git
   cd NFLRankings
   ```

2. Create a virtual environment and activate it:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage Guidelines
1. Run the main script to fetch data, perform calculations, and generate rankings:
   ```
   python src/main.py
   ```

2. Check the `data/` directory for raw and processed data files.

3. Check the `logs/` directory for execution logs.

4. Use the Jupyter notebook in the `notebooks/` directory for data exploration and analysis.

## Additional Notes
- This project aims to eliminate manual bias and ranking based on subjective factors like record or reputation. The focus is solely on statistical output.

- Ensure that the configuration file (`config/config.yaml`) is updated with the correct URLs and thresholds for the calculations.
