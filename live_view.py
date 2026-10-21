"""Shared pieces for showing a live game: scoreboard, bases diamond and line score.
Used by the Scorekeeper, the Live page and the Game Log box score."""
from html import escape

import styles as ui


def scoreboard(s):
    half = "Top" if s.half == "top" else "Bot"
    boxes = "".join(
        f"<span style='width:11px; height:11px; box-sizing:border-box; display:inline-block; "
        f"{'background:' + ui.INK if i < s.outs else 'border:1px solid ' + ui.INK};'></span>"
        for i in range(s.outs_limit))
    team = lambda t, align: (
        f"<div style='display:flex; flex-direction:column; align-items:{align}; gap:2px;'>"
        f"<span style='font-size:12px; color:{ui.MUTED};'>Team {t}{' · batting' if s.batting_team == t else ''}</span>"
        f"<span style='font-family:{ui.SERIF}; font-size:36px; font-weight:500; line-height:1;'>{s.score[t]}</span></div>")
    return (f"<div style='display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:8px; "
            f"padding:4px 0 14px; border-bottom:2px solid {ui.INK};'>{team(1, 'flex-start')}"
            f"<div style='display:flex; flex-direction:column; align-items:center; gap:7px;'>"
            f"<span style='font-size:12px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase;'>{half} {s.inning}</span>"
            f"<div role='img' aria-label='{s.outs} out' style='display:flex; gap:6px;'>{boxes}</div></div>"
            f"{team(2, 'flex-end')}</div>")

def base_label(r):
    if not r:
        return f"<span style='color:{ui.MUTED};'>—</span>"
    ghost = f" <span style='font-weight:400; color:{ui.MUTED};'>(ghost)</span>" if r.ghost else ""
    return f"<span style='font-weight:600;'>{escape(r.name)}</span>{ghost}"

def diamond(s):
    b = s.bases
    fill = lambda k: ui.INK if b[k] else ui.CREAM
    svg = (f"<svg width='132' height='112' viewBox='0 0 150 130' role='img' aria-label='Bases'>"
           f"<path d='M75 14 L136 70 L75 122 L14 70 Z' fill='none' stroke='#CFC8BA' stroke-width='1.5'></path>"
           f"<rect x='64' y='3' width='22' height='22' transform='rotate(45 75 14)' fill='{fill(2)}' stroke='{ui.INK}' stroke-width='1.5'></rect>"
           f"<rect x='125' y='59' width='22' height='22' transform='rotate(45 136 70)' fill='{fill(1)}' stroke='{ui.INK}' stroke-width='1.5'></rect>"
           f"<rect x='3' y='59' width='22' height='22' transform='rotate(45 14 70)' fill='{fill(3)}' stroke='{ui.INK}' stroke-width='1.5'></rect>"
           f"<path d='M66 113 L84 113 L84 120 L75 127 L66 120 Z' fill='{ui.CREAM}' stroke='{ui.INK}' stroke-width='1.5'></path></svg>")
    small = lambda txt: f"<span style='font-size:11px; letter-spacing:1px; text-transform:uppercase; color:{ui.MUTED};'>{txt}</span>"
    return (f"<div style='display:grid; grid-template-columns:1fr 132px 1fr; align-items:center; column-gap:6px; padding:12px 0 4px;'>"
            f"<div style='grid-column:1 / 4; text-align:center; font-size:15px;'>{small('2nd ')}{base_label(b[2])}</div>"
            f"<div style='text-align:right; font-size:15px; padding-top:24px;'>{small('3rd')}<br>{base_label(b[3])}</div>"
            f"<div>{svg}</div>"
            f"<div style='font-size:15px; padding-top:24px;'>{small('1st')}<br>{base_label(b[1])}</div></div>")

def line_score(s):
    n = max(len(s.line[1]), len(s.line[2]))
    th = "padding:6px 0; font-weight:500; text-align:center;"
    head = "".join(f"<th style='{th}'>{i + 1}</th>" for i in range(n))
    def row(t):
        cells = "".join(f"<td style='padding:9px 0; text-align:center;'>{s.line[t][i] if i < len(s.line[t]) else '–'}</td>" for i in range(n))
        return (f"<tr style='border-bottom:1px solid {ui.RULE};'><th scope='row' style='text-align:left; padding:9px 0; "
                f"font-family:{ui.SANS}; font-weight:500;'>Team {t}</th>{cells}"
                f"<td style='padding:9px 0 9px 8px; text-align:center; font-weight:600;'>{s.score[t]}</td>"
                f"<td style='padding:9px 0; text-align:center;'>{s.hits[t]}</td><td style='padding:9px 0; text-align:center;'>{s.errors[t]}</td></tr>")
    return (f"<div style='overflow-x:auto;'><table style='width:100%; border-collapse:collapse; font-family:{ui.MONO}; font-size:13px;'>"
            f"<thead><tr style='color:{ui.MUTED}; border-bottom:1px solid {ui.INK};'><th style='width:30%;'></th>{head}"
            f"<th style='{th} padding-left:8px; color:{ui.INK}; font-weight:600;'>R</th><th style='{th}'>H</th><th style='{th}'>E</th></tr></thead>"
            f"<tbody>{row(1)}{row(2)}</tbody></table></div>")