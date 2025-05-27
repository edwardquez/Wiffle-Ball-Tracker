import streamlit as st
import pandas as pd
import os

from pymongo import MongoClient
from dotenv import load_dotenv

# Load MongoDB URI from .env or environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')  

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['blitzballstats'] 



# Page config
st.set_page_config(page_title="Game Log")


# MongoDB collections
players = pd.DataFrame(list(db.players.find()))
atbats = pd.DataFrame(list(db.atbats.find()))
games = pd.DataFrame(list(db.games.find()))


# Convert date column to datetime format for filtering
games["date"] = pd.to_datetime(games["date"], errors="coerce")


st.title("Match History Log")


# Filters Player Standings by Year 
st.sidebar.header("Filter by Year")
available_years = games["date"].dt.year.dropna().unique()
selected_year = st.sidebar.selectbox("Select Year", sorted(available_years, reverse=True))
games = games[games["date"].dt.year == selected_year]


# Show the most recent games first
games = games.iloc[::-1].reset_index(drop=True)

for i, row in games.iterrows():
    match_title = f"Match {len(games) - i}:"
    game_date = row["date"]
    team1 = row["team1"]
    team2 = row["team2"]

    # Cast scores as integers, fallback to 0 if missing or invalid
    try:
        team1_score = int(float(row.get("team1_score", 0)))
        team2_score = int(float(row.get("team2_score", 0)))
    except ValueError:
        team1_score = team2_score = 0

    winner = team1 if team1_score > team2_score else team2 if team2_score > team1_score else "Draw"

    # Highlight winning team light green and losing team light red
    win_color = "#81c784"   # light green
    loss_color = "#ef9a9a"  # light red

    if winner == team1:
        team1_style = f"background-color: {win_color};"
        team2_style = f"background-color: {loss_color};"
    elif winner == team2:
        team2_style = f"background-color: {win_color};"
        team1_style = f"background-color: {loss_color};"
    else:
        team1_style = team2_style = ""
    

    with st.container():
        st.markdown(f"### {match_title}")
        st.markdown(f"**Date**: {game_date}")

        cols = st.columns(2)
        cols = st.columns(2)
        with cols[0]:
            st.markdown(
                f"<div style='{team1_style} padding: 10px; border-radius: 6px;'>"
                f"<strong>{team1}</strong> — Score: {team1_score}</div>",
                unsafe_allow_html=True
            )

        with cols[1]:
            st.markdown(
                f"<div style='{team2_style} padding: 10px; border-radius: 6px;'>"
                f"<strong>{team2}</strong> — Score: {team2_score}</div>",
                unsafe_allow_html=True
            )

        st.markdown(f"**Winner**: {winner}")
            # Show scoring plays
                # Show scoring plays
        with st.expander("📈 Scoring Plays"):
            game_id = row.get("game_id")
            if game_id is not None and game_id in atbats["game_id"].values:
                scoring_plays = atbats[(atbats["game_id"] == game_id) & (atbats["rbi"] > 0)].copy()

                if not scoring_plays.empty:
                    play_rows = []

                    # Convert team player strings to lists
                    team1_players = [p.strip() for p in str(row["team1_players"]).split(",")]
                    team2_players = [p.strip() for p in str(row["team2_players"]).split(",")]

                    # Initialize running score
                    team1_score = 0
                    team2_score = 0

                    for _, play in scoring_plays.iterrows():
                        inning_label = play["inning"] if pd.notna(play["inning"]) else "?"
                        batter = play["batter"]
                        outcome = play["outcome"]
                        rbi = int(play.get("rbi", 0))

                        
                        

                        # Determine team scoring
                        if batter in team1_players:
                            team1_score += rbi
                        elif batter in team2_players:
                            team2_score += rbi

                        # Create full event description
                        description = f"**{batter}** — {outcome}"

                        play_rows.append({
                            "Inning": inning_label,
                            "Event": description,
                            "Score": f"{team1_score}-{team2_score}"
                        })

                    scoring_df = pd.DataFrame(play_rows)
                    st.dataframe(scoring_df, hide_index=True, use_container_width=True)
                else:
                    st.markdown("No scoring plays recorded for this game.")
            else:
                st.warning("No valid game ID found or no scoring plays available.")




# --- Individual Player Standings Table ---
st.markdown("---")
st.markdown(f"## Player W/L Records — {selected_year}")

results = {}

for _, row in games.iterrows():
    try:
        team1_score = int(float(row.get("team1_score", 0)))
        team2_score = int(float(row.get("team2_score", 0)))
    except ValueError:
        continue

    team1_players = [p.strip() for p in str(row["team1_players"]).split(",")]
    team2_players = [p.strip() for p in str(row["team2_players"]).split(",")]

    if team1_score > team2_score:
        winners, losers = team1_players, team2_players

        for p in winners:
            if p not in results:
                results[p] = {"Wins": 0, "Losses": 0, "Draws": 0}
            results[p]["Wins"] += 1

        for p in losers:
            if p not in results:
                results[p] = {"Wins": 0, "Losses": 0, "Draws": 0}
            results[p]["Losses"] += 1

    elif team2_score > team1_score:
        winners, losers = team2_players, team1_players

        for p in winners:
            if p not in results:
                results[p] = {"Wins": 0, "Losses": 0, "Draws": 0}
            results[p]["Wins"] += 1

        for p in losers:
            if p not in results:
                results[p] = {"Wins": 0, "Losses": 0, "Draws": 0}
            results[p]["Losses"] += 1

    else:
        draw_players = team1_players + team2_players
        for p in draw_players:
            if p not in results:
                results[p] = {"Wins": 0, "Losses": 0, "Draws": 0}
            results[p]["Draws"] += 1

# Convert to DataFrame
data = []
for player, record in results.items():
    wins = record["Wins"]
    losses = record["Losses"]
    draws = record["Draws"]
    games_played = wins + losses
    win_pct = round(wins / games_played, 2) if games_played else 0.0
    data.append([player, wins, losses, draws, games_played, win_pct])

standings_df = pd.DataFrame(data, columns=["Player", "Wins", "Draws", "Losses", "Games Played", "Win %"])
standings_df = standings_df.sort_values(by=["Wins", "Win %"], ascending=[False, False]).reset_index(drop=True)
st.dataframe(standings_df, use_container_width=True)
