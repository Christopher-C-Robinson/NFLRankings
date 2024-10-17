# NFL Team Rankings Automation Project

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

## Additional Notes
- This project aims to eliminate manual bias and ranking based on subjective factors like record or reputation. The focus is solely on statistical output.

## Setup Instructions

### Backend
1. Clone the repository:
   ```bash
   git clone https://github.com/Christopher-C-Robinson/NFLRankings.git
   cd NFLRankings/server
   ```

2. Create a virtual environment and activate it:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the Django development server:
   ```bash
   python manage.py runserver
   ```

### Frontend
1. Navigate to the client directory:
   ```bash
   cd ../client
   ```

2. Install the required dependencies:
   ```bash
   npm install
   ```

3. Run the Angular development server:
   ```bash
   ng serve
   ```

## Usage Instructions
1. Access the frontend application in your browser at `http://localhost:4200`.
2. The application will display the NFL team rankings based on the latest data fetched and calculated by the backend.
