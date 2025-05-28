# Wiffle Ball Statistics Tracker

## A Streamlit web app backed by MongoDB for tracking Wiffle Ball games and individual player performance with data persistence.

This project is a web-based stat-tracking system designed for casual groups or wiffle ball leagues. Users can log each game in real time by recording the outcome of every at-bat. The app automatically calculates scores, generates advanced hitting and pitching statistics, and visualizes player performance over time. Key features include: 

- New Game Interface – Create games, assign teams, and input plays via a user-friendly form
- Match History Log – View historical games, team compositions, and scores
- Player Profiles – Career and per-game stats for batting and pitching
- Player Matchups – Compare head-to-head player stats with detailed breakdowns
- League Standings – Live leaderboards by hitting and pitching metrics 
- Data Visualization – Live graphs and figures for performance comparisons


## Live Demo

Check out the app here: [Wiffle ball Stat Tracker on Streamlit](https://wiffle.streamlit.app)

## Installation Instructions for Local Use

### Prerequisites: 
- MongoDB Atlas Account (or own MongoDB deployment)
- Python 3.8+

### Installation:

1. Clone the repository
```sh
git clone https://github.com/your-username/your-repo-name.git
```

2. Create a Virtual Environment: 
```sh
python -m venv venv
source venv\Scripts\activate
```
3. Install the dependencies: 
```sh
`pip install -r requirements.txt`
```
4. Create a `.env` file in the root directory. Within this file, add your MongoDB connection string: 
```sh
`MONGO_URI=your_mongodb_connection_string` 
```

5. Run the app:
```sh
`streamlit run home.py`
```

## Contact

Edward Quezada - edwardq@alumni.stanford.edu






