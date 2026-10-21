"""Glossary: every stat and term on the site, with its formula and a worked example from the league's
current numbers (the examples update as games are played).

Other pages link here with ?term=<key> (the "What's this?" links), which opens the page on that entry.
"""
import re

import streamlit as st
import pandas as pd

from html import escape

import styles as ui
import stats
from db import league

st.set_page_config(page_title="Glossary", layout="wide")
ui.apply()

lg = league()

# Phones: smaller type, formula behind a tap. Desktop: formula beside the example.
st.markdown(f"""<style>
.gl-how-phone {{ display:none; }}
.gl-key {{ display:block; margin-top:6px; font-family:{ui.SANS}; font-size:12px; line-height:1.5; color:{ui.MUTED}; }}
.gl-key a, .gl-means a {{ color:{ui.INK}; }}
.gl-jump {{ display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 4px; }}
.gl-jump a {{ font-size:13px; padding:6px 10px; border:1px solid {ui.RULE}; color:{ui.INK}; text-decoration:none; }}
.gl-jump a:hover {{ border-color:{ui.INK}; }}
@media (max-width: 640px) {{
  .gl-entry {{ padding:20px 0 18px !important; }}
  .gl-name {{ font-size:22px !important; }}
  .gl-full {{ font-size:13px !important; }}
  .gl-means {{ font-size:15px !important; line-height:1.55 !important; margin:6px 0 12px !important; }}
  .gl-how-desk {{ display:none !important; }}
  .gl-grid {{ display:block !important; }}
  .gl-ex {{ padding:10px 12px !important; }}
  .gl-ex-text {{ font-size:14px !important; line-height:1.55 !important; }}
  .gl-how-phone {{ display:block; margin-top:10px; }}
  .gl-how-phone summary {{ font-size:13px; color:{ui.MUTED}; cursor:pointer; list-style:none; }}
  .gl-how-phone summary::-webkit-details-marker {{ display:none; }}
  .gl-how-phone summary::before {{ content:"+ "; font-weight:600; }}
  .gl-how-phone[open] summary::before {{ content:"− "; }}
  .gl-how-phone .gl-f {{ margin-top:8px; font-family:{ui.MONO}; font-size:12.5px; line-height:1.7; color:{ui.INK}; }}
  .gl-codes td, .gl-codes th {{ padding-left:4px !important; padding-right:4px !important; font-size:13px !important; }}
}}
</style>""", unsafe_allow_html=True)

# ---------------- Header, season, search ---------------- #
title_col, season_col = st.columns([3, 1], vertical_alignment="bottom")
title_col.title("Glossary", anchor=False)
season_pick = season_col.selectbox("Examples from", ["Career"] + [str(y) for y in stats.seasons(lg)], key="gl_season")
year = None if season_pick == "Career" else int(season_pick)
lgs = lg if year is None else stats.season_league(lg, year)

ui.html(f"<p style='margin:-4px 0 16px; font-size:16px; line-height:1.6; color:{ui.BODY}; max-width:720px;'>"
        "Every stat on the site: what it means, how it's calculated, and a worked example using the league's "
        "current numbers. The examples update as games are played.</p>")

term = st.query_params.get("term")
q = st.text_input("Search", placeholder="Search a stat, like ERA or wOBA", key="gl_search",
                  label_visibility="collapsed").strip().lower()

# ---------------- League tables for the examples ---------------- #
bat = lgs.advanced_batting()
pit = lgs.advanced_pitching()
war = stats.war(lg, season=year)
war = war[war["G"] > 0]
fld = stats.fielding(lgs.fielding)
rpw = stats.runs_per_win(lgs)
SCOPE = "career" if year is None else str(year)


def link(key, text):
    """Link to another entry on this page."""
    return f"<a href='./Glossary?term={key}' target='_self'>{text}</a>"


def leader(table, col, low=False, need=None, at_least=0):
    """(name, row) of the best player at `col`, among players with `need` >= at_least."""
    t = table.dropna(subset=[col]) if col in table else table.iloc[0:0]
    if need:
        t = t[t[need] >= at_least]
    if t.empty:
        return None, None
    name = t[col].idxmin() if low else t[col].idxmax()
    return name, t.loc[name]


def b(text):
    return f"<b>{escape(str(text))}</b>"


def safe_div(a, c):
    return a / c if c else float("nan")


def r2(v):
    return "—" if pd.isna(v) else f"{v:.2f}"


def pct(v):
    return "—" if pd.isna(v) else f"{v * 100:.1f}%"


def d1(v):
    return "—" if pd.isna(v) else f"{v:.1f}"


def d0(v):
    return "—" if pd.isna(v) else f"{v:.0f}"


def sign(v, d=1):
    return "—" if pd.isna(v) else f"{v:+.{d}f}"


# League totals used in footers
T = {c: float(bat[c].sum()) for c in ("PA", "AB", "H", "BB", "K", "SF", "HR", "TB", "1B", "2B", "3B")} if not bat.empty else {}
IP = float(pit["IP"].sum()) if not pit.empty else 0.0
LG_ERA = safe_div(float(pit["ER"].sum()) * 9, IP) if IP else float("nan")


def lg_rate(num, den):
    return safe_div(T.get(num, 0), T.get(den, 0)) if T else float("nan")


# ---------------- Entries ---------------- #
# Each entry: section, key, name, full name, extra search words, meaning, formula (HTML or None),
# formula key (HTML or ""), example (function -> HTML, or None to fall back), fallback example, footer.
E = []


def add(section, key, name, full, means, formula=None, fkey="", example=None, fallback="", footer=None, words=""):
    E.append(dict(section=section, key=key, name=name, full=full, means=means, formula=formula, fkey=fkey,
                  example=example, fallback=fallback, footer=footer, words=words))


# ---- Hitting
add("Hitting", "pa", "PA", "Plate appearances",
    "Every time a player comes up to bat, whatever happens: hit, out, walk, sac fly or reaching on an error.",
    "PA = every completed turn at bat", "",
    lambda: (lambda n, r: f"{b(n)} leads the league with {b(int(r.PA))} plate appearances ({SCOPE})." if n else None)(*leader(bat, "PA")),
    "Batting 4 times in a game = 4 PA.", lambda: f"League total: {int(T.get('PA', 0))} PA")
add("Hitting", "ab", "AB", "At-bats",
    "Plate appearances that count toward batting average. Walks and sac flies don't count, so they never hurt AVG. "
    "Fielder's choices and reaching on an error do count as at-bats.",
    "AB = PA − BB − SF", "BB walks · SF sac flies",
    lambda: (lambda n, r: f"{b(n)}: {int(r.PA)} PA − {int(r.BB)} BB − {int(r.SF)} SF = {b(int(r.AB))} at-bats." if n else None)(*leader(bat, "AB")),
    "5 PA with 1 walk = 4 AB.", lambda: f"League total: {int(T.get('AB', 0))} AB")
add("Hitting", "avg", "AVG", "Batting average",
    "How often a hitter gets a hit in an official at-bat.",
    "AVG = H ÷ AB", f"H hits · {link('ab', 'AB at-bats')}",
    lambda: (lambda n, r: f"{b(n)} has {b(int(r.H))} hits in {b(int(r.AB))} at-bats: {int(r.H)} ÷ {int(r.AB)} = {b(ui.rate(r.AVG))}, "
             "the best in the league (5+ at-bats)." if n else None)(*leader(bat, "AVG", need="AB", at_least=5)),
    "3 hits in 10 at-bats = .300.", lambda: f"League average: {ui.rate(lg_rate('H', 'AB'))} · 5+ at-bats to lead the Home page", words="batting average")
add("Hitting", "obp", "OBP", "On-base percentage",
    "How often a hitter reaches base by a hit or a walk. Getting on base is the first step to scoring.",
    "OBP = (H + BB) ÷ (AB + BB + SF)", f"{link('ab', 'AB')} at-bats · BB walks · SF sac flies",
    lambda: (lambda n, r: f"{b(n)}: ({int(r.H)} H + {int(r.BB)} BB) ÷ ({int(r.AB)} AB + {int(r.BB)} BB + {int(r.SF)} SF) "
             f"= {b(ui.rate(r.OBP))}, the league's best (15+ PA)." if n else None)(*leader(bat, "OBP", need="PA", at_least=15)),
    "3 hits and 2 walks in 10 PA = .500.",
    lambda: f"League OBP: {ui.rate(safe_div(T.get('H', 0) + T.get('BB', 0), T.get('AB', 0) + T.get('BB', 0) + T.get('SF', 0)))}")
add("Hitting", "slg", "SLG", "Slugging percentage",
    "Total bases per at-bat. Like AVG, but a double counts twice as much as a single and a home run four times.",
    "SLG = TB ÷ AB<br>TB = 1B + 2 × 2B + 3 × 3B + 4 × HR", f"TB total bases · {link('ab', 'AB at-bats')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r['1B'])} singles + 2 × {int(r['2B'])} doubles + 3 × {int(r['3B'])} triples + "
             f"4 × {int(r.HR)} HR = {int(r.TB)} total bases in {int(r.AB)} at-bats = {b(ui.rate(r.SLG))}." if n else None)(*leader(bat, "SLG", need="PA", at_least=15)),
    "A single and a home run in 4 at-bats: 5 TB ÷ 4 = 1.250.", lambda: f"League SLG: {ui.rate(lg_rate('TB', 'AB'))}", words="slugging power")
add("Hitting", "ops", "OPS", "On-base plus slugging",
    "One quick number for overall hitting: getting on base plus hitting for power.",
    "OPS = OBP + SLG", f"{link('obp', 'OBP')} · {link('slg', 'SLG')}",
    lambda: (lambda n, r: f"{b(n)}: {ui.rate(r.OBP)} OBP + {ui.rate(r.SLG)} SLG = {b(ui.rate(r.OPS))}, the league's best (15+ PA)." if n else None)(*leader(bat, "OPS", need="PA", at_least=15)),
    ".400 OBP + .500 SLG = .900 OPS.", None)
add("Hitting", "bbpct", "BB%", "Walk rate",
    "Share of plate appearances that end in a walk. Shows patience and a good eye.",
    "BB% = BB ÷ PA", f"BB walks · {link('pa', 'PA')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r.BB)} walks in {int(r.PA)} PA = {b(pct(r['BB%']))}." if n else None)(*leader(bat, "BB%", need="PA", at_least=15)),
    "2 walks in 20 PA = 10.0%.", lambda: f"League walk rate: {pct(lg_rate('BB', 'PA'))}", words="walk rate")
add("Hitting", "kpct", "K%", "Strikeout rate",
    "Share of plate appearances that end in a strikeout. For hitters lower is better; for pitchers higher is better "
    "(a pitcher's K% uses batters faced).",
    "K% = K ÷ PA (hitters) · K ÷ BF (pitchers)", f"K strikeouts · {link('pa', 'PA')} · {link('bf', 'BF batters faced')}",
    lambda: (lambda n, r: f"{b(n)} strikes out the least: {int(r.K)} K in {int(r.PA)} PA = {b(pct(r['K%']))} (15+ PA)." if n else None)(*leader(bat, "K%", low=True, need="PA", at_least=15)),
    "3 strikeouts in 20 PA = 15.0%.", lambda: f"League strikeout rate: {pct(lg_rate('K', 'PA'))}", words="strikeout rate")
add("Hitting", "rbi", "RBI", "Runs batted in",
    "Runs that score because of the batter's plate appearance. No RBI on an error, a double play or a triple play.",
    "RBI = runs scored on the play (live games), or as entered (older games)", "",
    lambda: (lambda n, r: f"{b(n)} leads the league with {b(int(r.RBI))} RBI ({SCOPE})." if n else None)(*leader(bat, "RBI")),
    "A double with two runners on who both score = 2 RBI.", None, words="runs batted in")
add("Hitting", "r", "R", "Runs scored",
    "Times a player crossed home plate. Only live-scored games record who scored, so older games leave it blank.",
    "R = times scored (live games only)", f"{link('live', 'Live-scored games')}",
    lambda: (lambda n, r: f"{b(n)} has scored {b(int(r.R))} runs in live-scored games." if n and r.R > 0 else None)(*leader(bat, "R")),
    "Single, steal, then home on a hit = 1 run scored.", None, words="runs scored")

# ---- Pitching
add("Pitching", "ip", "IP", "Innings pitched",
    "Outs recorded while pitching, in innings. Shown baseball style: 4.2 means 4 innings and 2 outs (4⅔). "
    "Caught-stealing and pickoff outs count too.",
    "IP = outs ÷ 3", "",
    lambda: (lambda n, r: f"{b(n)} has recorded {int(r.OUTS)} outs = {b(stats.ip_text(r.OUTS))} innings ({SCOPE})." if n else None)(*leader(pit, "OUTS")),
    "14 outs = 4.2 innings.", lambda: f"League total: {stats.ip_text(round(IP * 3))} IP", words="innings pitched")
add("Pitching", "bf", "BF", "Batters faced",
    "Plate appearances against a pitcher. The pitching version of PA.",
    "BF = plate appearances against", f"{link('pa', 'PA')}",
    lambda: (lambda n, r: f"{b(n)} has faced {b(int(r.BF))} batters, the most in the league." if n else None)(*leader(pit, "BF")),
    "", None, words="batters faced")
add("Pitching", "era", "ERA", "Earned run average",
    "Earned runs a pitcher allows per 9 innings. Lower is better. Live games count real earned runs (runs that "
    "scored because of an error don't count against him); older games use RBIs allowed, the only run data they saved.",
    "ERA = ER × 9 ÷ IP", f"ER earned runs · {link('ip', 'IP innings pitched')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r.ER)} earned runs × 9 ÷ {stats.ip_text(r.OUTS)} IP = {b(r2(r.ERA))}, "
             "the league's best (12+ batters faced)." if n else None)(*leader(pit, "ERA", low=True, need="BF", at_least=12)),
    "3 earned runs in 6 innings = 4.50.", lambda: f"League ERA: {r2(LG_ERA)}", words="earned run average")
add("Pitching", "whip", "WHIP", "Walks + hits per inning",
    "How many baserunners a pitcher allows per inning, from walks and hits. Lower is better.",
    "WHIP = (BB + H) ÷ IP", f"BB walks · H hits allowed · {link('ip', 'IP')}",
    lambda: (lambda n, r: f"{b(n)}: ({int(r.BB)} BB + {int(r.H)} H) ÷ {stats.ip_text(r.OUTS)} IP = {b(r2(r.WHIP))} (12+ batters faced)." if n else None)(*leader(pit, "WHIP", low=True, need="BF", at_least=12)),
    "2 walks and 4 hits in 4 innings = 1.50.", lambda: f"League WHIP: {r2(safe_div(float(pit['BB'].sum() + pit['H'].sum()), IP))}")
add("Pitching", "k9", "K/9", "Strikeouts per 9 innings",
    "Strikeouts per 9 innings pitched. Higher is better.",
    "K/9 = K × 9 ÷ IP", f"K strikeouts · {link('ip', 'IP')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r.K)} K × 9 ÷ {stats.ip_text(r.OUTS)} IP = {b(d1(r['K/9']))}." if n else None)(*leader(pit, "K/9", need="BF", at_least=12)),
    "4 strikeouts in 3 innings = 12.0.", None, words="strikeouts per 9")
add("Pitching", "bb9", "BB/9", "Walks per 9 innings",
    "Walks per 9 innings pitched. Lower is better.",
    "BB/9 = BB × 9 ÷ IP", f"BB walks · {link('ip', 'IP')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r.BB)} BB × 9 ÷ {stats.ip_text(r.OUTS)} IP = {b(d1(r['BB/9']))}, the fewest (12+ batters faced)." if n else None)(*leader(pit, "BB/9", low=True, need="BF", at_least=12)),
    "1 walk in 3 innings = 3.0.", None, words="walks per 9")
add("Pitching", "pitches", "P", "Pitches",
    "Pitches thrown. Live games count every pitch. Older games saved only the count when the at-bat ended, so "
    "two-strike fouls and the pitch put in play are missing and their totals run a little low.",
    "Live: every pitch · Older: strikes + balls as saved", "",
    lambda: (lambda n, r: f"{b(n)} has thrown {b(int(r.P))} pitches ({SCOPE})." if n else None)(*leader(pit, "P")),
    "", None, words="pitch count")
add("Pitching", "strpct", "Strike %", "Strike percentage",
    "Share of pitches that are strikes. Fouls and balls put in play count as strikes.",
    "Strike % = strikes ÷ pitches", f"{link('pitches', 'Pitches')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r.STR)} strikes in {int(r.P)} pitches = {b(pct(r['STR%']))} (12+ batters faced)." if n else None)(*leader(pit, "STR%", need="BF", at_least=12)),
    "30 strikes in 50 pitches = 60.0%.", None, words="strike percentage")

# ---- Advanced
add("Advanced", "woba", "wOBA", "Weighted on-base average",
    "Like OBP, but each way of reaching base counts by how many runs it's worth: a home run is worth about three "
    "walks. On the OBP scale (.400 is excellent).",
    "wOBA = (0.69 BB + 0.89 1B + 1.27 2B + 1.62 3B + 2.10 HR) ÷ (AB + BB + SF)",
    f"The numbers are MLB run values · {link('ab', 'AB')} · BB walks · SF sac flies",
    lambda: (lambda n, r: f"{b(n)}: (0.69 × {int(r.BB)} + 0.89 × {int(r['1B'])} + 1.27 × {int(r['2B'])} + 1.62 × {int(r['3B'])} "
             f"+ 2.10 × {int(r.HR)}) ÷ ({int(r.AB)} + {int(r.BB)} + {int(r.SF)}) = {b(ui.rate(r.wOBA))}, the league's best (15+ PA)." if n else None)(*leader(bat, "wOBA", need="PA", at_least=15)),
    "", None, words="weighted on-base")
add("Advanced", "wrc", "wRC+", "Weighted runs created plus",
    "Overall hitting on a scale where 100 is the league average: 130 is 30% better than the league's typical hitter, 80 is 20% worse.",
    "wRC+ = 100 × ((wOBA − lg wOBA) ÷ 1.2 + lg R/PA) ÷ lg R/PA",
    f"{link('woba', 'wOBA')} · lg = league · R/PA = runs per plate appearance · 1.2 = wOBA scale",
    lambda: (lambda n, r: f"{b(n)} has a {ui.rate(r.wOBA)} wOBA in a league that scores about one run every "
             f"{1 / stats.league_runs_per_pa(lgs):.1f} plate appearances, which works out to {b(d0(r['wRC+']))}: "
             f"about {abs(r['wRC+'] - 100):.0f}% {'better' if r['wRC+'] >= 100 else 'worse'} than average (15+ PA)." if n else None)(*leader(bat, "wRC+", need="PA", at_least=15)),
    "", lambda: "League average: 100 by definition", words="weighted runs created plus")
add("Advanced", "iso", "ISO", "Isolated power",
    "Raw power: extra bases per at-bat, leaving singles out.",
    "ISO = SLG − AVG", f"{link('slg', 'SLG')} · {link('avg', 'AVG')}",
    lambda: (lambda n, r: f"{b(n)}: {ui.rate(r.SLG)} SLG − {ui.rate(r.AVG)} AVG = {b(ui.rate(r.ISO))}, the most power in the league (15+ PA)." if n else None)(*leader(bat, "ISO", need="PA", at_least=15)),
    "", lambda: f"League ISO: {ui.rate(lg_rate('TB', 'AB') - lg_rate('H', 'AB'))}", words="isolated power")
add("Advanced", "babip", "BABIP", "Batting average on balls in play",
    "Average on balls put in play, so strikeouts and home runs are left out. Very high or very low usually means "
    "luck that evens out over time. For pitchers, the same idea for hitters he faces.",
    "BABIP = (H − HR) ÷ (AB − K − HR + SF)", f"{link('ab', 'AB')} · K strikeouts · SF sac flies",
    lambda: (lambda n, r: f"{b(n)}: ({int(r.H)} H − {int(r.HR)} HR) ÷ ({int(r.AB)} AB − {int(r.K)} K − {int(r.HR)} HR + {int(r.SF)} SF) "
             f"= {b(ui.rate(r.BABIP))}, the luckiest in the league (15+ PA)." if n else None)(*leader(bat, "BABIP", need="PA", at_least=15)),
    "", lambda: f"League BABIP: {ui.rate(safe_div(T.get('H', 0) - T.get('HR', 0), T.get('AB', 0) - T.get('K', 0) - T.get('HR', 0) + T.get('SF', 0)))}",
    words="balls in play luck")
add("Advanced", "fip", "FIP", "Fielding-independent pitching",
    "ERA counting only what a pitcher controls by himself: strikeouts, walks and home runs. Balls in play depend "
    "partly on fielders and luck, so FIP leaves them out. Same scale as ERA, lower is better.",
    "FIP = (13 HR + 3 BB − 2 K) ÷ IP + C<br>C = lg ERA − (13 lg HR + 3 lg BB − 2 lg K) ÷ lg IP",
    f"HR, BB, K allowed · {link('ip', 'IP')} · C makes the league's FIP equal its {link('era', 'ERA')}",
    lambda: (lambda n, r: f"{b(n)}: {int(r.HR)} HR, {int(r.BB)} BB and {int(r.K)} K in {stats.ip_text(r.OUTS)} innings = "
             f"{b(r2(r.FIP))}, the best in the league (12+ batters faced). His ERA is {r2(r.ERA)}, so "
             f"{'he has been unlucky on balls in play' if r.ERA > r.FIP else 'his results have beaten what he controls'}." if n else None)(*leader(pit, "FIP", low=True, need="BF", at_least=12)),
    "", lambda: f"League FIP = league ERA ({r2(LG_ERA)})", words="fielding independent")
add("Advanced", "eraminus", "ERA-", "ERA minus",
    "ERA with 100 as the league average. Lower is better: 80 is 20% better than the league, 120 is 20% worse.",
    "ERA- = 100 × ERA ÷ lg ERA", f"{link('era', 'ERA')} · lg = league",
    lambda: (lambda n, r: f"{b(n)}: 100 × {r2(r.ERA)} ÷ {r2(LG_ERA)} league ERA = {b(d0(r['ERA-']))}, "
             f"{abs(100 - r['ERA-']):.0f}% {'better' if r['ERA-'] <= 100 else 'worse'} than average (12+ batters faced)." if n else None)(*leader(pit, "ERA-", low=True, need="BF", at_least=12)),
    "", lambda: "League average: 100 by definition", words="era minus")
add("Advanced", "kbb", "K-BB%", "Strikeout rate minus walk rate",
    "Strikeouts minus walks, per batter faced. A quick read on pure pitching skill. Higher is better.",
    "K-BB% = (K − BB) ÷ BF", f"K strikeouts · BB walks · {link('bf', 'BF')}",
    lambda: (lambda n, r: f"{b(n)}: ({int(r.K)} K − {int(r.BB)} BB) ÷ {int(r.BF)} BF = {b(pct(r['K-BB%']))} (12+ batters faced)." if n else None)(*leader(pit, "K-BB%", need="BF", at_least=12)),
    "", lambda: f"League: {pct(safe_div(float(pit['K'].sum() - pit['BB'].sum()), float(pit['BF'].sum())))}", words="k minus bb")
add("Advanced", "oppops", "Opp OPS", "Opponent OPS",
    "The OPS of the hitters a pitcher has faced. Lower is better.",
    "Opp OPS = OBP + SLG of batters faced", f"{link('ops', 'OPS')}",
    lambda: (lambda n, r: f"Hitters have the hardest time against {b(n)}: {b(ui.rate(r.OPP_OPS))} OPS against (12+ batters faced)." if n else None)(*leader(pit, "OPP_OPS", low=True, need="BF", at_least=12)),
    "", None, words="opponent ops against")

# ---- Value
add("Value", "war", "WAR", "Wins above replacement",
    "Wins a player added compared with a fill-in (replacement) player, counting hitting, pitching and fielding. "
    "0.0 is a fill-in; regulars build it up the more they play. Career WAR is the sum of a player's seasons.",
    "WAR = (Bat + Pitch + Field + Repl) ÷ RPW",
    f"{link('batruns', 'Bat')}, {link('pitchruns', 'Pitch')}, {link('fieldruns', 'Field')} = runs above average · "
    f"{link('replruns', 'Repl')} = replacement runs · {link('rpw', 'RPW')} = runs per win",
    lambda: (lambda n: f"{b(n)}: {sign(war.loc[n, 'Batting runs'])} batting, {sign(war.loc[n, 'Pitching runs'])} pitching, "
             f"{sign(war.loc[n, 'Fielding runs'])} fielding and {sign(war.loc[n, 'Replacement runs'])} replacement runs = "
             f"{sign(war.loc[n, 'Runs'] + war.loc[n, 'Replacement runs'])} runs ÷ {d1(rpw)} runs per win = "
             f"{b(sign(war.loc[n, 'WAR']))} WAR, the league lead ({SCOPE})." if n and year is not None else
             f"{b(n)}: {sign(war.loc[n, 'Batting runs'])} batting, {sign(war.loc[n, 'Pitching runs'])} pitching, "
             f"{sign(war.loc[n, 'Fielding runs'])} fielding and {sign(war.loc[n, 'Replacement runs'])} replacement runs, "
             f"turned into wins season by season = {b(sign(war.loc[n, 'WAR']))} WAR, the league lead (career)." if n else None)(war["WAR"].idxmax() if not war.empty else None),
    "", lambda: f"A typical regular adds about +{stats.REPLACEMENT_WAR_PER_GAME * 8:.1f} per 8-game season",
    words="wins above replacement value")
add("Value", "fwar", "fWAR / bWAR", "WAR with one kind of pitching",
    "Two alternate versions of WAR for comparison. fWAR (like FanGraphs) judges pitching only by FIP; bWAR "
    "(like Baseball Reference) only by runs actually allowed. The main WAR blends the two.",
    "fWAR: pitching runs from FIP only · bWAR: from ERA only", f"{link('fip', 'FIP')} · {link('era', 'ERA')} · {link('pitchruns', 'Pitching runs')}",
    None, "If a pitcher's FIP is better than his ERA, his fWAR will be higher than his bWAR.", None, words="fwar bwar fangraphs baseball reference")
add("Value", "waa", "WAA", "Wins above average",
    "WAR without the replacement credit: 0.0 is a league-average player, and the league adds up to zero. Shown on "
    "the Player Dashboard under the WAR tiles.",
    "WAA = (Bat + Pitch + Field) ÷ RPW", f"{link('rpw', 'RPW')} runs per win",
    lambda: (lambda n: f"{b(n)}: {b(sign(war.loc[n, 'WAA']))} wins above average ({SCOPE})." if n else None)(war["WAA"].idxmax() if not war.empty else None),
    "", None, words="wins above average")
add("Value", "batruns", "Batting runs", "Runs above average at the plate",
    "Runs a hitter created beyond what an average hitter would in the same plate appearances.",
    "Bat = (Σ run values − lg rate × PA) ÷ 1.2<br>Σ run values = 0.69 BB + 0.89 1B + 1.27 2B + 1.62 3B + 2.10 HR",
    f"lg rate = league run value per PA · {link('woba', 'same weights as wOBA')}",
    lambda: (lambda n: f"{b(n)}: {b(sign(war.loc[n, 'Batting runs']))} batting runs, the most in the league." if n else None)(war["Batting runs"].idxmax() if not war.empty else None),
    "", None, words="batting runs")
add("Value", "pitchruns", "Pitching runs", "Runs saved above average on the mound",
    "Runs a pitcher kept off the board compared with an average pitcher in the same innings. A blend of FIP and "
    "runs actually allowed: older games use FIP only, and live games move toward a 50/50 mix.",
    "Pitch = (1 − s) × FIP runs + s × RA runs<br>FIP runs = (lg ERA − FIP) × IP ÷ 9 · RA runs = lg ERA × IP ÷ 9 − ER",
    f"s = ½ × share of his innings from live games · {link('fip', 'FIP')} · {link('era', 'ERA')}",
    lambda: (lambda n: f"{b(n)}: {b(sign(war.loc[n, 'Pitching runs']))} pitching runs, the most in the league." if n else None)(war["Pitching runs"].idxmax() if not war.empty else None),
    "", None, words="pitching runs")
add("Value", "fieldruns", "Fielding runs", "Runs saved in the field",
    "Credit for throw-outs and a charge for errors, compared with the league's rate per game. Live-scored games only.",
    "Field = 0.3 × (TO − lg TO per game × G) − 0.5 × (E − lg E per game × G)",
    f"{link('to', 'TO throw-outs')} · {link('err', 'E errors')} · G = live games played",
    lambda: (lambda n: f"{b(n)}: {b(sign(war.loc[n, 'Fielding runs']))} fielding runs." if n and abs(war.loc[n, "Fielding runs"]) > 0.05 else None)(war["Fielding runs"].idxmax() if not war.empty else None),
    "3 throw-outs and no errors over 4 games when the league averages 0.5 throw-outs a game = +0.3 runs.", None, words="fielding runs defense")
add("Value", "replruns", "Replacement runs", "Credit for playing instead of a fill-in",
    f"A small credit for every game played, worth {stats.REPLACEMENT_WAR_PER_GAME:.2f} wins a game: half earned at the "
    "plate and half on the mound. It's why WAR builds up with playing time.",
    f"Repl = ½ × {stats.REPLACEMENT_WAR_PER_GAME:.2f} × RPW × (PA ÷ lg PA per game) + ½ × {stats.REPLACEMENT_WAR_PER_GAME:.2f} × RPW × (IP ÷ lg IP per game)",
    f"{link('rpw', 'RPW')} runs per win · lg PA / IP per game = per player per game",
    lambda: (lambda n: f"{b(n)}: {b(sign(war.loc[n, 'Replacement runs']))} replacement runs from {int(war.loc[n, 'G'])} games." if n else None)(war["G"].idxmax() if not war.empty else None),
    "", None, words="replacement level")
add("Value", "rpw", "Runs per win", "How many runs make one win",
    "WAR turns runs into wins with the league's own scoring: the more runs a game usually has, the more runs it "
    "takes to add a win.",
    "RPW = league runs per game (both teams), at least 3", "",
    lambda: f"Right now it's {b(d1(rpw))} runs per win ({SCOPE})." if len(lgs.completed) else None,
    "", None, words="runs per win")
add("Value", "percentile", "Percentile", "Percentile rank",
    "Where a player ranks in the league, 0 to 100: 100 is the best, 50 the middle. Used on the Visualizations sliders.",
    "Percentile = (rank − 1) ÷ (players − 1) × 100", "rank counted from the worst",
    None, "In a 7-player league, 2nd best = 83rd percentile.", None, words="percentile rank sliders")

# ---- Fielding
add("Fielding", "to", "TO", "Throw-outs",
    "Outs a fielder makes himself on a ball in play or a runner: a normal throw, hitting the runner with the ball, "
    "hitting the sign before the runner scores, or a tag. Recorded in live-scored games.",
    "TO = outs credited to the fielder", f"{link('live', 'Live-scored games')}",
    lambda: (lambda n: f"{b(n)} leads with {b(int(fld.loc[n, 'TO']))} throw-outs." if n else None)(fld["TO"].idxmax() if not fld.empty and fld["TO"].max() > 0 else None),
    "Ground ball, the pitcher throws and hits the runner before first: 1 TO (hit runner).", None, words="throw outs fielding")
add("Fielding", "err", "E", "Errors",
    "A misplay that lets a batter or runner reach or advance when he should have been out. Charged in live-scored games.",
    "E = errors charged to the fielder", "",
    lambda: f"{int(fld['E'].sum())} errors charged so far ({SCOPE})." if not fld.empty else None,
    "", None, words="errors")

# ---- App terms
add("App terms", "live", "Live-scored game", "Recorded pitch by pitch",
    "A game recorded with the Scorekeeper. It saves every pitch, who scored, earned runs and fielding, so stats like "
    "runs scored, errors and real ERA come from these. Older games only saved each at-bat's result and RBIs.",
    None, "",
    lambda: f"{b(int((lgs.games['mode'] == 'live').sum()))} of the league's {len(lgs.games)} games ({SCOPE}) were live-scored.",
    "", None, words="live scorekeeper older games")
add("App terms", "small", "Small sample", "Not much data yet",
    "A tag next to a player whose number rests on very few chances, so it can swing a lot. He's still ranked.",
    "Hitting rates: under 15 PA · Pitching rates: under 12 BF · WAR: under 30 PA + BF", "", None,
    "A 3-for-3 hitter shows a 1.000 average with the tag until he has more at-bats.", None, words="small sample tag")
add("App terms", "alltime", "All-time player", "Plays for both teams",
    "With an odd number of players, one plays for both sides: an all-time hitter bats for both teams and never "
    "fields; an all-time pitcher pitches for both and never bats. Those games count in the Both column, not W/L.",
    None, "", None, "", None, words="all time hitter pitcher both")
add("App terms", "ghost", "Ghost runner", "Holds a base while the player bats",
    "If a player is on base when it's his turn to bat again, a ghost runner takes his base. A run by the ghost "
    "is credited to the player it replaced.",
    None, "", None, "", None, words="ghost runner")
add("App terms", "season", "Career vs season", "Two ways to look at the numbers",
    "Season views use only that year's games and compare players with that year's league. Career uses everything; "
    "career WAR is the sum of a player's seasons.",
    None, "", None, "", None, words="career season picker")
add("App terms", "winpct", "Win %", "Record",
    "Share of games won, with a draw counting as half a win.",
    "Win % = (W + ½ D) ÷ GP", "W wins · D draws · GP games played (not counting Both)",
    lambda: (lambda r: (lambda n: f"{b(n)}: ({int(r.loc[n, 'W'])} W + ½ × {int(r.loc[n, 'D'])} D) ÷ {int(r.loc[n, 'GP'])} GP = "
             f"{b(ui.rate(r.loc[n, 'Pct']))}, the league's best." if n else None)(r["Pct"].idxmax() if not r.empty else None))(stats.records(lgs.completed).dropna(subset=["Pct"])),
    "3 wins, 1 draw and 1 loss = .700.", None, words="record win percentage draw")

KEYS = {e["key"] for e in E}
SECTIONS = []
for e in E:
    if e["section"] not in SECTIONS:
        SECTIONS.append(e["section"])
SECTIONS.insert(SECTIONS.index("App terms"), "Scorebook codes")


# ---------------- Scorebook codes (a compact table, with live counts) ---------------- #
CODES = [  # code, name, counts as, note
    ("1B", "Single", "PA, AB, H", "Batter reaches first on a hit"),
    ("2B", "Double", "PA, AB, H", "Reaches second on a hit"),
    ("3B", "Triple", "PA, AB, H", "Reaches third on a hit"),
    ("HR", "Home run", "PA, AB, H", "Every runner and the batter score"),
    ("BB", "Walk", "PA", "Four balls; not an at-bat"),
    ("K", "Strikeout", "PA, AB", "Three strikes; a foul with two strikes doesn't count"),
    ("GO", "Ground out", "PA, AB", "Out on a ground ball"),
    ("PO", "Pop out", "PA, AB", "Fly ball or pop-up caught"),
    ("LO", "Line out", "PA, AB", "Line drive caught"),
    ("FC", "Fielder's choice", "PA, AB", "Batter safe because the fielders got another runner out"),
    ("SF", "Sacrifice fly", "PA", "Fly out that scores a runner; not an at-bat"),
    ("DP", "Double play", "PA, AB", "Two outs on one play; no RBI"),
    ("TP", "Triple play", "PA, AB", "Three outs on one play; no RBI"),
    ("E", "Reached on error", "PA, AB", "Safe because of a misplay; not a hit, no RBI"),
]


def codes_table(rows):
    counts = lgs.pa["outcome"].value_counts()
    th = f"padding:9px 10px; font-size:12px; font-weight:600; color:{ui.MUTED}; text-align:left;"
    td = "padding:10px 10px; vertical-align:top;"
    body = "".join(
        f"<tr id='code-{c.lower()}' style='border-bottom:1px solid {ui.RULE};'>"
        f"<td style='{td} font-family:{ui.MONO}; font-weight:600;'>{c}</td>"
        f"<td style='{td}'><b>{n}</b><div style='font-size:13px; color:{ui.MUTED}; margin-top:2px;'>{note}</div></td>"
        f"<td style='{td} font-size:13px; white-space:nowrap;'>{counts_as}</td>"
        f"<td style='{td} text-align:right; font-family:{ui.MONO};'>{int(counts.get(c, 0))}</td></tr>"
        for c, n, counts_as, note in rows)
    return ("<table class='gl-codes' style='width:100%; border-collapse:collapse; font-size:15px; margin-top:6px;'>"
            f"<thead><tr style='border-bottom:1px solid {ui.INK};'><th style='{th} width:52px;'>Code</th><th style='{th}'>Meaning</th>"
            f"<th style='{th}'>Counts as</th><th style='{th} text-align:right;'>Times ({escape(SCOPE)})</th></tr></thead>"
            f"<tbody>{body}</tbody></table>"
            f"<p style='margin-top:8px; font-size:12px; color:{ui.MUTED};'>The same codes appear as tags in the Player "
            "Matchups at-bat logs; tap or hover one to see what it means.</p>")


# ---------------- Rendering ---------------- #
def section_head(title):
    return (f"<div id='sec-{title.lower().replace(' ', '-')}' role='heading' aria-level='2' "
            f"style='scroll-margin-top:70px; margin:36px 0 0; padding-bottom:8px; border-bottom:2px solid {ui.INK}; "
            f"font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase;'>{title}</div>")


def label(text):
    return (f"<div style='font-size:11px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; "
            f"color:{ui.MUTED};'>{text}</div>")


HOW_LABEL = label("How it's calculated")


def render(e):
    try:
        example = e["example"]() if e["example"] else None
    except Exception:          # not enough data for this one right now
        example = None
    example = example or e["fallback"]
    try:
        footer = e["footer"]() if e["footer"] else ""
    except Exception:
        footer = ""
    ex_title = "Example from our league" if e["example"] and example != e["fallback"] else "Example"
    ex_box = (f"<div class='gl-ex' style='background:{ui.PANEL}; padding:12px 14px; border-left:2px solid {ui.INK};'>"
              f"{label(ex_title)}<div class='gl-ex-text' style='margin-top:6px; font-size:15px; line-height:1.6;'>{example}</div>"
              + (f"<div style='margin-top:8px; font-size:13px; color:{ui.MUTED};'>{footer}</div>" if footer else "")
              + "</div>") if example else ""
    formula = ""
    phone = ""
    if e["formula"]:
        key = f"<span class='gl-key'>{e['fkey']}</span>" if e["fkey"] else ""
        formula = (f"<div class='gl-how-desk'>{HOW_LABEL}"
                   f"<div style='margin-top:6px; font-family:{ui.MONO}; font-size:13px; line-height:1.6; color:{ui.INK};'>"
                   f"{e['formula']}{key}</div></div>")
        phone = (f"<details class='gl-how-phone'><summary>How it's calculated</summary>"
                 f"<div class='gl-f'>{e['formula']}{key}</div></details>")
    grid = ""
    if formula or ex_box:
        cols = "repeat(auto-fit, minmax(240px, 1fr))" if formula and ex_box else "minmax(0, 1fr)"
        grid = (f"<div class='gl-grid' style='display:grid; grid-template-columns:{cols}; gap:12px 28px; max-width:"
                f"{'none' if formula else '640px'};'>{formula}{ex_box}</div>")
    return (f"<div id='{e['key']}' class='gl-entry' style='padding:22px 0 20px; border-bottom:1px solid {ui.RULE}; scroll-margin-top:80px;'>"
            "<div style='display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;'>"
            f"<span class='gl-name' style='font-family:{ui.SERIF}; font-size:26px; font-weight:500;'>{e['name']}</span>"
            f"<span class='gl-full' style='font-size:14px; color:{ui.MUTED};'>{e['full']}</span></div>"
            f"<p class='gl-means' style='margin:8px 0 12px; font-size:16px; line-height:1.6; max-width:760px;'>{e['means']}</p>"
            f"{grid}{phone}</div>")


def matches(e, query):
    """Every search word has to start a word in the stat's name, full name or keywords ("era" finds ERA and
    ERA-, not "average")."""
    words = re.findall(r"[a-z0-9%+/-]+", " ".join([e["name"], e["full"], e["words"]]).lower())
    return all(any(w.startswith(q) for w in words) for q in re.findall(r"[a-z0-9%+/-]+", query))


# Which entries to show: one term (from a "What's this?" link), a search, or everything
CODE_KEYS = {c[0].lower(): c for c in CODES}
if term and not q and (term in KEYS or term.lower() in CODE_KEYS or term == "codes"):
    shown = [e for e in E if e["key"] == term]
    codes = CODES if term == "codes" else [CODE_KEYS[term.lower()]] if term.lower() in CODE_KEYS else []
    ui.html(f"<p style='margin:4px 0 0; font-size:14px; color:{ui.MUTED};'>Showing {'the scorebook codes' if term == 'codes' else 'one stat'} · "
            f"<a href='./Glossary' target='_self' style='color:{ui.INK};'>Show the whole glossary</a></p>")
elif q:
    shown = [e for e in E if matches(e, q)]
    codes = [c for c in CODES if q == c[0].lower()
             or all(any(w.startswith(x) for w in (c[0] + " " + c[1]).lower().split()) for x in q.split())]
else:
    shown, codes = E, CODES
    ui.html("<div class='gl-jump'>" + "".join(
        f"<a href='#sec-{s.lower().replace(' ', '-')}'>{s}</a>" for s in SECTIONS) + "</div>")

parts, last = [], None
for sec in SECTIONS:
    if sec == "Scorebook codes":
        if codes:
            parts.append(section_head(sec) + codes_table(codes))
        continue
    items = [e for e in shown if e["section"] == sec]
    if items:
        parts.append(section_head(sec) + "".join(render(e) for e in items))
if parts:
    ui.html("".join(parts))
else:
    ui.html(f"<p style='margin-top:24px; color:{ui.MUTED};'>No stat matches “{escape(q)}”. Try a name like ERA, "
            "wOBA or WAR.</p>")