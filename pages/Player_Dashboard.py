import streamlit as st
import pandas as pd
import os
import urllib.parse

from urllib.parse import urlparse, parse_qs
from urllib.parse import unquote
from urllib.parse import quote
from pymongo import MongoClient
from dotenv import load_dotenv



# Page config
st.set_page_config(page_title="Player Dashboard")

# Load MongoDB URI from .env or environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')  

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['blitzballstats'] 


# Collections
players_col = db["players"]
atbats_col = db["atbats"]
games_col = db["games"]


players = pd.DataFrame(list(players_col.find()))
atbats = pd.DataFrame(list(atbats_col.find()))
games = pd.DataFrame(list(games_col.find()))


# Get query params
query_params = st.query_params
selected_player = query_params.get("player")

# Decode
if selected_player:
    selected_player = unquote(selected_player)
else:
    selected_player = None

if not selected_player or selected_player not in players["name"].values:
    st.title("Player Dashboard")
    st.markdown("### Select a player below to view their stats:")

    player_list = players["name"].tolist()
    num_cols = 3

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
                            color: #FFFFFF;
                            border: 1px solid #ccc;
                            border-radius: 8px;
                            font-size: 15px;
                            cursor: pointer;
                        ">{player}</button>
                    </a>
                    """,
                    unsafe_allow_html=True
                )
    
    st.stop()  # Prevent loading the rest of the dashboard





st.title(f" {selected_player}'s Dashboard")


# Filter for batting and pitching separately
player_batting = atbats[atbats["batter"] == selected_player]
player_pitching = atbats[atbats["pitcher"] == selected_player]


# ---------------------
# HITTING STATS SECTION
# ---------------------
st.subheader("Career Hitting Stats")


num_at_bats = len(player_batting)
hits = player_batting["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
walks = player_batting["outcome"].eq("Walk").sum()
singles = player_batting["outcome"].eq("Single").sum()
doubles = player_batting["outcome"].eq("Double").sum()
triples = player_batting["outcome"].eq("Triple").sum()
home_runs = player_batting["outcome"].eq("Home Run").sum()
strikeouts = player_batting["outcome"].eq("Strike Out").sum()
#rbis= player_batting["runners_on"].where(player_batting["outcome"].isin(["Single", "Double", "Triple", "Home Run"])).sum()
rbis = player_batting["rbi"].sum()
sac_flies = player_batting["outcome"].eq("Sacrifice Fly").sum()
xbh = player_batting["outcome"].isin(["Double", "Triple", "Home Run"]).sum()
batting_average = hits / num_at_bats if num_at_bats else 0
obp = (hits + walks) / (num_at_bats + walks) if (num_at_bats + walks) else 0
slugging = (
    singles + 2 * doubles + 3 * triples + 4 * home_runs
) / num_at_bats if num_at_bats else 0
k_rate = round((strikeouts / num_at_bats) * 100, 2) if num_at_bats else 0 



card_style = """
    <div style="
        padding: 12px;
        margin-bottom: 10px;
        border: 1px solid #333;
        border-radius: 8px;
        background-color: #1f1f2e;
        color: #f1f1f1;
        font-size: 16px;">
        <b>{label}</b> {value}
    </div>
"""

col1, col2 = st.columns(2)

with col1:
    st.markdown(card_style.format(label="Games Played:", value=player_batting["game_id"].nunique()), unsafe_allow_html=True)
    st.markdown(card_style.format(label="At-Bats:", value=num_at_bats), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Hits:", value=hits), unsafe_allow_html=True)
    st.markdown(card_style.format(label="AVG:", value=f"{batting_average:.3f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="OBP:", value=f"{obp:.3f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="SLG:", value=f"{slugging:.3f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Extra-Base Hits (XBH):", value=xbh), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Sacrifice Fly:", value=sac_flies), unsafe_allow_html=True)
with col2:
    st.markdown(card_style.format(label="RBIs:", value=int(rbis)), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Walks:", value=walks), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Strikeouts:", value=strikeouts), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Singles:", value=singles), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Doubles:", value=doubles), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Triples:", value=triples), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Home Runs:", value=home_runs), unsafe_allow_html=True)
    st.markdown(card_style.format(label="K%:", value=k_rate), unsafe_allow_html=True)

# Group hitting stats per game
hitting_game_log = []

for game_id, group in player_batting.groupby("game_id"):
    at_bats = len(group)
    hits = group["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
    singles = group["outcome"].eq("Single").sum()
    doubles = group["outcome"].eq("Double").sum()
    triples = group["outcome"].eq("Triple").sum()
    home_runs = group["outcome"].eq("Home Run").sum()
    walks = group["outcome"].eq("Walk").sum()
    strikeouts = group["outcome"].eq("Strike Out").sum()
    sacrifice_flies = group["outcome"].eq("Sacrifice Fly").sum()
    xbh = doubles + triples + home_runs
    rbis = group["rbi"].sum()
    avg = hits / at_bats if at_bats else 0
    obp = (hits + walks) / (at_bats + walks) if (at_bats + walks) else 0
    slg = (singles + 2*doubles + 3*triples + 4*home_runs) / at_bats if at_bats else 0
    k_rate = round((strikeouts / num_at_bats) * 100, 2) if num_at_bats else 0 

    hitting_game_log.append({
        "Game ID": game_id,
        "At-Bats": at_bats,
        "Hits": hits,
        "Singles": singles,
        "Doubles": doubles,
        "Triples": triples,
        "Home Runs": home_runs,
        "XBH": xbh,
        "Walks": walks,
        "Strikeouts": strikeouts,
        "Sac Flies": sacrifice_flies,
        "RBIs": int(rbis),
        "AVG": round(avg, 3),
        "OBP": round(obp, 3),
        "SLG": round(slg, 3),
        "K%": k_rate
    })

hitting_game_log_df = pd.DataFrame(hitting_game_log)

if not hitting_game_log_df.empty:
    hitting_game_log_df = hitting_game_log_df.merge(games[["game_id", "date"]], left_on="Game ID", right_on="game_id", how="left")
    hitting_game_log_df["date"] = pd.to_datetime(hitting_game_log_df["date"])
    hitting_game_log_df = hitting_game_log_df.sort_values(by="date")
    hitting_game_log_df.drop(columns=["game_id"], inplace=True)

    # Movees date to the first column of the game log
    cols = hitting_game_log_df.columns.tolist()
    cols.insert(0, cols.pop(cols.index("date")))
    hitting_game_log_df = hitting_game_log_df[cols]


    # Shows hitting game log
    with st.expander("📂 View Hitting Game Log"):
        st.write("Game-by-game hitting stats:")
        st.dataframe(hitting_game_log_df)
else: 
    st.info("No Hitting game log data available for this player.")


# ---------------------
# PITCHING STATS SECTION
# ---------------------
st.subheader("Career Pitching Stats")

games_pitched = player_pitching["game_id"].nunique()
total_outs = player_pitching["outs_recorded"].sum()
innings_pitched = total_outs / 3
walks_allowed = player_pitching["outcome"].eq("Walk").sum()
strikeouts_pitched = player_pitching["outcome"].eq("Strike Out").sum()
hits_allowed = player_pitching["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
home_runs_allowed = player_pitching["outcome"].eq("Home Run").sum()
double_plays = player_pitching["outcome"].eq("Double Play").sum()
batters_faced = player_pitching.shape[0]
strikes = player_pitching["strikes"].sum()
balls = player_pitching["balls"].sum()
k_rate = (strikeouts_pitched / batters_faced * 100) if batters_faced else 0
whip = (walks_allowed + hits_allowed) / innings_pitched if innings_pitched else 0
k_per_9 = (strikeouts_pitched * 9) / innings_pitched if innings_pitched else 0
hr_per_9 = (home_runs_allowed * 9) / innings_pitched if innings_pitched else 0
earned_runs = player_pitching["rbi"].sum()


era = (earned_runs / innings_pitched * 9) if innings_pitched else 0


card_style = """
    <div style="
        padding: 12px;
        margin-bottom: 10px;
        border: 1px solid #333;
        border-radius: 8px;
        background-color: #1f1f2e;
        color: #f1f1f1;
        font-size: 16px;">
        <b>{label}</b> {value}
    </div>
"""

col1, col2 = st.columns(2)

with col1:
    st.markdown(card_style.format(label="Games Pitched:", value=games_pitched), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Innings Pitched:", value=f"{innings_pitched:.1f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Earned Runs:", value=int(earned_runs)), unsafe_allow_html=True)
    st.markdown(card_style.format(label="ERA:", value=f"{era:.2f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Total Outs:", value=total_outs), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Hits Allowed:", value=hits_allowed), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Walks Allowed:", value=walks_allowed), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Total Strikes:", value=strikes), unsafe_allow_html=True)
with col2:
    st.markdown(card_style.format(label="Home Runs Allowed:", value=home_runs_allowed), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Strikeouts:", value=strikeouts_pitched), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Double Plays:", value=double_plays), unsafe_allow_html=True)
    st.markdown(card_style.format(label="K%:", value=f"{k_rate:.1f}%"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="WHIP:", value=f"{whip:.2f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="K/9:", value=f"{k_per_9:.2f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="HR/9:", value=f"{hr_per_9:.2f}"), unsafe_allow_html=True)
    st.markdown(card_style.format(label="Total Balls:", value=balls), unsafe_allow_html=True)


# Group pitching stats per game
pitching_game_log = []


for game_id, group in player_pitching.groupby("game_id"):
    outs = group["outs_recorded"].sum()
    ip = outs / 3
    walks = group["outcome"].eq("Walk").sum()
    strikeouts = group["outcome"].eq("Strike Out").sum()
    home_runs = group["outcome"].eq("Home Run").sum()
    double_plays = group["outcome"].eq("Double Play").sum()
    triple_plays = group["outcome"].eq("Triple Play").sum()
    earned_runs = group["rbi"].sum() 
    totalstrikes = group["strikes"].sum()
    totalballs = group["balls"].sum()
    era = (earned_runs / ip * 9) if ip else 0
    whip = (walks + group["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()) / ip if ip else 0
    k9 = (strikeouts / ip * 9) if ip else 0
    hr9 = (home_runs / ip * 9) if ip else 0
    

    pitching_game_log.append({
        "Game ID": game_id,
        "Innings Pitched": round(ip, 1),
        "ERA": round(era, 2),
        "Outs": outs,
        "Earned Runs": int(earned_runs),
        "Walks": walks,
        "Strikeouts": strikeouts,
        "Home Runs": home_runs,
        "Double Plays": double_plays,
        "Triple Plays": triple_plays,
        "WHIP": round(whip, 2),
        "K/9": round(k9, 2),
        "HR/9": round(hr9, 2),
        "Balls": totalballs,
        "Strikes": totalstrikes
    })

pitching_game_log_df = pd.DataFrame(pitching_game_log)
if not pitching_game_log_df.empty:
    pitching_game_log_df = pitching_game_log_df.merge(games[["game_id", "date"]], left_on="Game ID", right_on="game_id", how="left")
    pitching_game_log_df["date"] = pd.to_datetime(pitching_game_log_df["date"])
    pitching_game_log_df = pitching_game_log_df.sort_values(by="date")
    pitching_game_log_df.drop(columns=["game_id"], inplace=True)
    cols = pitching_game_log_df.columns.tolist()
    cols.insert(0, cols.pop(cols.index("date")))
    pitching_game_log_df = pitching_game_log_df[cols]
    
# Shows pitching game log
    with st.expander("📂 View Pitching Game Log"):
        st.write("Game-by-game pitching stats:")
        st.dataframe(pitching_game_log_df)
else: 
    st.info("No Pitching game log data available for this player.")