## Packages 
import streamlit as st
import pandas as pd
import os
import uuid 
import random
import json

from urllib.parse import quote
from dotenv import load_dotenv
from datetime import datetime 
from pymongo import MongoClient

load_dotenv()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Load MongoDB URI from .env or environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')  

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['blitzballstats'] 


# Page Title
st.set_page_config(
    page_title ="Wiffle Ball Stats"
)


# MongoDB collections
players_col = db["players"]
games_col = db["games"]
atbats_col = db["atbats"]


# Define expected columns
expected_player_fields = [
    "name", "team", "games_played", "at_bats", "hits", "singles", "doubles",
    "triples", "home_runs", "walks", "rbi", "strikeouts", "batting_average",
    "obp", "slugging", "innings_pitched", "era", "bb"
]

expected_game_fields = [
    "game_id", "date", "team1", "team2", "team1_players", "team2_players",
    "status", "team1_score", "team2_score", "ended_innings"
]

expected_atbat_fields = [
    "game_id", "inning", "batter", "pitcher", "strikes", "balls",
    "runners_on", "outcome", "outs_recorded", "rbi"
]

# Load from MongoDB
players = pd.DataFrame(list(players_col.find()))
games = pd.DataFrame(list(games_col.find()))
atbats = pd.DataFrame(list(atbats_col.find()))

# Ensure all expected columns exist in each DataFrame
for col in expected_player_fields:
    if col not in players.columns:
        players[col] = None

for col in expected_game_fields:
    if col not in games.columns:
        games[col] = None

for col in expected_atbat_fields:
    if col not in atbats.columns:
        atbats[col] = None




# Title
st.title("Wiffle Ball Stat Tracker")


st.header("Player Management:")

with st.form("add_player_form"):
    new_name = st.text_input("Add New Player", "")
    submitted = st.form_submit_button("➕ Add Player")

    if submitted:
        if new_name.strip() != "" and new_name not in players['name'].values:
            new_player = {"name": new_name}
            players_col.insert_one({ "name": new_name })
            players = pd.DataFrame(list(players_col.find()))
            st.success(f"Player '{new_name}' added.")
        elif new_name in players['name'].values:
            st.warning("Player already exists.")
        else:
            st.error("Name cannot be empty.")


from urllib.parse import quote

with st.expander("📋 Current Players"):
    player_list = players["name"].tolist()
    num_cols = 3

    # Loop through players and place them in rows of 3 columns
    for i in range(0, len(player_list), num_cols):
        cols = st.columns(num_cols)
        for j in range(num_cols):
            if i + j < len(player_list):
                player = player_list[i + j]
                player_encoded = quote(player)
                cols[j].markdown(
                    f"""
                    <a href="./Player_Dashboard?player={player_encoded}" target="_self">
                        <button style="
                            padding: 10px 16px;
                            margin: 6px 0;
                            width: 100%;
                            background-color: #262730;
                            color: #FFFFF;
                            border: 1px solid #ccc;
                            border-radius: 8px;
                            font-size: 15px;
                            cursor: pointer;
                        ">{player}</button>
                    </a>
                    """,
                    unsafe_allow_html=True
                )



#----- Section: Start a New Game----- #
st.header("Start Game:")
with st.expander("Start a New Game", expanded = False):
    # Select teams from existing players
    team1 = st.multiselect("Select Team 1 Players", options=players["name"].tolist(), key="team1")
    team2 = st.multiselect("Select Team 2 Players", options=players["name"].tolist(), key="team2")

    # Date and game ID
    game_date = st.date_input("Game Date")
    game_id = f"Game_{len(games) + 1}"

    # Start button
    if st.button("⚾ Start Game"):
        if not team1 or not team2:
            st.error("You must select at least one player for each team.")
        elif set(team1) & set(team2):
            st.error("A player cannot be on both teams.")
        else:
            new_game = {
                "game_id": game_id,
                "date": str(game_date),
                "team1": ", ".join(team1),
                "team2": ", ".join(team2),
                "team1_players": ",".join(team1),
                "team2_players": ", ".join(team2),
                "status": "active"
            }
            games_col.insert_one(new_game)
            games = pd.DataFrame(list(games_col.find()))

            st.success(f"✅ Game {game_id} started and saved!")


# ------ Section: Record an at-bat ------ #
st.header("Record At-Bats / Game:")
active_games = games[games["status"] == "active"] if "status" in games.columns else games
if active_games.empty:
    st.warning("Please start a game first.")
else:
    with st.expander("Record At-Bat", expanded=False):
        with st.form("atbat_form"):
            current_game = st.selectbox("Select Game", active_games["game_id"])
            current_game_row = active_games[active_games["game_id"] == current_game].iloc[0]
            def parse_ended_innings(val):
                if pd.isna(val) or val == "":
                    return []
                return val.split(";")

            ended_innings = parse_ended_innings(current_game_row.get("ended_innings", ""))

            current_game_atbats = atbats[atbats["game_id"] == current_game]
            all_innings = [f"{half} {i}" for i in range(1, 7) for half in ["Top", "Bottom"]]
            available_innings = [inn for inn in all_innings if inn not in ended_innings]
            if not available_innings:
                st.warning("All innings have been ended for this game.")
                st.stop()
            selected_inning = st.selectbox("Inning", available_innings)
            half_inning, inning_number = selected_inning.split()
            inning_number = int(inning_number)

            # Extract team players
            current_game_row = games[games["game_id"] == current_game].iloc[0]
            team1_players = [p.strip() for p in str(current_game_row["team1"]).split(",") if p.strip()]
            team2_players = [p.strip() for p in str(current_game_row["team2"]).split(",") if p.strip()]

            # Prefix names with team label
            team1_options = [f"Team 1 - {p}" for p in team1_players]
            team2_options = [f"Team 2 - {p}" for p in team2_players]
            all_options = team1_options + team2_options

            # Select batter and pitcher
            batter_label = st.selectbox("Select Batter", all_options)
            pitcher_label = st.selectbox("Select Pitcher", all_options)

            # Extract actual names
            batter = batter_label.split(" - ")[-1]
            pitcher = pitcher_label.split(" - ")[-1]



            strikes = st.selectbox("Strikes", [0, 1, 2, 3])
            balls = st.selectbox("Balls", [0, 1, 2, 3, 4])
            runners_on = st.selectbox("Runners on Base", [0, 1, 2, 3])
            outcome = st.selectbox("Outcome", [
                "Single", "Double", "Triple", "Home Run", "Ground Out", "Pop Out", "Line Out",
                "Strike Out", "Walk", "Fielder's Choice", "Sacrifice Fly", "Double Play", "Triple Play"
            ])
            # Automatically determine outs recorded
            if outcome in ["Ground Out", "Pop Out", "Line Out", "Strike Out", "Fielder's Choice", "Sacrifice Fly"]:
                outs_on_play = 1
            elif outcome == "Double Play":
                outs_on_play = 2
            elif outcome == "Triple Play":
                outs_on_play = 3
            else:
                outs_on_play = 0  # hits, walks, etc.
            valid_rbi_outcomes = ["Single", "Double", "Triple", "Home Run", "Sacrifice Fly", "Fielder's Choice", "Walk", "Ground Out"]
            rbi_enabled = outcome in valid_rbi_outcomes

            if outcome == "Home Run":
                rbi_default = 1 + runners_on  # 1 for the batter + number of runners
            else:
                rbi_default = 0
            
            rbis = st.number_input(
            "Runs Batted In (RBIs)",
            min_value=0,
            max_value=4,
            value=rbi_default,
            disabled= not rbi_enabled
            )


            
            st.markdown(f"**Outs recorded on this play**: `{outs_on_play}`")
            st.markdown(f"**RBIs recorded on this play**: `{rbis}`")
            # Add Checkbox to end this inning
            end_inning = st.checkbox("End this half-inning after recording this at-bat")
            submit_atbat = st.form_submit_button("Record At-Bat")

            if submit_atbat:
                if batter == pitcher:
                    st.error("⚠️ Batter and pitcher cannot be the same player.")
                else:
                    outs_on_play = 1 if outcome in ["Ground Out", "Pop Out", "Line Out", "Strike Out", "Sacrifice Fly", "Fielder's Choice"] else 0
                    atbat = {
                        "game_id": current_game,
                        "inning": f"{half_inning} {inning_number}",
                        "batter": batter,
                        "pitcher": pitcher,
                        "strikes": strikes,
                        "balls": balls,
                        "runners_on": runners_on,
                        "outcome": outcome,
                        "outs_recorded": outs_on_play,
                        "rbi": rbis
                    }
                    atbats_col.insert_one(atbat)
                    atbats = pd.DataFrame(list(atbats_col.find()))
                    st.success("✅ At-bat recorded!")
                #End the inning and update games.csv
                if end_inning:
                    if selected_inning not in ended_innings:
                        ended_innings.append(selected_inning)
                        ended_str = ";".join(ended_innings)
                        games_col.update_one({"game_id": current_game}, {"$set": {"ended_innings": ended_str}})
                        games = pd.DataFrame(list(games_col.find()))
                        st.success(f"✅ Inning '{selected_inning}' has been ended and locked. Refresh")



    # ----- Undo Last At Bats/Games Button -----
    with st.expander("Undo Last At-Bat"):
        st.subheader("Undo Last At-Bat")

        if not current_game_atbats.empty:
            last_atbat = current_game_atbats.iloc[-1]
            with st.form("undo_last_atbat_form"):
                st.write(f"Last at-bat: `{last_atbat['batter']}` vs `{last_atbat['pitcher']}` | Outcome: `{last_atbat['outcome']}`")
                confirm_last = st.checkbox("Confirm Undo Last At-Bat")
                submitted = st.form_submit_button("Undo Last At-Bat")
                if submitted and confirm_last:
                    last_id = current_game_atbats.iloc[-1]["_id"]
                    atbats_col.delete_one({"_id": last_id})
                    atbats = pd.DataFrame(list(atbats_col.find()))
                    st.success("✅ Last at-bat has been removed.")
                elif submitted and not confirm_last:
                    st.warning("Please confirm before undoing.")
        else:
            st.info("No at-bats recorded for this game yet.")

# ---- End Current Game Button ---- #
with st.expander("End Current Game"):
    st.subheader("End Current Game")

    active_games = games[games["status"] == "active"] 
    if active_games.empty:
        st.info("No active games to end.")
    else:
        current_game = st.selectbox("Select Game to End", active_games["game_id"])
        confirm_end = st.checkbox(f"Confirm end of `{current_game}`")
        team1_score = st.number_input("Enter Team 1 Score", min_value=0, max_value=99, step=1)
        team2_score = st.number_input("Enter Team 2 Score", min_value=0, max_value=99, step=1)

        if confirm_end and st.button("End Game"):
            games_col.update_one(
                {"game_id": current_game},
                {"$set": {
                    "status": "completed",
                    "team1_score": team1_score,
                    "team2_score": team2_score
                }}
            )
            games = pd.DataFrame(list(games_col.find()))
            st.success(f"✅  `{current_game}` has been marked as completed.")



# Section: Reset Data
with st.expander("Reset All Data"):
    st.subheader("Reset All Data")
    password_input = st.text_input("Enter admin password to reset data", type="password")
    confirm_reset = st.checkbox("I confirm I want to reset all data.")
    
    if st.button("Reset Data"):
        if password_input != ADMIN_PASSWORD:
            st.error("Incorrect password. Access denied.")
        elif not confirm_reset:
            st.warning("Please confirm the reset by checking the box.")
        else:
            # Perform the data reset
            players = pd.DataFrame(columns=players.columns)
            games = pd.DataFrame(columns=games.columns)
            atbats = pd.DataFrame(columns=atbats.columns)
            players_col.delete_many({})
            games_col.delete_many({})
            atbats_col.delete_many({})
            st.success("✅ Data has been reset.")





