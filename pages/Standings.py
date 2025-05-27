import streamlit as st
import pandas as pd
import numpy as np
import os
import urllib.parse
from urllib.parse import urlparse, parse_qs
from urllib.parse import unquote
from urllib.parse import quote
from pymongo import MongoClient
from dotenv import load_dotenv


# Load MongoDB URI from .env or environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')  

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['blitzballstats'] 


# Page config
st.set_page_config(page_title="League Standings")


players_col = db["players"]
atbats_col = db["atbats"]
games_col = db["games"]

players = pd.DataFrame(list(players_col.find()))
atbats = pd.DataFrame(list(atbats_col.find()))
games = pd.DataFrame(list(games_col.find()))

st.title("League Standings")

# Choose stat type
stat_type = st.radio("Select Stat Type", ["Hitting", "Pitching"])

# Stat options
hitting_stats = ["AVG", "OBP", "HR", "1B", "2B", "3B", "RBIs", "BB", "K%"]
pitching_stats = ["ERA", "WHIP", "Hits Allowed", "HR Allowed", "K%"]

category = st.selectbox(
    f"Select {stat_type} Stat",
    hitting_stats if stat_type == "Hitting" else pitching_stats
)

# Process stats for each player
leaderboard = []

for player in players["name"].unique():
    player_batting = atbats[atbats["batter"] == player]
    player_pitching = atbats[atbats["pitcher"] == player]

    # Hitting stats
    num_at_bats = len(player_batting)
    hits = player_batting["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
    walks = player_batting["outcome"].eq("Walk").sum()
    strikeouts = player_batting["outcome"].eq("Strike Out").sum()
    singles = player_batting["outcome"].eq("Single").sum()
    doubles = player_batting["outcome"].eq("Double").sum()
    triples = player_batting["outcome"].eq("Triple").sum()
    home_runs = player_batting["outcome"].eq("Home Run").sum()
    rbis = player_batting["rbi"].sum()

    batting_average = hits / num_at_bats if num_at_bats else 0
    obp = (hits + walks) / (num_at_bats + walks) if (num_at_bats + walks) else 0
    k_rate_bat = (strikeouts / num_at_bats * 100) if num_at_bats else 0

    # Pitching stats
    total_outs = player_pitching["outs_recorded"].sum()
    innings_pitched = total_outs / 3
    hits_allowed = player_pitching["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
    walks_allowed = player_pitching["outcome"].eq("Walk").sum()
    strikeouts_pitched = player_pitching["outcome"].eq("Strike Out").sum()
    home_runs_allowed = player_pitching["outcome"].eq("Home Run").sum()
    batters_faced = len(player_pitching)
    earned_runs = player_pitching["rbi"].sum()

    era = (earned_runs / innings_pitched * 9) if innings_pitched else np.nan
    whip = (walks_allowed + hits_allowed) / innings_pitched if innings_pitched else np.nan
    k_rate_pit = (strikeouts_pitched / batters_faced * 100) if batters_faced else np.nan

    row = {
        "Player": player,
        "AVG": round(batting_average, 3),
        "OBP": round(obp, 3),
        "HR": home_runs,
        "1B": singles,
        "2B": doubles,
        "3B": triples,
        "RBIs": rbis,
        "BB": walks,
        "K%": round(k_rate_bat, 2),
        "ERA": round(era, 2) if not np.isnan(era) else None,
        "WHIP": round(whip, 2) if not np.isnan(whip) else None,
        "Hits Allowed": hits_allowed,
        "HR Allowed": home_runs_allowed,
        "K%_P": round(k_rate_pit, 2) if not np.isnan(k_rate_pit) else None,
    }

    leaderboard.append(row)
df = pd.DataFrame(leaderboard)

# Determine sorting column and order
if stat_type == "Pitching" and category == "K%":
    sort_col = "K%_P"
    ascending = False  # Higher pitching K% is better
elif stat_type == "Hitting" and category == "K%":
    sort_col = "K%"
    ascending = True  # Lower hitting K% is better
else:
    sort_col = category
    ascending_stats = ["ERA", "WHIP", "Hits Allowed", "HR Allowed"]
    ascending = category in ascending_stats


# Card style from the other pages
def get_card_style(value, bg_color=None):
    base_color = bg_color if bg_color else "#1f1f2e"
    return f"""
        <div style="
            padding: 12px;
            margin: 6px;
            border: 1px solid #333;
            border-radius: 8px;
            background-color: {base_color};
            color: #f1f1f1;
            font-size: 16px;
            text-align: center;">
            <b>{value}</b>
        </div>
    """

# Safely show leaderboard only if data exists
if df.empty or sort_col not in df.columns:
    st.warning("No data available for the selected stat yet. Play some games to see the standings!")
else:
    sorted_df = df[["Player", sort_col]].dropna().sort_values(by=sort_col, ascending=ascending).reset_index(drop=True)

    st.subheader(f"{category} Leaderboard")

    # Loop and display leaderboard in 3 columns: Rank, Name, Stat
    for i, row in sorted_df.iterrows():
        # Conditional coloring
        if i == 0:
            bg = "#81c784"  # Green for top
        elif i == len(sorted_df) - 1:
            bg = "#ef9a9a"  # Red for bottom
        else:
            bg = None

        col1, col2, col3 = st.columns([1, 2, 2])
        with col1:
            st.markdown(get_card_style(f"#{i + 1}", bg), unsafe_allow_html=True)
        with col2:
            st.markdown(get_card_style(row["Player"], bg), unsafe_allow_html=True)
        with col3:
            st.markdown(get_card_style(row[sort_col], bg), unsafe_allow_html=True)