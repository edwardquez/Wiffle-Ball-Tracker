"""Awards & Records: season awards, single-game records, hitting streaks and career milestones."""
import streamlit as st
from html import escape
from urllib.parse import quote

import styles as ui
import stats
from db import league

st.set_page_config(page_title="Awards & Records", layout="wide")
ui.apply()
lg = league()
seasons = stats.seasons(lg)

st.markdown(f"""<style>
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap:26px; }}
[data-testid="stTabs"] button[role="tab"] {{ padding:10px 2px; }}
[data-testid="stTabs"] button[role="tab"] p {{ font-size:15px; color:{ui.MUTED}; }}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p {{ color:{ui.INK}; font-weight:600; }}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color:{ui.INK} !important; height:2px; }}
[data-testid="stTabs"] [data-baseweb="tab-border"] {{ background-color:{ui.RULE}; }}
.aw-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(250px, 1fr)); gap:26px 22px; }}
</style>""", unsafe_allow_html=True)

st.title("Awards & Records", anchor=False)
if not seasons:
    st.info("No games yet. Awards and records appear once games are played.")
    st.stop()

completed = lg.completed.set_index("game_id")


def when(game_id):
    """'Jun 27, 2025 · Match 3' for a game."""
    if game_id in completed.index:
        g = completed.loc[game_id]
        return f"{ui.date_text(g['date'])} · Match {int(g['match_no'])}"
    return ""


def head(text, top=26):
    return (f"<div style='margin:{top}px 0 4px; padding-bottom:8px; border-bottom:2px solid {ui.INK}; font-size:12px; "
            f"font-weight:600; letter-spacing:1.6px; text-transform:uppercase;'>{text}</div>")


def plural(n, word):
    n = int(n)
    return f"{n} {word if n == 1 else word + 's'}" if not word.isupper() else f"{n} {word}"


tab_awards, tab_records = st.tabs(["Awards", "Records"])

# ================================================================ AWARDS
AWARDS = [  # key, title, what it's for, value format, glossary term
    ("MVP", "Most Valuable Player", "Highest WAR", lambda v: f"{v:+.1f}", "war"),
    ("Pitcher", "Pitcher of the Year", "Most pitching runs saved", lambda v: f"{v:+.1f}", "pitchruns"),
    ("Hitter", "Hitter of the Year", f"Best wRC+ · {stats.AWARD_MIN_PA}+ PA", lambda v: f"{v:.0f}", "wrc"),
    ("Glove", "Gold Glove", "Most fielding runs (live games)", lambda v: f"{v:+.1f}", "fieldruns"),
    ("Improved", "Most Improved", "Biggest WAR jump", lambda v: f"{v:+.1f}", "war"),
]


def award_card(title, why, ranked, fmt, term, empty=""):
    if not ranked:
        body = (f"<div style='margin:14px 0 6px; font-family:{ui.SERIF}; font-size:24px; color:{ui.MUTED};'>To be decided</div>"
                f"<div style='font-size:13px; color:{ui.MUTED};'>{empty}</div>")
    else:
        (name, value), rest = ranked[0], ranked[1:]
        body = (f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin:12px 0 10px;'>"
                f"<a href='./Player_Dashboard?player={quote(name)}' target='_self' style='font-family:{ui.SERIF}; font-size:30px; "
                f"font-weight:500; text-decoration:none;'>{escape(name)}</a>"
                f"<span style='font-family:{ui.MONO}; font-size:20px; font-weight:600;'>{fmt(value)}</span></div>"
                + "".join(f"<div style='display:flex; justify-content:space-between; padding:6px 0; font-size:14px; "
                          f"border-top:1px solid {ui.RULE};'><span>{i + 2}. {escape(n)}</span>"
                          f"<span style='font-family:{ui.MONO}; color:{ui.MUTED};'>{fmt(v)}</span></div>"
                          for i, (n, v) in enumerate(rest)))
    return (f"<div style='border-top:2px solid {ui.INK}; padding-top:14px;'>"
            f"<div style='display:flex; justify-content:space-between; align-items:baseline; gap:8px;'>"
            f"<span style='font-size:12px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:{ui.GOLD};'>{title}</span>"
            f"{ui.glossary_link(term)}</div>"
            f"<div style='font-size:13px; color:{ui.MUTED}; margin-top:2px;'>{why}</div>{body}</div>")


with tab_awards:
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    year = int(c2.selectbox("Season", [str(y) for y in seasons], key="aw_season"))
    aw = stats.season_awards(lg, year)
    n_games = len(stats.season_league(lg, year).completed)
    c1.markdown(f"<p style='margin:0; font-size:14px; color:{ui.MUTED};'>{year} season · {plural(n_games, 'game')} · "
                f"{'final' if year != seasons[0] else 'standings so far, updated as games are played'}</p>",
                unsafe_allow_html=True)
    cards = []
    for key, title, why, fmt, term in AWARDS:
        if key == "Improved":
            if "Improved" not in aw:
                continue          # first season: nothing to compare with
            why = f"Biggest WAR jump from {aw['_improved_from']}"
        empty = "Needs live-scored games with throw-outs and errors." if key == "Glove" else \
                f"No one has {stats.AWARD_MIN_PA}+ plate appearances yet." if key == "Hitter" else "Not enough games yet."
        cards.append(award_card(title, why, aw.get(key, []), fmt, term, empty))
    ui.html(f"<div class='aw-grid' style='margin-top:18px;'>{''.join(cards)}</div>")

# ================================================================ RECORDS
with tab_records:
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    scope = c2.selectbox("Records from", ["All-time"] + [str(y) for y in seasons], key="rec_scope")
    lr = lg if scope == "All-time" else stats.season_league(lg, int(scope))
    c1.markdown(f"<p style='margin:0; font-size:14px; color:{ui.MUTED};'>"
                f"{'Every game ever recorded' if scope == 'All-time' else scope + ' season only'}</p>", unsafe_allow_html=True)

    # Single game
    rows = []
    for label, col, holders in stats.single_game_records(lr):
        value = stats.ip_text(holders[0][2]) if col == "OUTS" else f"{holders[0][2]:.0f}"
        names = "".join(f"<div><b>{escape(p)}</b> <span style='font-size:12px; color:{ui.MUTED};'>{when(g)}</span></div>"
                        for p, g, _ in holders[:3])
        more = f"<div style='font-size:12px; color:{ui.MUTED};'>+{len(holders) - 3} more tied</div>" if len(holders) > 3 else ""
        rows.append(f"<div style='display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1.4fr) 56px; gap:10px; "
                    f"align-items:baseline; padding:11px 0; border-bottom:1px solid {ui.RULE};'>"
                    f"<span style='font-size:15px;'>{label}</span><span style='font-size:15px; line-height:1.5;'>{names}{more}</span>"
                    f"<span style='text-align:right; font-family:{ui.MONO}; font-size:18px; font-weight:600;'>{value}</span></div>")
    single = head("Single game", top=18) + ("".join(rows) or f"<p style='color:{ui.MUTED};'>No games yet.</p>")

    # Streaks
    streak_rows = []
    for longest, name, current in [s for s in stats.hitting_streaks(lr) if s[0] > 0][:5]:
        active = f" · <span style='color:{ui.WIN}; font-weight:600;'>active</span>" if current and current == longest else \
                 f" · <span style='color:{ui.MUTED};'>current {current}</span>" if current else ""
        streak_rows.append(f"<div style='display:flex; justify-content:space-between; gap:10px; padding:10px 0; "
                           f"border-bottom:1px solid {ui.RULE}; font-size:15px;'><span><b>{escape(name)}</b>{active}</span>"
                           f"<span style='font-family:{ui.MONO};'>{plural(longest, 'game')}</span></div>")
    streaks = (head("Longest hitting streaks", top=18)
               + f"<div style='font-size:13px; color:{ui.MUTED}; margin:6px 0 2px;'>Games in a row with a hit (games he "
                 "sat out don't break it)</div>" + ("".join(streak_rows) or f"<p style='color:{ui.MUTED};'>No hits yet.</p>"))

    # Milestones (always career)
    STAT_WORD = {"HR": "home run", "H": "hit", "RBI": "RBI", "WAR": "WAR"}
    mrows = []
    for name, stat, cur, goal in stats.milestones(lg):
        left = goal - cur
        gap = f"{left:.1f} WAR" if stat == "WAR" else plural(left, STAT_WORD[stat])
        now = f"{cur:+.1f}" if stat == "WAR" else f"{cur:.0f}"
        mrows.append(f"<div style='padding:10px 0; border-bottom:1px solid {ui.RULE};'>"
                     f"<div style='display:flex; justify-content:space-between; gap:10px; font-size:15px;'>"
                     f"<span><b>{escape(name)}</b> · {gap} from {goal}{' career WAR' if stat == 'WAR' else ''}</span>"
                     f"<span style='font-family:{ui.MONO}; color:{ui.MUTED};'>{now}</span></div>"
                     f"<div style='height:4px; background:{ui.TRACK}; margin-top:8px;'>"
                     f"<div style='height:4px; width:{min(cur / goal, 1) * 100:.0f}%; background:{ui.INK};'></div></div></div>")
    miles = (head("Closest to a milestone · career", top=34) + ("".join(mrows) or f"<p style='color:{ui.MUTED};'>Nothing close yet.</p>"))

    left, right = st.columns(2, gap="large")
    with left:
        ui.html(single)
    with right:
        ui.html(streaks + miles)