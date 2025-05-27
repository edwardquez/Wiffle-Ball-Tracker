import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go 


from pymongo import MongoClient
from dotenv import load_dotenv

# Load MongoDB URI from .env or environment variables
load_dotenv()
MONGO_URI = os.getenv('MONGO_URI')  

# Connect to MongoDB Atlas
client = MongoClient(MONGO_URI)
db = client['blitzballstats'] 

# Page config
st.set_page_config(page_title="Visualizations")


players_col = db["players"]
atbats_col = db["atbats"]
games_col = db["games"]

players = pd.DataFrame(list(players_col.find()))
atbats = pd.DataFrame(list(atbats_col.find()))
games = pd.DataFrame(list(games_col.find()))

st.title("Player Visualizations")

#--- Function for Preventing Key Errors with No Games Played Yet ---#
def column_has_data(df, column):
    return column in df.columns and not df[column].dropna().empty


# ==== HITTING STATS FUNCTION ====
def calculate_all_player_stats(atbats):
    player_stats = {}

    for player in pd.unique(atbats['batter'].dropna()):
        player_df = atbats[atbats['batter'] == player]
        ab = len(player_df)
        hits = player_df["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
        walks = player_df["outcome"].eq("Walk").sum()
        singles = player_df["outcome"].eq("Single").sum()
        doubles = player_df["outcome"].eq("Double").sum()
        triples = player_df["outcome"].eq("Triple").sum()
        home_runs = player_df["outcome"].eq("Home Run").sum()
        strikeouts = player_df["outcome"].eq("Strike Out").sum()
        rbis = player_df["rbi"].sum()
        avg = hits / ab if ab else 0
        obp = (hits + walks) / (ab + walks) if (ab + walks) else 0
        slg = (singles + 2*doubles + 3*triples + 4*home_runs) / ab if ab else 0

        player_stats[player] = {
            "name": player,
            "AB": ab,
            "H": hits,
            "BB": walks,
            "1B": singles,
            "2B": doubles,
            "3B": triples,
            "HR": home_runs,
            "K": strikeouts,
            "RBI": rbis,
            "AVG": round(avg, 3),
            "OBP": round(obp, 3),
            "SLG": round(slg, 3)
        }

    return pd.DataFrame(player_stats).T.reset_index(drop=True)

# ==== PITCHING STATS FUNCTION ====
def calculate_pitcher_stats(atbats):
    pitcher_stats = {}

    for pitcher in pd.unique(atbats['pitcher'].dropna()):
        pitcher_df = atbats[atbats["pitcher"] == pitcher]
        outs = pitcher_df["outs_recorded"].sum()
        ip = outs / 3
        walks = pitcher_df["outcome"].eq("Walk").sum()
        hits = pitcher_df["outcome"].isin(["Single", "Double", "Triple", "Home Run"]).sum()
        hr = pitcher_df["outcome"].eq("Home Run").sum()
        k = pitcher_df["outcome"].eq("Strike Out").sum()
        er = pitcher_df["rbi"].sum()

        era = (er / ip * 9) if ip else 0
        whip = (walks + hits) / ip if ip else 0
        k9 = (k * 9) / ip if ip else 0

        pitcher_stats[pitcher] = {
            "name": pitcher,
            "IP": ip,
            "H": hits,
            "HR": hr,
            "BB": walks,
            "K": k,
            "ER": er,
            "ERA": round(era, 2),
            "WHIP": round(whip, 2),
            "K/9": round(k9, 2)
        }

    return pd.DataFrame(pitcher_stats).T.reset_index(drop=True)

# Calculate stats
hitters = calculate_all_player_stats(atbats)
pitchers = calculate_pitcher_stats(atbats)
qualified_pitchers = pitchers[pitchers["IP"] >= 1]




# ---- RBI Leaders -----
st.subheader("RBI Leaders:")
fig_rbi_horizontal = px.bar(
    hitters.sort_values("RBI", ascending=True),  # Ascending so highest is on top
    x="RBI", y="name", color="RBI", orientation='h',
    title="Hitter Performance: RBI(Runs Batted In)"
)
fig_rbi_horizontal.update_layout(yaxis={'categoryorder': 'total ascending'})  
st.plotly_chart(fig_rbi_horizontal)



# ----Walks vs Strikeouts-----

hitters["AB"] = pd.to_numeric(hitters["AB"], errors="coerce")
hitters["BB"] = pd.to_numeric(hitters["BB"], errors="coerce")
hitters["K"] = pd.to_numeric(hitters["K"], errors="coerce")

avg_bb = hitters["BB"].mean()
avg_k = hitters["K"].mean()

st.subheader("Strikeouts vs Walks:")

fig_bb_k = px.scatter(
    hitters,
    x="BB",  # Walks
    y="K",  # Strikeouts
    text="name",  # Player name on hover
    size="AB",  # Optional: size by at-bats
    color="name",  # Optional: color by batting average
    color_continuous_scale="Plasma",
    title="Hitter Performance: K vs BB"
)

# Add quadrant lines
fig_bb_k.add_shape(
    type="line",
    x0=avg_bb, x1=avg_bb,
    y0=hitters["K"].min(), y1=hitters["K"].max(),
    line=dict(dash="dash", color="gray")
)
fig_bb_k.add_shape(
    type="line",
    x0=hitters["BB"].min(), x1=hitters["BB"].max(),
    y0=avg_k, y1=avg_k,
    line=dict(dash="dash", color="gray")
)

# Shaded rectangles for each quadrant
fig_bb_k.add_shape(
    type="rect",
    x0=hitters["BB"].min(), x1=avg_bb,
    y0=avg_k, y1=hitters["K"].max(),
    fillcolor="rgba(255, 179, 186, 0.25)",  # High K, Low BB
    line_width=0,
    layer="below"
)
fig_bb_k.add_shape(
    type="rect",
    x0=avg_bb, x1=hitters["BB"].max(),
    y0=avg_k, y1=hitters["K"].max(),
    fillcolor="rgba(255, 223, 186, 0.25)",  # High K, High BB
    line_width=0,
    layer="below"
)
fig_bb_k.add_shape(
    type="rect",
    x0=hitters["BB"].min(), x1=avg_bb,
    y0=hitters["K"].min(), y1=avg_k,
    fillcolor="rgba(186, 255, 201, 0.25)",  # Low K, Low BB
    line_width=0,
    layer="below"
)
fig_bb_k.add_shape(
    type="rect",
    x0=avg_bb, x1=hitters["BB"].max(),
    y0=hitters["K"].min(), y1=avg_k,
    fillcolor="rgba(186, 225, 255, 0.25)",  # Low K, High BB (best)
    line_width=0,
    layer="below"
)

# Add dummy invisible traces for legend
fig_bb_k.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 179, 186, 0.25)"),
    name="High K, Low BB"
))
fig_bb_k.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 223, 186, 0.25)"),
    name="High K, High BB"
))
fig_bb_k.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 255, 201, 0.25)"),
    name="Low K, Low BB"
))
fig_bb_k.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 225, 255, 0.25)"),
    name="Low K, High BB"
))

# Update axes
fig_bb_k.update_layout(
    xaxis_title="Walks (BB)",
    yaxis_title="Strikeouts (K)",
    legend=dict(title="Quadrant Key:", x=1.02, y=1),
    margin=dict(r=140)
)
fig_bb_k.update_traces(textposition="top center")
st.plotly_chart(fig_bb_k)


# ---- OBP vs SLG Quadrant Graph ----
st.subheader("OBP vs SLG (Size = HRs):")

# Ensure numeric data types
hitters["OBP"] = pd.to_numeric(hitters["OBP"], errors="coerce")
hitters["SLG"] = pd.to_numeric(hitters["SLG"], errors="coerce")
hitters["HR"] = pd.to_numeric(hitters["HR"], errors="coerce")

# Calculate averages
avg_obp = hitters["OBP"].mean()
avg_slg = hitters["SLG"].mean()

# Create scatter plot
fig_obp_slg = px.scatter(
    hitters,
    x="OBP", y="SLG",
    size="HR", color="name", hover_name="name",
    text="name",
    title="Hitter Performance: OBP vs SLG"
)

# Add quadrant lines
fig_obp_slg.add_shape(
    type="line",
    x0=avg_obp, x1=avg_obp,
    y0=hitters["SLG"].min(), y1=hitters["SLG"].max(),
    line=dict(dash="dash", color="gray")
)
fig_obp_slg.add_shape(
    type="line",
    x0=hitters["OBP"].min(), x1=hitters["OBP"].max(),
    y0=avg_slg, y1=avg_slg,
    line=dict(dash="dash", color="gray")
)

# Add shaded quadrants
fig_obp_slg.add_shape(
    type="rect",
    x0=hitters["OBP"].min(), x1=avg_obp,
    y0=avg_slg, y1=hitters["SLG"].max(),
    fillcolor="rgba(255, 179, 186, 0.25)", line_width=0, layer="below"
)
fig_obp_slg.add_shape(
    type="rect",
    x0=avg_obp, x1=hitters["OBP"].max(),
    y0=avg_slg, y1=hitters["SLG"].max(),
    fillcolor="rgba(255, 223, 186, 0.25)", line_width=0, layer="below"
)
fig_obp_slg.add_shape(
    type="rect",
    x0=hitters["OBP"].min(), x1=avg_obp,
    y0=hitters["SLG"].min(), y1=avg_slg,
    fillcolor="rgba(186, 255, 201, 0.25)", line_width=0, layer="below"
)
fig_obp_slg.add_shape(
    type="rect",
    x0=avg_obp, x1=hitters["OBP"].max(),
    y0=hitters["SLG"].min(), y1=avg_slg,
    fillcolor="rgba(186, 225, 255, 0.25)", line_width=0, layer="below"
)

# Add dummy traces for quadrant legend
fig_obp_slg.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 179, 186, 0.5)"),
    name="High SLG, Low OBP"
))
fig_obp_slg.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 223, 186, 0.5)"),
    name="High SLG, High OBP"
))
fig_obp_slg.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 255, 201, 0.5)"),
    name="Low SLG, Low OBP"
))
fig_obp_slg.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 225, 255, 0.5)"),
    name="Low SLG, High OBP"
))

# Final layout tweaks
fig_obp_slg.update_layout(
    xaxis_title="OBP (On-Base Percentage)",
    yaxis_title="SLG (Slugging Percentage)",
    legend_title="Quadrant Key:",
    margin=dict(r=40)
)
fig_obp_slg.update_traces(textposition="top center")
st.plotly_chart(fig_obp_slg)



# ---- ERA Leaders (Horizontal) ----
st.subheader("ERA Leaders:")
fig_era_horizontal = px.bar(
    qualified_pitchers.sort_values("ERA", ascending=True),
    x="ERA", y="name", color="ERA", orientation='h',
    title="Pitcher Performance: ERA(Earned Run Average)"
)
fig_era_horizontal.update_layout(yaxis={'categoryorder': 'total ascending'})
st.plotly_chart(fig_era_horizontal)




# ---- WHIP vs K/9 Quadrant Graph (with px.scatter) ----
st.subheader("WHIP vs K/9:")

qualified_pitchers["IP"] = pd.to_numeric(qualified_pitchers["IP"], errors="coerce")
qualified_pitchers["WHIP"] = pd.to_numeric(qualified_pitchers["WHIP"], errors="coerce")
qualified_pitchers["K/9"] = pd.to_numeric(qualified_pitchers["K/9"], errors="coerce")

avg_whip = qualified_pitchers["WHIP"].mean()
avg_k9 = qualified_pitchers["K/9"].mean()

fig_whip_k9 = px.scatter(
    qualified_pitchers,
    x="WHIP", y="K/9",
    size="IP", color="name", hover_name="name",
    text ="name",
    title="Pitcher Performance: WHIP vs K/9"
)

# Add quadrant lines
fig_whip_k9.add_shape(
    type="line",
    x0=avg_whip, x1=avg_whip,
    y0=qualified_pitchers["K/9"].min(), y1=qualified_pitchers["K/9"].max(),
    line=dict(dash="dash", color="gray")
)
fig_whip_k9.add_shape(
    type="line",
    x0=qualified_pitchers["WHIP"].min(), x1=qualified_pitchers["WHIP"].max(),
    y0=avg_k9, y1=avg_k9,
    line=dict(dash="dash", color="gray")
)

# Add shaded quadrants
fig_whip_k9.add_shape(
    type="rect",
    x0=qualified_pitchers["WHIP"].min(), x1=avg_whip,
    y0=avg_k9, y1=qualified_pitchers["K/9"].max(),
    fillcolor="rgba(255, 179, 186, 0.25)", line_width=0, layer="below"
)
fig_whip_k9.add_shape(
    type="rect",
    x0=avg_whip, x1=qualified_pitchers["WHIP"].max(),
    y0=avg_k9, y1=qualified_pitchers["K/9"].max(),
    fillcolor="rgba(255, 223, 186, 0.25)", line_width=0, layer="below"
)
fig_whip_k9.add_shape(
    type="rect",
    x0=qualified_pitchers["WHIP"].min(), x1=avg_whip,
    y0=qualified_pitchers["K/9"].min(), y1=avg_k9,
    fillcolor="rgba(186, 255, 201, 0.25)", line_width=0, layer="below"
)
fig_whip_k9.add_shape(
    type="rect",
    x0=avg_whip, x1=qualified_pitchers["WHIP"].max(),
    y0=qualified_pitchers["K/9"].min(), y1=avg_k9,
    fillcolor="rgba(186, 225, 255, 0.25)", line_width=0, layer="below"
)

# Add dummy traces for quadrant legend labels
fig_whip_k9.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 179, 186, 0.5)"),
    name="High K/9, Low WHIP"
))
fig_whip_k9.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 223, 186, 0.5)"),
    name="High K/9, High WHIP"
))
fig_whip_k9.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 255, 201, 0.5)"),
    name="Low K/9, Low WHIP"
))
fig_whip_k9.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 225, 255, 0.5)"),
    name="Low K/9, High WHIP"
))

# Final layout tweaks
fig_whip_k9.update_layout(
    xaxis_title="WHIP (Walks + Hits / Inning)",
    yaxis_title="K/9 (Strikeouts per 9 IP)",
    legend_title="Quadrant Key",
    margin=dict(r=40)
)
fig_whip_k9.update_traces(textposition="top center")
st.plotly_chart(fig_whip_k9)


# ---- OPS vs ERA ----

# Combine hitting (OPS = OBP + SLG) and pitching stats
hitters["OPS"] = hitters["OBP"] + hitters["SLG"]
combined = pd.merge(hitters[["name", "OPS"]], qualified_pitchers[["name", "ERA", "IP"]], on="name")

# Calculate means
avg_ops = combined["OPS"].mean()
avg_era = combined["ERA"].mean()

# Plot quadrant graph
st.subheader("OPS vs ERA:")

fig_ops_era = px.scatter(
    combined,
    x="OPS",
    y="ERA",
    text="name",
    size="IP",
    color="name",
    color_continuous_scale="Viridis",
    title="Hitter/Pitcher Performance: OPS vs ERA"
)


# Add quadrant lines
fig_ops_era.add_shape(
    type="line",
    x0=avg_ops, x1=avg_ops,
    y0=combined["ERA"].min(), y1=combined["ERA"].max(),
    line=dict(dash="dash", color="gray")
)
fig_ops_era.add_shape(
    type="line",
    x0=combined["OPS"].min(), x1=combined["OPS"].max(),
    y0=avg_era, y1=avg_era,
    line=dict(dash="dash", color="gray")
)

# Shaded quadrants
fig_ops_era.add_shape(
    type="rect",
    x0=combined["OPS"].min(), x1=avg_ops,
    y0=avg_era, y1=combined["ERA"].max(),
    fillcolor="rgba(255, 179, 186, 0.25)",  # Low OPS, High ERA
    line_width=0, layer="below"
)
fig_ops_era.add_shape(
    type="rect",
    x0=avg_ops, x1=combined["OPS"].max(),
    y0=avg_era, y1=combined["ERA"].max(),
    fillcolor="rgba(255, 223, 186, 0.25)",  # High OPS, High ERA
    line_width=0, layer="below"
)
fig_ops_era.add_shape(
    type="rect",
    x0=combined["OPS"].min(), x1=avg_ops,
    y0=combined["ERA"].min(), y1=avg_era,
    fillcolor="rgba(186, 255, 201, 0.25)",  # Low OPS, Low ERA
    line_width=0, layer="below"
)
fig_ops_era.add_shape(
    type="rect",
    x0=avg_ops, x1=combined["OPS"].max(),
    y0=combined["ERA"].min(), y1=avg_era,
    fillcolor="rgba(186, 225, 255, 0.25)",  # High OPS, Low ERA (ideal)
    line_width=0, layer="below"
)

# Add dummy traces for legend
fig_ops_era.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 179, 186, 0.25)"),
    name="Low OPS, High ERA"
))
fig_ops_era.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(255, 223, 186, 0.25)"),
    name="High OPS, High ERA"
))
fig_ops_era.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 255, 201, 0.25)"),
    name="Low OPS, Low ERA"
))
fig_ops_era.add_trace(go.Scatter(
    x=[None], y=[None],
    mode='markers',
    marker=dict(size=10, color="rgba(186, 225, 255, 0.25)"),
    name="High OPS, Low ERA"
))

# Final layout tweaks
fig_ops_era.update_layout(
    xaxis_title="OPS (OBP + SLG)",
    yaxis_title="ERA (Earned Run Average)",
    legend=dict(title="Quadrant Key:", x=1.02, y=1),
    margin=dict(r=140)
)
fig_ops_era.update_traces(textposition="top center")

st.plotly_chart(fig_ops_era)



