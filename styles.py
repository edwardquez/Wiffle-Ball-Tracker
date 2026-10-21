"""Shared look for every page: colors, fonts, page CSS and small HTML building blocks.

Usage on a page (right after st.set_page_config):

    import styles as ui
    ui.apply()
    ui.html(ui.section_label("Leaders") + ui.kpi_grid([...]))
"""

from html import escape
from urllib.parse import quote

import pandas as pd
import streamlit as st

# ---------- Colors ---------- #
CREAM = "#FDFBF7"     # page background
PANEL = "#F6F2EA"     # sidebar / subtle fills
INK = "#14213D"       # deep navy text and rules
BODY = "#2E3A55"      # body copy
MUTED = "#4A5470"     # labels, secondary text
RULE = "#E3DDD0"      # thin dividers
TRACK = "#ECE6DA"     # empty part of a bar

WIN = "#2E6B4E"       # green: win / better
LOSS = "#A8432C"      # brick red: loss / worse
DRAW = "#3F5F86"      # blue: draw
GOLD = "#8A5F0E"      # home runs

# ---------- Fonts ---------- #
# Double quotes inside, because the HTML blocks use single-quoted style='...' attributes
SERIF = '"Newsreader", Georgia, serif'
SANS = '"IBM Plex Sans", system-ui, sans-serif'
MONO = '"IBM Plex Mono", ui-monospace, monospace'

_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600"
    "&family=IBM+Plex+Sans:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
)

_CSS = f"""
<style>
@import url('{_FONTS_URL}');

/* Content column: comfortable reading width, generous top space */
[data-testid="stMainBlockContainer"] {{
    max-width: 1040px;
    padding-top: 3.5rem;
    padding-bottom: 5rem;
}}

/* Page titles */
h1 {{ letter-spacing: -0.8px; }}

/* Numbers line up in columns everywhere */
body {{ font-variant-numeric: tabular-nums; }}

/* Our HTML tables: no default cell borders/fills (rows draw their own hairlines) */
.wf table {{ border: none; }}
.wf th, .wf td {{ border: none !important; background: transparent !important; }}

/* Links inside our HTML blocks */
.wf a {{ color: {INK}; text-decoration-color: rgba(20,33,61,0.35); text-underline-offset: 3px; }}
.wf a:hover {{ text-decoration-color: {INK}; }}
</style>
"""


def apply():
    """Inject the shared CSS. Call once per page, right after st.set_page_config."""
    st.markdown(_CSS + TIP_CSS, unsafe_allow_html=True)


TIP_CSS = f"""
<style>
.wf-tap {{ position:relative; cursor:pointer; outline:none; -webkit-tap-highlight-color:transparent; }}
.wf-tap:focus {{ box-shadow:0 0 0 2px {INK}; z-index:5; }}
.wf-tip {{ display:none; position:absolute; bottom:calc(100% + 8px); left:50%; transform:translateX(-50%);
  width:max-content; max-width:230px; padding:8px 10px; background:{INK}; color:{CREAM};
  font-family:{SANS}; font-size:13px; font-weight:400; line-height:1.4; text-align:left; letter-spacing:0;
  text-transform:none; white-space:normal; z-index:20; pointer-events:none; box-shadow:0 4px 14px rgba(20,33,61,0.18); }}
.wf-tip b {{ font-weight:600; }}
.wf-tip::after {{ content:""; position:absolute; top:100%; left:50%; margin-left:-5px; border:5px solid transparent;
  border-top-color:{INK}; }}
.wf-tip.wf-l {{ left:0; transform:none; }} .wf-tip.wf-l::after {{ left:18px; }}
.wf-tip.wf-r {{ left:auto; right:0; transform:none; }} .wf-tip.wf-r::after {{ left:auto; right:13px; }}
.wf-tap:hover .wf-tip, .wf-tap:focus .wf-tip {{ display:block; }}
.wf-tip.wf-noarrow::after {{ display:none; }}
</style>"""


def tip(text, align=""):
    """Tooltip box, placed inside an element that has TAP in its attributes. Shows on hover (mouse) and on
    tap (phones: the element takes focus; tapping elsewhere closes it). align: "" centered, "wf-l" / "wf-r"
    to line it up with the element's left / right edge near the sides of the screen."""
    return f"<span class='wf-tip {align}'>{text}</span>"


TAP = "class='wf-tap' tabindex='0'"     # attributes that make an element tappable for tip()


def glossary_link(term, margin="0"):
    """Small "What's this? ->" link that opens the Glossary on one stat (term = its key there)."""
    return (f"<a href='./Glossary?term={term}' target='_self' style='display:inline-block; margin:{margin}; "
            f"font-size:13px; color:{MUTED}; text-decoration-color:rgba(74,84,112,0.4);'>What's this? &rarr;</a>")


def game_label(game_id):
    """'Game_9' -> 'Game 9' for display (the id itself stays as stored)."""
    return str(game_id).replace('_', ' ')


def html(markup):
    """Render one of the HTML blocks below."""
    st.markdown(f"<div class='wf'>{markup}</div>", unsafe_allow_html=True)


# ---------- Formatting helpers ---------- #
def rate(value, digits=3):
    """.476 instead of 0.476 (baseball style)."""
    if value is None or pd.isna(value):
        return "—"
    text = f"{value:.{digits}f}"
    return text[1:] if text.startswith("0.") else text


def date_text(value):
    """Jun 27, 2025 (no leading zero on the day)."""
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return "Unknown date"
    return f"{ts.strftime('%b')} {ts.day}, {ts.year}"


def names_with_ties(names):
    """'Carl' or 'Edward, Jason (tied)'."""
    names = list(names)
    if not names:
        return "—"
    return names[0] if len(names) == 1 else ", ".join(names) + " (tied)"


# ---------- Building blocks (each returns an HTML string) ---------- #
def eyebrow(text):
    """Small uppercase label above a title."""
    return (
        f"<div style='font-size:12px; font-weight:600; letter-spacing:1.6px; "
        f"text-transform:uppercase; color:{MUTED};'>{escape(text)}</div>"
    )


def section_label(text, margin_top=0):
    """Small uppercase section heading, as on the stat-sheet mockups."""
    return (
        # role=heading instead of <h2>: Streamlit adds a link icon to real headings
        f"<div role='heading' aria-level='2' style='margin:{margin_top}px 0 12px; padding:0; font-family:{SANS}; "
        f"font-size:12px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase; color:{MUTED};'>"
        f"{escape(text)}</div>"
    )


def small_sample(title="Small sample"):
    """Tiny muted tag for numbers built on very few plate appearances or batters faced.
    `title` is the hover text (e.g. 'Only 3 at-bats')."""
    return (
        f"<span title='{escape(title)}' style='display:inline-block; margin-left:5px; padding:0 3px; "
        f"border:1px solid {RULE}; color:{MUTED}; font-family:{SANS}; font-size:8.5px; font-weight:500; "
        f"letter-spacing:0.4px; text-transform:uppercase; line-height:12px; vertical-align:middle; "
        f"white-space:nowrap;'>small sample</span>"
    )


def kpi_grid(items, min_width=160):
    """Big floating numbers under one navy rule.

    items: list of dicts with 'value', 'label' and optionally 'who' (a player name line)
    and 'who_tag' (extra HTML after the name, e.g. small_sample()).
    """
    cells = []
    for item in items:
        who = ""
        if item.get("who"):
            who = (
                f"<div style='margin-top:8px; font-size:15px; font-weight:600;'>"
                f"{escape(str(item['who']))}{item.get('who_tag', '')}</div>"
            )
        cells.append(
            "<div style='padding:24px 0 4px; display:flex; flex-direction:column; gap:6px;'>"
            f"<div style='font-family:{SERIF}; font-size:44px; font-weight:500; line-height:1;'>"
            f"{escape(str(item['value']))}</div>"
            f"<div style='font-size:13px; color:{MUTED};'>{escape(str(item['label']))}</div>"
            f"{who}</div>"
        )
    return (
        f"<div style='display:grid; grid-template-columns:repeat(auto-fit, minmax({min_width}px, 1fr)); "
        f"column-gap:24px; border-top:2px solid {INK}; margin-bottom:8px;'>{''.join(cells)}</div>"
    )


def tag(text, color):
    """Small outlined uppercase tag (FINAL, DRAW, IN PROGRESS...)."""
    return (
        f"<span style='display:inline-block; padding:2px 8px; border:1px solid {color}; color:{color}; "
        f"font-weight:600; font-size:12px; letter-spacing:1px; text-transform:uppercase;'>{escape(text)}</span>"
    )


def scoreline(team1, score1, team2, score2, colors=None, weights=None):
    """'Edward, Arath, Carl   4 – 4   Uriel, Vera, Jason' on one centered line.

    colors/weights: optional (team1, team2) pairs, e.g. win/loss colors on the Game Log.
    """
    c1, c2 = colors or (INK, INK)
    w1, w2 = weights or (400, 400)
    return (
        "<div style='display:grid; grid-template-columns:minmax(0,1fr) auto minmax(0,1fr); "
        "align-items:center; gap:28px; padding:22px 0;'>"
        f"<span style='text-align:right; font-size:17px; color:{c1}; font-weight:{w1};'>{escape(team1)}</span>"
        f"<span style='display:flex; align-items:center; gap:16px; font-family:{SERIF}; font-size:30px; "
        f"font-weight:500; line-height:1;'>"
        f"<span style='color:{c1};'>{score1}</span>"
        f"<span style='display:inline-block; width:14px; height:1px; background:{MUTED};'></span>"
        f"<span style='color:{c2};'>{score2}</span></span>"
        f"<span style='text-align:left; font-size:17px; color:{c2}; font-weight:{w2};'>{escape(team2)}</span>"
        "</div>"
    )


_ARROW = (
    f"<svg aria-hidden='true' width='14' height='14' viewBox='0 0 14 14' fill='none' "
    f"stroke='{MUTED}' stroke-width='1.5'><path d='M3 7h8M7.5 3.5L11 7l-3.5 3.5'></path></svg>"
)


def player_links(names, min_width=180):
    """Grid of player names, each linking to that player's dashboard."""
    links = "".join(
        f"<a href='./Player_Dashboard?player={quote(name)}' target='_self' "
        f"style='display:flex; justify-content:space-between; align-items:center; padding:16px 16px 16px 0; "
        f"margin-right:16px; border-bottom:1px solid {RULE}; text-decoration:none; font-size:16px; "
        f"font-weight:500; min-height:44px; box-sizing:border-box;'>{escape(name)}{_ARROW}</a>"
        for name in names
    )
    return (
        f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax({min_width}px, 1fr)); "
        f"border-top:2px solid {INK};'>{links}</div>"
    )


def stat_grid(items, min_width=120):
    """Secondary stats: smaller monospace numbers in a grid under a thin rule.

    items: list of dicts with 'value' and 'label'.
    """
    cells = "".join(
        "<div style='display:flex; flex-direction:column; gap:4px;'>"
        f"<div style='font-family:{MONO}; font-size:20px; font-weight:500;'>{escape(str(item['value']))}</div>"
        f"<div style='font-size:12px; color:{MUTED};'>{escape(str(item['label']))}</div></div>"
        for item in items
    )
    return (
        f"<div style='display:grid; grid-template-columns:repeat(auto-fill, minmax({min_width}px, 1fr)); "
        f"gap:18px 24px; margin-top:20px; padding-top:20px; border-top:1px solid {RULE};'>{cells}</div>"
    )


def innings(outs):
    """Baseball innings notation from outs: 47 outs -> '15.2' (15 innings + 2 outs)."""
    if outs is None or pd.isna(outs):
        return "—"
    outs = int(outs)
    return f"{outs // 3}.{outs % 3}"