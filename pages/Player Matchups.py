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

# MongoDB Collections
players_col = db["players"]
atbats_col = db["atbats"]
games_col = db["games"]



# Page config
st.set_page_config(page_title="Player Matchups")

players = pd.DataFrame(players_col.find())
atbats = pd.DataFrame(atbats_col.find())
games = pd.DataFrame(games_col.find())


st.title("Player Matchups")

player1 = st.selectbox("Select Player 1", sorted(players["name"].unique()))
player2 = st.selectbox("Select Player 2", sorted(players["name"].unique()), index=1)

if player1 == player2:
    st.warning("Please select two different players.")
    st.stop()

# Filter for head-to-head matchups
head_to_head = atbats[((atbats["batter"] == player1) & (atbats["pitcher"] == player2)) |
                         ((atbats["batter"] == player2) & (atbats["pitcher"] == player1))]

# Separate player 1 stats
player1_hitting = head_to_head[(head_to_head["batter"] == player1) & (head_to_head["pitcher"] == player2)]
player1_pitching = head_to_head[(head_to_head["pitcher"] == player1) & (head_to_head["batter"] == player2)]

# Separate player 2 stats
player2_hitting = head_to_head[(head_to_head["batter"] == player2) & (head_to_head["pitcher"] == player1)]
player2_pitching = head_to_head[(head_to_head["pitcher"] == player2) & (head_to_head["batter"] == player1)]

# Card style
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

def render_hitting_stats(data):
    ab = data.shape[0]
    hits = data["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
    singles = data["outcome"].eq("Single").sum()
    doubles = data["outcome"].eq("Double").sum()
    triples = data["outcome"].eq("Triple").sum()
    hr = data["outcome"].eq("Home Run").sum()
    walks = data["outcome"].eq("Walk").sum()
    rbi = data["rbi"].sum()
    strikeouts = data["outcome"].eq("Strike Out").sum()
    avg = hits / ab if ab else 0
    obp = (hits + walks) / (ab + walks) if (ab + walks) else 0
    slg = ((singles + 2*doubles + 3*triples + 4*hr) / ab) if ab else 0

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(card_style.format(label="At-Bats:", value=ab), unsafe_allow_html=True)
        st.markdown(card_style.format(label="Hits:", value=hits), unsafe_allow_html=True)
        st.markdown(card_style.format(label="RBIs:", value=int(rbi)), unsafe_allow_html=True)
        st.markdown(card_style.format(label="Strikeouts:", value=strikeouts), unsafe_allow_html=True)
        st.markdown(card_style.format(label="AVG:", value=f"{avg:.3f}"), unsafe_allow_html=True)
        st.markdown(card_style.format(label="OBP:", value=f"{obp:.3f}"), unsafe_allow_html=True)
        st.markdown(card_style.format(label="SLG:", value=f"{slg:.3f}"), unsafe_allow_html=True)
        
    with col2:
        st.markdown(card_style.format(label="Singles:", value=singles), unsafe_allow_html=True)
        st.markdown(card_style.format(label="Doubles:", value=doubles), unsafe_allow_html=True)
        st.markdown(card_style.format(label="Triples:", value=triples), unsafe_allow_html=True)
        st.markdown(card_style.format(label="Home Runs:", value=hr), unsafe_allow_html=True)
        st.markdown(card_style.format(label="Walks:", value=walks), unsafe_allow_html=True)

def render_pitching_stats(data):
    games_pitched = data["game_id"].nunique()
    total_outs = data["outs_recorded"].sum()
    innings_pitched = total_outs / 3
    walks_allowed = data["outcome"].eq("Walk").sum()
    strikeouts_pitched = data["outcome"].eq("Strike Out").sum()
    hits_allowed = data["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
    home_runs_allowed = data["outcome"].eq("Home Run").sum()
    double_plays = data["outcome"].eq("Double Play").sum()
    batters_faced = data.shape[0]
    strikes = data["strikes"].sum()
    balls = data["balls"].sum()
    k_rate = (strikeouts_pitched / batters_faced * 100) if batters_faced else 0
    whip = (walks_allowed + hits_allowed) / innings_pitched if innings_pitched else 0
    k_per_9 = (strikeouts_pitched * 9) / innings_pitched if innings_pitched else 0
    hr_per_9 = (home_runs_allowed * 9) / innings_pitched if innings_pitched else 0
    earned_runs = data["rbi"].sum()
    era = (earned_runs / innings_pitched * 9) if innings_pitched else 0

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

# Filter logs
log_cols = ["game_id", "batter", "pitcher", "strikes", "balls", "runners_on", "outcome", "outs_recorded", "rbi"]
player1_hitting_log = player1_hitting[log_cols]
player1_pitching_log = player1_pitching[log_cols]
player2_hitting_log = player2_hitting[log_cols]
player2_pitching_log = player2_pitching[log_cols]

# Display for Player 1
st.header(f" {player1}:")
st.subheader(f" Career Hitting vs {player2}")
render_hitting_stats(player1_hitting)

with st.expander(f"📂 View Hitting Matchup Game Log vs {player2}"):
    st.dataframe(player1_hitting_log)

st.subheader(f"Career Pitching vs {player2}")
render_pitching_stats(player1_pitching)

with st.expander(f"📂 View Pitching Matchup Game Log vs {player2}"):
    st.dataframe(player1_pitching_log)

st.markdown("---")

# Display for Player 2
st.header(f" {player2}:")
st.subheader(f" Career Hitting vs {player1}")
render_hitting_stats(player2_hitting)

with st.expander(f"📂 View Hitting Matchup Game Log vs {player1}"):
    st.dataframe(player2_hitting_log)

st.subheader(f"Career Pitching vs {player1}")
render_pitching_stats(player2_pitching)

with st.expander(f"📂 View Pitching Matchup Game Log vs {player1}"):
    st.dataframe(player2_pitching_log)