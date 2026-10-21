"""Glue between the game engine and MongoDB for live games.

A live game is one document in `games` with:
    mode: "live", status: "active" | "completed",
    setup: {lineups: {"1": [...], "2": [...]}, rotations: {...}, outs_per_half, all_time}
    events: [ ...engine events, in order... ]

Every time an event is saved, the game's rows in `atbats` are rewritten from the engine,
so all the existing stat pages keep working off `atbats` exactly as before.
"""
import re

import game_engine as ge

OUTCOME_NAMES = {
    "1B": "Single", "2B": "Double", "3B": "Triple", "HR": "Home Run", "BB": "Walk",
    "K": "Strike Out", "GO": "Ground Out", "PO": "Pop Out", "LO": "Line Out",
    "FC": "Fielder's Choice", "SF": "Sacrifice Fly", "DP": "Double Play", "TP": "Triple Play",
    "E": "Reached on Error",
}


def state_for(game):
    return ge.replay(game["setup"], game.get("events", []))


def next_game_id(existing_ids):
    """Game_N with N one past the highest existing number (safe even if games were deleted)."""
    nums = [int(m.group(1)) for gid in existing_ids if (m := re.fullmatch(r"Game_(\d+)", str(gid)))]
    return f"Game_{max(nums, default=0) + 1}"


def atbat_docs(game_id, state):
    docs = []
    for i, pa in enumerate(state.plate_appearances):
        p = pa["pitches"]
        docs.append({
            "game_id": game_id,
            "inning": f"{'Top' if pa['half'] == 'top' else 'Bottom'} {pa['inning']}",
            "batter": pa["batter"],
            "pitcher": pa["pitcher"],
            "strikes": sum(1 for c in p if c in "SFX"),
            "balls": p.count("B"),
            "runners_on": sum(1 for v in pa["bases_before"].values() if v),
            "outcome": OUTCOME_NAMES[pa["outcome"]],
            "outs_recorded": pa["outs_on_play"],
            "rbi": int(pa["rbi"]),
            # Live-only detail (used by the corrected stats later)
            "live": True,
            "seq": i,
            "team": pa["team"],
            "pitches": p,
            "runs": pa["runs"],
            "error_fielder": pa["error_fielder"],
            "out_details": pa.get("out_details", []),
            "outs_before": pa["outs_before"],
        })
    return docs


def sync_atbats(db, game_id, state):
    db.atbats.delete_many({"game_id": game_id})
    docs = atbat_docs(game_id, state)
    if docs:
        db.atbats.insert_many(docs)


def batter_line(state, name):
    """'1-for-2' style line for this game (walks and sac flies aren't at-bats)."""
    pas = [p for p in state.plate_appearances if p["batter"] == name]
    if not pas:
        return "first time up"
    ab = sum(1 for p in pas if p["outcome"] not in ("BB", "SF"))
    h = sum(1 for p in pas if p["outcome"] in ge.HITS)
    extra = [f"{sum(1 for p in pas if p['outcome'] == 'BB')} BB"] if any(p["outcome"] == "BB" for p in pas) else []
    return ", ".join([f"{h}-for-{ab}"] + extra) + " today"


def ordinal(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")