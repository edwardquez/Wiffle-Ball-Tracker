import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from html import escape

import styles as ui
import stats
from db import league

# Page setup (must come first), then the shared look
st.set_page_config(page_title="Visualizations", layout="wide")
ui.apply()

# League tables, shared and cached for a few seconds (see db.py)
lg = league()

# Tabs styled like the rest of the site: navy underline, muted labels
st.markdown(f"""
<style>
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:26px; }}
[data-testid="stTabs"] button[role="tab"] {{ padding:10px 2px; }}
[data-testid="stTabs"] button[role="tab"] p {{ font-size:15px; color:{ui.MUTED}; }}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p {{ color:{ui.INK}; font-weight:600; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color:{ui.INK} !important; height:2px; }}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ background-color:{ui.RULE}; }}
</style>
""", unsafe_allow_html=True)

title_col, season_col = st.columns([3, 1], vertical_alignment="bottom")
title_col.title("Visualizations", anchor=False)
# Career (every game) or one season; every chart on the page follows this
season_pick = season_col.selectbox("Season", ["Career"] + [str(y) for y in stats.seasons(lg)], key="viz_season")
year = None if season_pick == "Career" else int(season_pick)
lgs = lg if year is None else stats.season_league(lg, year)

# Shared definitions from stats.py (same numbers as every other page)
bat_table = lgs.advanced_batting()       # standard stats plus wOBA, wRC+, ISO, BABIP
pit_table = lgs.advanced_pitching()      # standard stats plus FIP, ERA-, K-BB%, opponent OPS
hitters = bat_table.rename_axis("name").reset_index()
pitchers = pit_table.rename_axis("name").reset_index()
qualified_pitchers = pitchers[pitchers["IP"] >= 1].copy()
for df in (hitters, qualified_pitchers):
    for col in df.columns.drop("name"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)

if hitters.empty:
    st.info("No at-bats recorded yet. Charts appear once games are played.")
    st.stop()

# Same small-sample cutoffs as the Standings page
SMALL_PA, SMALL_BF, SMALL_WAR = 15, 12, 30


# ---------- Initials for the dots, and the player key ---------- #
def make_initials(names):
    out, used = {}, set()
    for n in sorted(names):
        ini = n[:2].upper()
        if ini in used and len(n) > 1:      # two players starting the same way: first + last letter
            ini = (n[0] + n[-1]).upper()
        used.add(ini)
        out[n] = ini
    return out


everyone = sorted(set(hitters["name"]) | set(qualified_pitchers["name"]))
INITIALS = make_initials(everyone)

key_items = "".join(
    "<span style='display:inline-flex; align-items:center; gap:7px;'>"
    f"<span style='display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; "
    f"border-radius:50%; background:{ui.INK}; color:{ui.CREAM}; font-size:10px; font-weight:600; letter-spacing:0.3px;'>"
    f"{INITIALS[n]}</span>{escape(n)}</span>"
    for n in everyone
)
ui.html(
    "<div style='display:flex; flex-wrap:wrap; align-items:center; gap:8px 18px; font-size:14px; margin:-4px 0 12px;'>"
    f"<span style='font-size:12px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:{ui.MUTED};'>Players</span>"
    f"{key_items}</div>"
)


# ---------- Building blocks ---------- #
# Quadrant tints (fill, key-swatch edge): best, worst, and the two mixed quadrants
TINT = {
    "best": ("rgba(46,107,78,0.13)", "#7FA98F"),
    "worst": ("rgba(168,67,44,0.11)", "#C9826F"),
    "mixA": ("rgba(63,95,134,0.11)", "#7F9BBE"),
    "mixB": ("rgba(154,107,18,0.12)", "#C49A45"),
}
CHART_CONFIG = {"displayModeBar": False}


def section_heading(title, top=48):
    term = CHART_TERMS.get(title)
    ui.html(
        f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:12px; "
        f"margin:{top}px 0 24px; padding-bottom:8px; border-bottom:2px solid {ui.INK};'>"
        f"<span role='heading' aria-level='2' style='font-size:12px; font-weight:600; letter-spacing:1.6px; "
        f"text-transform:uppercase;'>{title}</span>{ui.glossary_link(term) if term else ''}</div>"
    )


# Glossary entry for each chart's "What's this?" link (chart title -> term on the Glossary page)
CHART_TERMS = {
    "RBI leaders": "rbi", "Strikeouts vs walks": "kpct", "OBP vs SLG": "obp", "ERA leaders": "era",
    "WHIP vs K/9": "whip", "OPS vs ERA": "ops", "K% minus BB%": "kbb", "Efficiency": "strpct",
    "Pressure pitching": "ops", "Runners on vs bases empty": "ops", "Trouble innings": "era",
    "What batters do against each pitcher": "codes", "How each hitter's plate appearances end": "codes",
    "Teammate chemistry": "winpct", "Every batter vs every pitcher · OBP": "obp",
    "Every batter vs every pitcher · OPS": "ops", "Percentile rankings": "percentile", "WAR race": "war",
}


def fig_title(title, sub):
    term = CHART_TERMS.get(title)
    what = f" · {ui.glossary_link(term)}" if term else ""
    return (f"<div style='font-family:{ui.SERIF}; font-size:22px; font-weight:500; line-height:1.2;'>{title}</div>"
            f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:4px;'>{sub}{what}</div>")


def leader_bars(title, sub, data, col, digits, low_is_best=False):
    """Uniform navy bars, best first; the leader's name and value are bold."""
    if data.empty:
        ui.html(fig_title(title, sub) + f"<p style='color:{ui.MUTED}; font-size:14px;'>Not enough data yet.</p>")
        return
    data = data.sort_values([col, "name"], ascending=[low_is_best, True])
    best = data[col].iloc[0]
    top = data[col].max() or 1
    rows = []
    for _, r in data.iterrows():
        v = r[col]
        weight = 600 if v == best else 400
        width = 0 if v == 0 else max(v / top * 100, 2)
        rows.append(
            f"<div {ui.TAP} style='display:grid; grid-template-columns:72px minmax(0,1fr) 52px; "
            "align-items:center; gap:12px; min-height:26px;'>"
            f"<span style='font-size:14px; font-weight:{weight};'>{escape(r['name'])}</span>"
            f"<div style='height:14px; background:#EFEAE0;'><div style='height:14px; width:{width:.1f}%; background:{ui.INK};'></div></div>"
            f"<span style='text-align:right; font-family:{ui.MONO}; font-size:14px; font-weight:{weight};'>{v:.{digits}f}</span>"
            + ui.tip(f"<b>{escape(r['name'])}</b><br>{escape(title.replace(' leaders', ''))}: {v:.{digits}f}")
            + "</div>"
        )
    ui.html(fig_title(title, sub)
            + f"<div style='display:flex; flex-direction:column; gap:8px; margin-top:16px;'>{''.join(rows)}</div>")


def quadrant_chart(title, sub, data, x, y, size, x_title, y_title, quads, fx, fy):
    """Scatter with pastel quadrants split at the averages, navy initial dots sized by `size`.

    quads = {"tl": (label, tint), "tr": ..., "bl": ..., "br": ...}  (top/bottom = high/low y,
    left/right = low/high x)."""
    data = data.dropna(subset=[x, y, size])
    if len(data) < 2:
        ui.html(fig_title(title, sub) + f"<p style='color:{ui.MUTED}; font-size:14px;'>Not enough data yet.</p>")
        return

    def domain(v):
        lo, hi = v.min(), v.max()
        pad = (hi - lo) * 0.14 or 1
        return lo - pad, hi + pad

    (x0, x1), (y0, y1) = domain(data[x]), domain(data[y])
    mx, my = data[x].mean(), data[y].mean()

    # Quadrant key above the chart, in the same 2x2 arrangement as the chart
    key = "".join(
        "<span style='display:inline-flex; align-items:center; gap:8px;'>"
        f"<span style='flex:none; width:12px; height:12px; background:{TINT[quads[p][1]][0]}; "
        f"border:1px solid {TINT[quads[p][1]][1]};'></span>{quads[p][0]}</span>"
        for p in ("tl", "tr", "bl", "br")
    )
    ui.html(fig_title(title, sub)
            + "<div style='display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px 16px; "
            f"font-size:12px; color:{ui.BODY}; margin-top:12px;'>{key}</div>")

    fig = go.Figure()
    for pos, (qx0, qx1, qy0, qy1) in {
        "tl": (x0, mx, my, y1), "tr": (mx, x1, my, y1),
        "bl": (x0, mx, y0, my), "br": (mx, x1, y0, my),
    }.items():
        fig.add_shape(type="rect", x0=qx0, x1=qx1, y0=qy0, y1=qy1, fillcolor=TINT[quads[pos][1]][0],
                      line_width=0, layer="below")
    dash = dict(color="#A49C8C", width=1, dash="dash")
    fig.add_shape(type="line", x0=mx, x1=mx, y0=y0, y1=y1, line=dash, layer="below")
    fig.add_shape(type="line", x0=x0, x1=x1, y0=my, y1=my, line=dash, layer="below")

    s = data[size]
    span = s.max() - s.min()
    sizes = 24 + ((s - s.min()) / span * 12 if span else 6)
    fig.add_trace(go.Scatter(
        x=data[x], y=data[y], mode="markers+text",
        text=[INITIALS[n] for n in data["name"]],
        textposition="middle center",
        textfont=dict(color=ui.CREAM, size=10, family="IBM Plex Sans, sans-serif"),
        marker=dict(size=sizes, color=ui.INK, opacity=1, line=dict(color=ui.CREAM, width=2)),
        customdata=list(zip(data["name"], s)),
        hovertemplate=(f"<b>%{{customdata[0]}}</b><br>{x}: %{{x:{fx}}}<br>{y}: %{{y:{fy}}}"
                       f"<br>{size}: %{{customdata[1]:.3~f}}<extra></extra>"),
        showlegend=False,
    ))
    axis = dict(showgrid=False, zeroline=False, showline=True, linecolor="#B9B2A4", ticks="outside",
                tickcolor="#B9B2A4", ticklen=4, automargin=True, nticks=5, tickfont=dict(family="IBM Plex Mono, monospace", size=11, color=ui.MUTED),
                title_font=dict(size=12, color=ui.MUTED),
                title_standoff=18)   # gap between the axis title and the tick labels
    fig.update_layout(
        height=380, margin=dict(l=60, r=12, t=12, b=56),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=ui.INK),
        xaxis=dict(axis, range=[x0, x1], title_text=x_title, tickformat=fx),
        yaxis=dict(axis, range=[y0, y1], title_text=y_title, tickformat=fy),
        hoverlabel=dict(bgcolor=ui.CREAM, bordercolor=ui.INK, font=dict(color=ui.INK, size=13)),
    )
    st.plotly_chart(fig, config=CHART_CONFIG, theme=None)


# ---------- Shared color helpers for the new charts ---------- #
# Diverging scale: brick (worse / pitcher ahead) -> neutral -> steel blue (better / batter ahead).
# Steel blue rather than the site's navy: navy turns gray when lightened, which reads as "average".
NEUTRAL = "#EFEAE0"
GOOD = "#2A5F9E"
LIGHT_TEXT_FROM = 0.55     # past this share of the way to a pole, cell text switches to cream


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """Color t of the way from a to b (hex in, hex out)."""
    t = max(0.0, min(1.0, float(t)))
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(_rgb(a), _rgb(b)))


def diverging(score):
    """score in [-1, 1]: -1 brick, 0 neutral, +1 navy. Returns (fill, text color)."""
    if pd.isna(score):
        return ui.PANEL, ui.MUTED
    fill = mix(NEUTRAL, GOOD if score > 0 else ui.LOSS, abs(score))
    return fill, (ui.CREAM if abs(score) >= LIGHT_TEXT_FROM else ui.INK)


def swatch(color, label, border=None):
    edge = border or color
    return ("<span style='display:inline-flex; align-items:center; gap:7px;'>"
            f"<span style='flex:none; width:12px; height:12px; background:{color}; border:1px solid {edge};'></span>"
            f"{label}</span>")


def legend_row(items):
    return (f"<div style='display:flex; flex-wrap:wrap; gap:6px 18px; font-size:12px; color:{ui.BODY}; "
            f"margin:12px 0 14px;'>{''.join(items)}</div>")


def empty_note(text="Not enough data yet."):
    return f"<p style='color:{ui.MUTED}; font-size:14px;'>{text}</p>"


# ================================================================ VALUE
def percentile_sliders(player):
    """Baseball Savant-style percentile ranks for one player, grouped Value / Hitting / Pitching."""
    w = stats.war(lg, season=year)
    w = w[w["G"] > 0]
    bat = bat_table[bat_table["PA"] > 0]
    pit = pit_table[pit_table["BF"] > 0]
    groups = [
        ("Value", w, [("WAR", "WAR", False, lambda v: f"{v:+.1f}"),
                      ("Batting runs", "Batting runs", False, lambda v: f"{v:+.1f}"),
                      ("Pitching runs", "Pitching runs", False, lambda v: f"{v:+.1f}")]),
        ("Hitting", bat, [("wOBA", "wOBA", False, ui.rate),
                          ("AVG", "Batting average", False, ui.rate), ("OBP", "On-base %", False, ui.rate),
                          ("SLG", "Slugging %", False, ui.rate), ("BB%", "Walk rate", False, lambda v: f"{v * 100:.1f}%"),
                          ("K%", "Strikeout rate", True, lambda v: f"{v * 100:.1f}%")]),
        ("Pitching", pit, [("FIP", "FIP", True, lambda v: f"{v:.2f}"),
                           ("ERA", "ERA", True, lambda v: f"{v:.2f}"), ("WHIP", "WHIP", True, lambda v: f"{v:.2f}"),
                           ("K%", "Strikeout rate", False, lambda v: f"{v * 100:.1f}%"),
                           ("BB/9", "Walks per 9", True, lambda v: f"{v:.1f}"),
                           ("STR%", "Strike %", False, lambda v: f"{v * 100:.1f}%")]),
    ]
    pa = float(bat_table["PA"].get(player, 0) or 0)
    bf = float(pit_table["BF"].get(player, 0) or 0)
    small = {"Value": pa + bf < SMALL_WAR, "Hitting": pa < SMALL_PA, "Pitching": bf < SMALL_BF}
    small_text = {"Value": f"{int(pa + bf)} PA + batters faced", "Hitting": f"{int(pa)} plate appearances",
                  "Pitching": f"{int(bf)} batters faced"}

    parts = []
    for group, table, rows in groups:
        if player not in table.index:
            continue
        tag = ui.small_sample(f"Only {small_text[group]}") if small[group] else ""
        parts.append(f"<div style='margin:22px 0 6px; font-size:12px; font-weight:600; letter-spacing:1.4px; "
                     f"text-transform:uppercase; color:{ui.MUTED};'>{group}{tag}</div>")
        for col, label, lower_better, fmt in rows:
            vals = table[col].dropna()
            if player not in vals.index:
                continue
            n = len(vals)
            # Percentile rank among players with a value: 100 = best in the league, 0 = worst
            r = vals.rank(ascending=not lower_better, method="average")
            pct = 50.0 if n < 2 else float((r[player] - 1) / (n - 1) * 100)
            fill, text = diverging((pct - 50) / 50)
            parts.append(
                f"<div {ui.TAP} style='display:grid; grid-template-columns:minmax(0,130px) minmax(0,1fr) 64px; align-items:center; "
                "gap:14px; min-height:40px;'>"
                f"<span style='font-size:14px;'>{label}</span>"
                "<div style='position:relative; height:28px;'>"
                f"<div style='position:absolute; left:0; right:0; top:12px; height:4px; background:{ui.TRACK};'></div>"
                f"<div style='position:absolute; left:50%; top:7px; width:1px; height:14px; background:#CFC8BA;'></div>"
                f"<div style='position:absolute; left:0; top:12px; height:4px; width:{pct:.1f}%; background:{fill};'></div>"
                f"<div style='position:absolute; left:{pct:.1f}%; top:0; transform:translateX(-50%); width:28px; "
                f"height:28px; border-radius:50%; background:{fill}; border:2px solid {ui.CREAM}; box-sizing:border-box; "
                f"display:flex; align-items:center; justify-content:center; font-family:{ui.MONO}; font-size:11px; "
                f"font-weight:600; color:{text};'>{pct:.0f}</div></div>"
                f"<span style='text-align:right; font-family:{ui.MONO}; font-size:14px;'>{fmt(vals[player])}</span>"
                + ui.tip(f"<b>{escape(label)}: {escape(fmt(vals[player]))}</b><br>Better than {pct:.0f}% of the league "
                         f"({n} players with this stat)")
                + "</div>"
            )
    if not parts:
        ui.html(empty_note())
        return
    ui.html(
        legend_row([swatch(ui.LOSS, "Worse than the league"), swatch(NEUTRAL, "Middle", "#CFC8BA"),
                    swatch(GOOD, "Better than the league")])
        + f"<div style='font-size:13px; color:{ui.MUTED};'>Percentile rank among every player with that stat this "
          f"{'career view' if year is None else 'season'}: 100 is the best in the league, 0 the worst. "
          "Lower is better for strikeout rate as a hitter, FIP, ERA, WHIP and walks per 9.</div>"
        + "".join(parts)
    )


# Line colors (validated colorblind-safe on the cream background); only the first four are used, for the
# highlighted players. Names sit at the line ends so color is never the only way to tell lines apart.
LINE_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER_LINE = "#CBC4B5"


@st.cache_data(ttl=30, show_spinner="Building the WAR race...")
def _race(_league, key):
    return stats.war_race(_league)


def war_race_chart():
    done = lgs.completed
    games, values = _race(lgs, (year, tuple(done["game_id"]), len(lgs.pa)))
    if len(games) < 2 or values.empty:
        ui.html(empty_note("The WAR race needs at least two completed games."))
        return
    final = values.ffill().iloc[-1].sort_values(ascending=False)
    roster = sorted(values.columns)
    picks = st.multiselect("Highlight up to 4 players", roster, default=list(final.index[:3]), max_selections=4,
                           key="race_pick")
    # Highlighted players take the four most distinct colors; a player keeps his color while he stays
    # highlighted (adding or removing someone else doesn't repaint him).
    held = {n: c for n, c in st.session_state.get("race_colors", {}).items() if n in picks}
    for n in picks:
        if n not in held:
            held[n] = next(c for c in LINE_COLORS[:4] if c not in held.values())
    st.session_state["race_colors"] = held
    color_of = held
    ui.html(legend_row([swatch(color_of.get(n, ui.INK), escape(n)) for n in picks]
                       + [swatch(OTHER_LINE, "Everyone else")]))

    fig = go.Figure()
    x = games["n"]
    hover_dates = [ui.date_text(d) for d in games["date"]]
    for name in sorted(roster, key=lambda n: n in picks):          # highlighted lines drawn on top
        y = values[name]
        on = name in picks
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", connectgaps=False, name=name, showlegend=False,
            line=dict(color=color_of.get(name, ui.INK) if on else OTHER_LINE, width=2.5 if on else 1.5),
            customdata=list(zip(games["match_no"], hover_dates)),
            hovertemplate=f"<b>{escape(name)}</b><br>After game %{{x}} (match %{{customdata[0]}}, %{{customdata[1]}})"
                          "<br>WAR %{y:+.2f}<extra></extra>",
        ))
    # Direct labels at the line ends, nudged apart so they don't overlap
    ends = sorted(((float(values[n].ffill().iloc[-1]), n) for n in picks), reverse=True)
    span = (values.max().max() - values.min().min()) or 1
    placed = []
    for yv, name in ends:
        ylab = yv if not placed else min(yv, placed[-1] - span * 0.07)
        placed.append(ylab)
        fig.add_annotation(x=x.iloc[-1], y=ylab, text=f"<b>{escape(name)}</b> {yv:+.1f}", showarrow=False,
                           xanchor="left", xshift=8, font=dict(size=12, color=ui.INK))
    fig.add_hline(y=0, line=dict(color="#A49C8C", width=1, dash="dash"), layer="below")
    axis = dict(showgrid=False, zeroline=False, showline=True, linecolor="#B9B2A4", ticks="outside",
                tickcolor="#B9B2A4", ticklen=4, tickfont=dict(family="IBM Plex Mono, monospace", size=11, color=ui.MUTED),
                title_font=dict(size=12, color=ui.MUTED), title_standoff=18)
    fig.update_layout(
        height=380, margin=dict(l=60, r=110, t=12, b=56), hovermode="closest",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Sans, sans-serif", color=ui.INK),
        xaxis=dict(axis, title_text="Completed games", dtick=1 if len(x) <= 16 else None,
                   range=[0.8, len(x) + 0.2]),
        yaxis=dict(axis, title_text="WAR (to date)", tickformat="+.1f"),
        hoverlabel=dict(bgcolor=ui.CREAM, bordercolor=ui.INK, font=dict(color=ui.INK, size=13)),
    )
    st.plotly_chart(fig, config=CHART_CONFIG, theme=None)


# ================================================================ HITTING (new)
MIX_COLORS = {   # outs in brick and gray; reaching base in a navy ramp that darkens with power
    "Strikeout": ui.LOSS, "In play, no hit": "#CFC8BA", "Walk": "#B3C3D9",
    "Single": "#7F98BC", "Double": "#536F9B", "Triple": "#2F4B78", "Home run": ui.INK,
}


def outcome_mix_chart(by="batter"):
    """by='batter': how each hitter's PAs end (most on base first).
    by='pitcher': how PAs end against each pitcher (fewest on base first)."""
    pitching = by == "pitcher"
    mix_t = stats.outcome_mix(lgs.pa, by=by)
    mix_t = mix_t[mix_t["PA"] > 0]
    if pitching:
        mix_t = mix_t[mix_t.index.isin(qualified_pitchers["name"])]
    if mix_t.empty:
        ui.html(empty_note())
        return
    on_base = mix_t[["Walk", "Single", "Double", "Triple", "Home run"]].sum(axis=1)
    limit, unit = (SMALL_BF, "batters faced") if pitching else (SMALL_PA, "plate appearances")
    rows = []
    for name in on_base.sort_values(ascending=pitching).index:
        r = mix_t.loc[name]
        segs = []
        start = 0.0                      # where this segment starts along the bar, for the tooltip's side
        for label, color in MIX_COLORS.items():
            share = r[label]
            if share <= 0:
                continue
            mid = start + share / 2
            start += share
            # On a phone the bar starts mid-screen: centered fits up to ~60% along, past that align right
            side = "" if mid < 0.6 else "wf-r"
            dark = color in (ui.LOSS, "#536F9B", "#2F4B78", ui.INK)
            text = f"{share * 100:.0f}%" if share >= 0.12 else ""
            segs.append(f"<div {ui.TAP} style='flex:{share:.4f} 1 0; min-width:3px; height:24px; background:{color}; "
                        f"display:flex; align-items:center; justify-content:center; font-family:{ui.MONO}; "
                        f"font-size:11px; color:{ui.CREAM if dark else ui.INK};'>{text}"
                        + ui.tip(f"<b>{escape(name)} · {label}</b><br>{round(share * r['PA'])} of {int(r['PA'])} "
                                 f"{'batters faced' if pitching else 'plate appearances'} ({share * 100:.0f}%)", side)
                        + "</div>")
        small = ui.small_sample(f"Only {int(r['PA'])} {unit}") if r["PA"] < limit else ""
        rows.append("<div style='display:grid; grid-template-columns:minmax(0,150px) minmax(0,1fr) 52px; "
                    "align-items:center; gap:12px; min-height:32px;'>"
                    f"<span style='font-size:14px; white-space:nowrap;'>{escape(name)}{small}</span>"
                    f"<div style='display:flex; gap:2px;'>{''.join(segs)}</div>"
                    f"<span style='text-align:right; font-family:{ui.MONO}; font-size:13px; color:{ui.MUTED};'>"
                    f"{int(r['PA'])} {'BF' if pitching else 'PA'}</span></div>")
    title = (("What batters do against each pitcher", "Share of batters faced · fewest reaching base first · 1+ IP")
             if pitching else ("How each hitter's plate appearances end", "Share of plate appearances · most often on base first"))
    ui.html(fig_title(*title)
            + legend_row([swatch(c, lab) for lab, c in MIX_COLORS.items()])
            + f"<div style='display:flex; flex-direction:column; gap:6px;'>{''.join(rows)}</div>"
            + f"<p style='margin-top:10px; font-size:12px; color:{ui.MUTED};'>In play, no hit: ground, pop and line outs, "
              "sac flies, double plays, fielder's choices and reaching on an error.</p>")


def runner_split_chart(by="batter"):
    """Hitters: OPS with runners on vs bases empty. Pitchers (by='pitcher'): OPS allowed in each."""
    pitching = by == "pitcher"
    title = ("Pressure pitching", "OPS allowed with runners on vs bases empty · best under pressure first · 1+ IP") \
        if pitching else ("Runners on vs bases empty", "OPS in each situation · biggest jump with runners on first")
    sp = stats.runner_splits(lgs.pa, by=by).dropna(subset=["OPS on", "OPS empty"])
    if pitching:
        sp = sp[sp.index.isin(qualified_pitchers["name"])]
    if sp.empty:
        ui.html(fig_title(*title) + empty_note())
        return
    sp["diff"] = sp["OPS on"] - sp["OPS empty"]
    top = max(sp["OPS on"].max(), sp["OPS empty"].max(), 0.001) * 1.08
    rows = []
    for name, r in sp.sort_values("diff", ascending=pitching).iterrows():
        a, b = r["OPS empty"] / top * 100, r["OPS on"] / top * 100
        lo, hi = min(a, b), max(a, b)
        few = min(r["PA on"], r["PA empty"]) < 8
        small = ui.small_sample(f"{int(r['PA on'])} PA with runners on, {int(r['PA empty'])} with bases empty") if few else ""
        sign = "+" if r["diff"] >= 0 else "−"
        rows.append(
            f"<div {ui.TAP} style='display:grid; grid-template-columns:minmax(0,150px) minmax(0,1fr) 64px; align-items:center; "
            "gap:12px; min-height:34px;'>"
            f"<span style='font-size:14px; white-space:nowrap;'>{escape(name)}{small}</span>"
            "<div style='position:relative; height:20px;'>"
            f"<div style='position:absolute; left:0; right:0; top:9px; height:2px; background:{ui.TRACK};'></div>"
            f"<div style='position:absolute; left:{lo:.1f}%; width:{hi - lo:.1f}%; top:9px; height:2px; background:#8C95A8;'></div>"
            f"<div style='position:absolute; left:{a:.1f}%; top:3px; transform:translateX(-50%); width:14px; height:14px; "
            f"border-radius:50%; background:{ui.CREAM}; border:2px solid {ui.MUTED}; box-sizing:border-box;'></div>"
            f"<div style='position:absolute; left:{b:.1f}%; top:3px; transform:translateX(-50%); width:14px; height:14px; "
            f"border-radius:50%; background:{ui.INK}; border:2px solid {ui.CREAM}; box-sizing:border-box;'></div></div>"
            f"<span style='text-align:right; font-family:{ui.MONO}; font-size:13px;'>{sign}{ui.rate(abs(r['diff']))}</span>"
            + ui.tip(f"<b>{escape(name)}</b><br>Runners on: {ui.rate(r['OPS on'])} OPS{' allowed' if pitching else ''} "
                     f"({int(r['PA on'])} PA)<br>Bases empty: {ui.rate(r['OPS empty'])} ({int(r['PA empty'])} PA)")
            + "</div>"
        )
    note = ("Right column: OPS allowed with runners on minus bases empty, so negative means he's tougher with "
            "runners on." if pitching else "Right column: OPS with runners on minus bases empty.")
    ui.html(fig_title(*title)
            + legend_row([swatch(ui.INK, "Runners on"), swatch(ui.CREAM, "Bases empty", ui.MUTED)])
            + f"<div style='display:flex; flex-direction:column; gap:4px;'>{''.join(rows)}</div>"
            + f"<p style='margin-top:10px; font-size:12px; color:{ui.MUTED};'>{note} Tap or hover a row for the numbers.</p>")


# ================================================================ PITCHING (new)
def k_minus_bb_chart():
    """Strikeout rate minus walk rate per pitcher, as bars left/right of the league average."""
    p = pit_table[pit_table.index.isin(qualified_pitchers["name"])]
    if p.empty:
        ui.html(fig_title("K% minus BB%", "Strikeout rate minus walk rate") + empty_note())
        return
    kbb = (p["K"] - p["BB"]) / p["BF"]
    league_kbb = (pit_table["K"].sum() - pit_table["BB"].sum()) / max(pit_table["BF"].sum(), 1)
    reach = max((kbb - league_kbb).abs().max(), 0.01)
    rows = []
    for name, v in kbb.sort_values(ascending=False).items():
        d = (v - league_kbb) / reach * 50                  # % of the half-width
        left, width = (50, d) if d >= 0 else (50 + d, -d)
        color = GOOD if d >= 0 else ui.LOSS
        bf = int(p.loc[name, "BF"])
        small = ui.small_sample(f"Only {bf} batters faced") if bf < SMALL_BF else ""
        rows.append(
            f"<div {ui.TAP} style='display:grid; grid-template-columns:minmax(0,150px) minmax(0,1fr) 60px; "
            "align-items:center; gap:12px; min-height:30px;'>"
            f"<span style='font-size:14px; white-space:nowrap;'>{escape(name)}{small}</span>"
            "<div style='position:relative; height:16px;'>"
            f"<div style='position:absolute; left:50%; top:-4px; width:1px; height:24px; background:#A49C8C;'></div>"
            f"<div style='position:absolute; left:{left:.1f}%; width:{max(width, 0.6):.1f}%; top:2px; height:12px; "
            f"background:{color};'></div></div>"
            f"<span style='text-align:right; font-family:{ui.MONO}; font-size:13px;'>{v * 100:.1f}%</span>"
            + ui.tip(f"<b>{escape(name)}: {v * 100:.1f}%</b><br>{int(p.loc[name, 'K'])} K, {int(p.loc[name, 'BB'])} BB "
                     f"in {bf} batters faced")
            + "</div>")
    ui.html(fig_title("K% minus BB%", f"Strikeout rate minus walk rate · center line = league ({league_kbb * 100:.1f}%) · 1+ IP")
            + legend_row([swatch(GOOD, "Better than the league"), swatch(ui.LOSS, "Worse than the league")])
            + f"<div style='display:flex; flex-direction:column; gap:4px;'>{''.join(rows)}</div>"
            + f"<p style='margin-top:10px; font-size:12px; color:{ui.MUTED};'>A quick read on pitching skill: more "
              "strikeouts and fewer walks, with no help needed from the fielders.</p>")


def efficiency_chart():
    data = qualified_pitchers[qualified_pitchers["P"] > 0].copy()
    data["P/BF"] = data["P"] / data["BF"]
    quadrant_chart(
        "Efficiency", "Strike % vs pitches per batter · dot size = innings pitched · 1+ IP", data, "P/BF", "STR%", "IP",
        "Pitches per batter faced", "Strike %",
        {"tl": ("Few pitches, many strikes", "best"), "tr": ("Many pitches, many strikes", "mixB"),
         "bl": ("Few pitches, few strikes", "mixA"), "br": ("Many pitches, few strikes", "worst")},
        ".1f", ".0%",
    )
    ui.html(f"<p style='margin-top:4px; font-size:12px; color:{ui.MUTED};'>Older games saved only the count when "
            "the at-bat ended, so their pitch totals run slightly low (two-strike fouls and the pitch put in play "
            "weren't saved). Live games count every pitch.</p>")


def trouble_innings_chart():
    rate, ip = stats.inning_runs(lgs)
    rate = rate[rate.index.isin(qualified_pitchers["name"])]
    ip = ip.reindex(rate.index)
    if rate.empty:
        ui.html(fig_title("Trouble innings", "Runs allowed per inning, by inning of the game") + empty_note())
        return
    innings = [c for c in sorted(rate.columns) if ip[c].fillna(0).sum() > 0][:9]
    lg_rate, total_ip = stats.inning_runs(lgs)
    league_rate = float((lg_rate * total_ip).sum().sum() / max(total_ip.sum().sum(), 1e-9))
    reach = max(league_rate, 0.5)
    label = {str(i): stats_ordinal(i) for i in innings}

    def cell(pitcher, col):
        i = int(col)
        n = ip.at[pitcher, i] if i in ip.columns else float("nan")
        if pd.isna(n) or n <= 0:
            return None
        v = rate.at[pitcher, i]
        fill, color = diverging(max(-1, min(1, (league_rate - v) / reach)))
        if n < 1:                                     # under one inning: washed out toward neutral
            fill, color = mix(fill, NEUTRAL, 0.55), ui.INK
        return (f"{v:.2f}", f"{stats.ip_text(round(n * 3))} IP", fill, color,
                f"<b>{escape(pitcher)} · {label[col]} inning</b><br>{v:.2f} runs per inning over "
                f"{stats.ip_text(round(n * 3))} IP", False)

    ui.html(fig_title("Trouble innings", f"Runs allowed per inning, by inning of the game · league {league_rate:.2f} · 1+ IP")
            + legend_row([swatch(GOOD, "Fewer runs than the league"), swatch(NEUTRAL, "About average", "#CFC8BA"),
                          swatch(ui.LOSS, "More runs than the league"), swatch(mix(GOOD, NEUTRAL, 0.55), "Faded: under 1 IP")])
            + grid_table(list(rate.index), [str(i) for i in innings], cell, "Pitcher", col_labels=label)
            + f"<p style='margin-top:4px; font-size:12px; color:{ui.MUTED};'>Live games count every run charged to "
              "the pitcher; older games count RBIs allowed, the same stand-in ERA uses.</p>")


def stats_ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ================================================================ HEAD TO HEAD
def grid_table(rows, cols, cell, corner="", col_labels=None):
    """HTML grid: cell(row, col) -> (text, subtext, fill, text_color, tooltip) or None for an empty cell."""
    # Column names stay on one line (a long name is cut with "…" on a phone; the full name is in the row labels)
    th = (f"padding:6px 1px; font-size:11.5px; font-weight:600; color:{ui.MUTED}; text-align:center; "
          "white-space:nowrap; overflow:hidden; text-overflow:ellipsis;")
    head = f"<th style='{th} text-align:left;'>{corner}</th>" + "".join(
        f"<th style='{th}' title='{escape((col_labels or {}).get(c, c))}'>{escape((col_labels or {}).get(c, c))}</th>" for c in cols)
    body = []
    for r in rows:
        cells = []
        for c in cols:
            v = cell(r, c)
            if v is None:
                cells.append(f"<td style='padding:2px;'><div style='height:50px; background:{ui.PANEL};'></div></td>")
                continue
            text, sub, fill, color, tip, outline = v
            # Pick the tooltip's side for a phone-width grid (64px names + equal columns across ~360px)
            ci = cols.index(c)
            colw = 296 / len(cols)
            center = 64 + (ci + 0.5) * colw
            align = "wf-l" if center < 120 else "wf-r" if center > 240 else ""
            cells.append(f"<td style='padding:2px;'><div {ui.TAP} style='height:46px; background:{fill}; "
                         f"{'box-shadow:inset 0 0 0 2px ' + ui.INK + ';' if outline else ''}"
                         f"display:flex; flex-direction:column; align-items:center; justify-content:center; min-width:0; "
                         f"padding:0 1px; color:{color};'>"
                         # nowrap + tight spacing so "1.000" and "12 G" fit a phone-width column
                         f"<span style='font-family:{ui.MONO}; font-size:12px; font-weight:600; letter-spacing:-0.4px; "
                         f"white-space:nowrap;'>{text}</span>"
                         f"<span style='font-size:10px; opacity:0.85; white-space:nowrap;'>{sub}</span>{ui.tip(tip, align)}</div></td>")
        body.append(f"<tr><th style='padding:2px 6px 2px 0; text-align:left; font-size:13px; font-weight:500; "
                    f"white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>{escape(r)}</th>{''.join(cells)}</tr>")
    return ("<div><table style='border-collapse:separate; border-spacing:0; "
            "width:100%; table-layout:fixed;'>"
            f"<colgroup><col style='width:64px'>{'<col>' * len(cols)}</colgroup>"
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
            f"<p style='margin-top:8px; font-size:12px; color:{ui.MUTED};'>Tap or hover a cell for the details.</p>")


def matchup_heatmap():
    stat = st.segmented_control("Stat", ["OBP", "OPS"], default="OBP", key="mu_stat",
                                label_visibility="collapsed") or "OBP"
    values, counts = stats.matchup_grid(lgs.pa, stat)
    if values.empty:
        ui.html(empty_note())
        return
    lg_val = bat_table[stat].mean() if stat == "OPS" else (
        (bat_table["H"].sum() + bat_table["BB"].sum()) /
        max(bat_table["AB"].sum() + bat_table["BB"].sum() + bat_table["SF"].sum(), 1))
    reach = 0.30 if stat == "OBP" else 0.60          # this far from the league number = full color
    batters = sorted(values.index)
    pitchers_ = sorted(values.columns)

    def cell(b, p):
        if b == p or p not in counts.columns or b not in counts.index or pd.isna(counts.at[b, p]):
            return None   # never faced each other (or himself)
        n = int(counts.at[b, p])
        v = values.at[b, p]
        score = 0 if pd.isna(v) else (v - lg_val) / reach
        fill, color = diverging(max(-1, min(1, score)))
        if n < 5:                                   # few PA: washed out toward neutral
            fill, color = mix(fill, NEUTRAL, 0.55), ui.INK
        return (ui.rate(v), f"{n} PA", fill, color,
                f"<b>{escape(b)} vs {escape(p)}</b><br>{ui.rate(v)} {stat} in {n} PA", False)

    ui.html(fig_title(f"Every batter vs every pitcher · {stat}", "Rows are batters, columns are pitchers")
            + legend_row([swatch(ui.LOSS, "Pitcher ahead"), swatch(NEUTRAL, f"About league average ({ui.rate(lg_val)})", "#CFC8BA"),
                          swatch(GOOD, "Batter ahead"), swatch(mix(GOOD, NEUTRAL, 0.55), "Faded: under 5 PA")])
            + grid_table(batters, pitchers_, cell, "Batter"))


def chemistry_heatmap():
    done = lgs.completed
    pairs = stats.teammate_records(done)
    own = stats.records(done)
    if pairs.empty:
        ui.html(empty_note())
        return
    names = sorted(set(pairs["a"]) | set(pairs["b"]))
    lookup = {}
    for r in pairs.itertuples(index=False):
        lookup[(r.a, r.b)] = lookup[(r.b, r.a)] = r

    def cell(a, b):
        if a == b:
            if a not in own.index or not own.loc[a, "GP"]:
                return None
            o = own.loc[a]
            fill, color = diverging((o["Pct"] - 0.5) / 0.5)
            return (ui.rate(o["Pct"]), f"{int(o['GP'])} G", fill, color,   # outlined = his own record (see the legend)
                    f"<b>{escape(a)} overall</b><br>{int(o['W'])}-{int(o['D'])}-{int(o['L'])} in {int(o['GP'])} games", True)
        r = lookup.get((a, b))
        if r is None:
            return None
        fill, color = diverging((r.Pct - 0.5) / 0.5)
        if r.GP < 3:
            fill, color = mix(fill, NEUTRAL, 0.55), ui.INK
        return (ui.rate(r.Pct), f"{int(r.GP)} G", fill, color,
                f"<b>{escape(a)} and {escape(b)} together</b><br>{int(r.W)}-{int(r.D)}-{int(r.L)} "
                f"({ui.rate(r.Pct)}) in {int(r.GP)} games", False)

    ui.html(fig_title("Teammate chemistry", "Win % when two players are on the same team · a draw is half a win")
            + legend_row([swatch(ui.LOSS, "Lose together"), swatch(NEUTRAL, ".500", "#CFC8BA"),
                          swatch(GOOD, "Win together"), swatch(mix(GOOD, NEUTRAL, 0.55), "Faded: under 3 games"),
                          swatch(ui.CREAM, "Outlined: the player's own win %", ui.INK)])
            + grid_table(names, names, cell))


# ================================================================ TABS
tab_value, tab_hit, tab_pitch, tab_h2h, tab_two = st.tabs(["Value", "Hitting", "Pitching", "Head to head", "Two-way"])

with tab_value:
    section_heading("Percentile rankings", top=16)
    war_now = stats.war(lg, season=year)
    choices = war_now[war_now["G"] > 0].sort_values("WAR", ascending=False).index.tolist() or lgs.names
    who = st.selectbox("Player", choices, key="pct_player")
    percentile_sliders(who)
    section_heading("WAR race")
    war_race_chart()

with tab_hit:
    section_heading("Hitting", top=16)
    left, right = st.columns(2, gap="large")
    with left:
        leader_bars("RBI leaders", "Runs batted in, most to fewest", hitters, "RBI", 0)
    with right:
        quadrant_chart(
            "Strikeouts vs walks", "Dot size = at-bats", hitters, "BB", "K", "AB",
            "Walks (BB)", "Strikeouts (K)",
            {"tl": ("High K, low BB", "worst"), "tr": ("High K, high BB", "mixB"),
             "bl": ("Low K, low BB", "mixA"), "br": ("Low K, high BB", "best")},
            ".0f", ".0f",
        )
    left, right = st.columns(2, gap="large")
    with left:
        ui.html("<div style='height:28px;'></div>")
        quadrant_chart(
            "OBP vs SLG", "Dot size = home runs", hitters, "OBP", "SLG", "HR",
            "OBP (on-base percentage)", "SLG (slugging percentage)",
            {"tl": ("High SLG, low OBP", "mixB"), "tr": ("High SLG, high OBP", "best"),
             "bl": ("Low SLG, low OBP", "worst"), "br": ("Low SLG, high OBP", "mixA")},
            ".3f", ".3f",
        )
    with right:
        ui.html("<div style='height:28px;'></div>")
        runner_split_chart()
    section_heading("Outcome mix")
    outcome_mix_chart()

with tab_pitch:
    section_heading("Pitching", top=16)
    left, right = st.columns(2, gap="large")
    with left:
        leader_bars("ERA leaders", "Earned run average, lowest first · 1+ IP", qualified_pitchers, "ERA", 2, low_is_best=True)
    with right:
        quadrant_chart(
            "WHIP vs K/9", "Dot size = innings pitched · 1+ IP", qualified_pitchers, "WHIP", "K/9", "IP",
            "WHIP (walks + hits per inning)", "K/9 (strikeouts per 9 IP)",
            {"tl": ("High K/9, low WHIP", "best"), "tr": ("High K/9, high WHIP", "mixB"),
             "bl": ("Low K/9, low WHIP", "mixA"), "br": ("Low K/9, high WHIP", "worst")},
            ".2f", ".1f",
        )
    left, right = st.columns(2, gap="large")
    with left:
        ui.html("<div style='height:28px;'></div>")
        k_minus_bb_chart()
    with right:
        ui.html("<div style='height:28px;'></div>")
        efficiency_chart()
    left, right = st.columns(2, gap="large")
    with left:
        ui.html("<div style='height:28px;'></div>")
        runner_split_chart(by="pitcher")
    with right:
        ui.html("<div style='height:28px;'></div>")
        trouble_innings_chart()
    section_heading("Results allowed")
    outcome_mix_chart(by="pitcher")

with tab_h2h:
    section_heading("Matchups", top=16)
    matchup_heatmap()
    section_heading("Teammates")
    chemistry_heatmap()

with tab_two:
    section_heading("Two-way", top=16)
    hitters["OPS"] = hitters["OBP"] + hitters["SLG"]
    combined = pd.merge(hitters[["name", "OPS"]], qualified_pitchers[["name", "ERA", "IP"]], on="name")
    left, _ = st.columns(2, gap="large")
    with left:
        quadrant_chart(
            "OPS vs ERA", "Dot size = innings pitched", combined, "OPS", "ERA", "IP",
            "OPS (OBP + SLG)", "ERA (earned run average)",
            {"tl": ("Low OPS, high ERA", "worst"), "tr": ("High OPS, high ERA", "mixB"),
             "bl": ("Low OPS, low ERA", "mixA"), "br": ("High OPS, low ERA", "best")},
            ".3f", ".2f",
        )



