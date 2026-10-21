"""Shared stat definitions for every page.

Every page builds its numbers from the same four tables, so a player's AVG or ERA is the same
wherever it's shown:

    pa        one row per plate appearance (older games from `atbats`, live games from a replay)
    runs      one row per run scored          (live games only)
    pitches   one row per pitch               (live games only)
    fielding  one row per error or throw-out  (live games only)
    runner_outs  one row per caught stealing / pickoff, for the pitcher's outs (live games only)

Pages should use `lg.batting(...)` and `lg.pitching(...)`: they pass the right tables together
(runner outs count toward a pitcher's innings, runs scored go to the runner).

Older games only recorded outcome + RBI per at-bat, so stats that need more detail (runs scored,
earned runs from the real base state, pitch counts, errors, throw-outs) come from live games only.

Definitions
    PA   every plate appearance
    AB   PA - walks - sac flies (errors and fielder's choices count as at-bats)
    AVG  H / AB          OBP  (H + BB) / (AB + BB + SF)          SLG  TB / AB      OPS  OBP + SLG
    K%   K / PA          BB%  BB / PA
    IP   outs / 3 (outs on plate appearances plus caught stealing and pickoffs)
    ER   live games: earned runs charged to the pitcher (inherited runners go to whoever put them on);
         older games: RBIs allowed (the only run data they have)
    ERA  ER * 9 / IP     WHIP (BB + H) / IP      K/9, BB/9 per 9 innings
"""
import copy

import numpy as np
import pandas as pd

import game_engine as ge
from live_scoring import OUTCOME_NAMES

CODE_OF = {name: code for code, name in OUTCOME_NAMES.items()}
HITS = ("1B", "2B", "3B", "HR")
TOTAL_BASES = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}
HOW_LABELS = {"throw": "Normal throw", "runner": "Hit runner", "sign": "Hit the sign", "tag": "Tagged"}

PA_COLS = ["game_id", "game_order", "seq", "live", "inning", "team", "batter", "pitcher", "outcome",
           "rbi", "outs", "strikes", "balls", "error_fielder", "runners_on"]
RUN_COLS = ["game_id", "player", "pitcher", "earned", "batter", "via", "inning"]
PITCH_COLS = ["game_id", "pitcher", "batter", "result"]
FIELD_COLS = ["game_id", "player", "kind", "how", "batter", "pitcher"]
OUT_COLS = ["game_id", "pitcher", "runner", "kind", "inning"]
# Every play that scored a run in a live game, in the order it happened (for the Game Log feed)
SCORE_COLS = ["game_id", "n", "inning", "team", "player", "outcome", "rbi", "runs"]


def _num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def _div(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(b > 0, a / b, np.nan)


class League:
    """All the tables a page needs. Build once per page with `League.from_db(db)`."""

    def __init__(self, players, games, atbats):
        self.players = players.copy()
        if "name" not in self.players.columns:
            self.players["name"] = None
        self.games = _clean_games(games)
        (self.pa, self.runs, self.pitches, self.fielding, self.runner_outs,
         self.scoring, self.problems) = _build_tables(self.games, atbats)

    @classmethod
    def from_db(cls, db):
        return cls(pd.DataFrame(list(db.players.find())), pd.DataFrame(list(db.games.find())),
                   pd.DataFrame(list(db.atbats.find())))

    @property
    def names(self):
        return sorted(self.players["name"].dropna().unique())

    @property
    def live_players(self):
        """Everyone who was in a live-scored game (lineups and pitchers): the players who can
        have runs scored, errors and throw-outs recorded."""
        out = set()
        for setup in self.games.loc[self.games["mode"] == "live", "setup"]:
            if isinstance(setup, dict):
                for group in ("lineups", "rotations"):
                    for names in (setup.get(group) or {}).values():
                        out.update(names)
        return out

    @property
    def completed(self):
        """Completed games oldest first, numbered per season like the Game Log."""
        g = self.games.dropna(subset=["team1_score", "team2_score"]).copy()
        g["match_no"] = g.groupby(g["date"].dt.year).cumcount() + 1
        return g

    # ---- convenience filters ----
    def subset(self, games=None, batter=None, pitcher=None):
        """Tables restricted to some games and/or a batter/pitcher (e.g. one game, one matchup)."""
        pa, runs, pitches, fl = self.pa, self.runs, self.pitches, self.fielding
        if games is not None:
            games = set(games)
            pa, runs = pa[pa.game_id.isin(games)], runs[runs.game_id.isin(games)]
            pitches, fl = pitches[pitches.game_id.isin(games)], fl[fl.game_id.isin(games)]
        if batter is not None:
            pa, runs = pa[pa.batter == batter], runs[runs.batter == batter]
            pitches, fl = pitches[pitches.batter == batter], fl[fl.batter == batter]
        if pitcher is not None:
            pa, runs = pa[pa.pitcher == pitcher], runs[runs.pitcher == pitcher]
            pitches, fl = pitches[pitches.pitcher == pitcher], fl[fl.pitcher == pitcher]
        return pa, runs, pitches, fl

    def batting(self, games=None, batter=None, pitcher=None):
        """Hitting lines for some games and/or one batter/pitcher matchup."""
        pa, _, _, _ = self.subset(games, batter, pitcher)
        runs = self.runs
        if games is not None:
            runs = runs[runs.game_id.isin(set(games))]
        if pitcher is not None:
            runs = runs[runs.pitcher == pitcher]
        return batting(pa, runs)

    def pitching(self, games=None, batter=None, pitcher=None):
        """Pitching lines, with caught-stealing and pickoff outs counted in IP.
        With `batter` (one matchup) runner outs are left out: they aren't the batter's."""
        pa, runs, pitches, _ = self.subset(games, batter, pitcher)
        outs = self.runner_outs if batter is None else self.runner_outs.iloc[0:0]
        if games is not None:
            outs = outs[outs.game_id.isin(set(games))]
        if pitcher is not None:
            outs = outs[outs.pitcher == pitcher]
        return pitching(pa, runs, pitches, outs=outs)

    def advanced_batting(self):
        """lg.batting() plus wOBA, wRC+, ISO and BABIP (see advanced_batting below)."""
        return advanced_batting(self.batting(), league_runs_per_pa(self))

    def advanced_pitching(self):
        """lg.pitching() plus FIP, ERA-, K-BB% and opponent OPS (see advanced_pitching below)."""
        return advanced_pitching(self.pitching(), self.pa)

    @property
    def pitcher_outs(self):
        """All outs recorded by each pitcher (plate appearances + runner outs)."""
        o = self.pa.groupby("pitcher")["outs"].sum() if not self.pa.empty else pd.Series(dtype=float)
        r = self.runner_outs.groupby("pitcher").size() if not self.runner_outs.empty else pd.Series(dtype=float)
        return o.add(r, fill_value=0).astype(float)


# ------------------------------------------------------------------ building the tables

def _clean_games(games):
    g = games.copy()
    for col in ("_id", "game_id", "date", "team1", "team2", "team1_players", "team2_players",
                "team1_score", "team2_score", "status", "mode", "setup", "events"):
        if col not in g.columns:
            g[col] = None
    g["date"] = pd.to_datetime(g["date"], errors="coerce")
    g["team1_score"] = pd.to_numeric(g["team1_score"], errors="coerce")
    g["team2_score"] = pd.to_numeric(g["team2_score"], errors="coerce")
    if not g.empty:
        g = g.sort_values("_id").reset_index(drop=True)
    g["game_order"] = range(len(g))
    return g


def _build_tables(games, atbats):
    pa_rows, run_rows, pitch_rows, field_rows, out_rows, score_rows, problems = [], [], [], [], [], [], []
    order = dict(zip(games["game_id"], games["game_order"]))
    live = games[games["mode"] == "live"]
    live_ids = set(live["game_id"])

    # Older games: straight from the atbats collection
    ab = atbats.copy()
    for col in ("_id", "game_id", "inning", "batter", "pitcher", "outcome", "rbi", "outs_recorded",
                "strikes", "balls", "live", "runners_on"):
        if col not in ab.columns:
            ab[col] = None
    ab = ab[~ab["game_id"].isin(live_ids) & (ab["live"] != True)]   # noqa: E712
    if not ab.empty:
        ab = ab.sort_values("_id")
    for i, r in enumerate(ab.itertuples(index=False)):
        pa_rows.append({
            "game_id": r.game_id, "game_order": order.get(r.game_id, -1), "seq": i, "live": False,
            "inning": r.inning, "team": np.nan, "batter": r.batter, "pitcher": r.pitcher,
            "outcome": CODE_OF.get(r.outcome, r.outcome), "rbi": r.rbi, "outs": r.outs_recorded,
            "strikes": r.strikes, "balls": r.balls, "error_fielder": None, "runners_on": r.runners_on,
        })

    # Live games: replay the recorded events (the source of truth for these games)
    for g in live.itertuples(index=False):
        if not isinstance(g.setup, dict):
            continue
        try:
            s = ge.replay(g.setup, g.events or [])
        except ge.GameError as e:
            problems.append(f"{g.game_id}: {e}")
            continue
        gid = g.game_id
        for i, p in enumerate(s.plate_appearances):
            seq = p["pitches"]
            pa_rows.append({
                "game_id": gid, "game_order": order.get(gid, -1), "seq": i, "live": True,
                "inning": f"{'Top' if p['half'] == 'top' else 'Bottom'} {p['inning']}", "team": p["team"],
                "batter": p["batter"], "pitcher": p["pitcher"], "outcome": p["outcome"], "rbi": p["rbi"],
                "outs": p["outs_on_play"], "strikes": sum(c in "SFX" for c in seq), "balls": seq.count("B"),
                "error_fielder": p["error_fielder"],
                "runners_on": sum(1 for v in p["bases_before"].values() if v),
            })
            if p["runs"]:
                score_rows.append({"game_id": gid, "n": p.get("n", i), "inning": pa_rows[-1]["inning"],
                                   "team": p["team"], "player": p["batter"], "outcome": p["outcome"],
                                   "rbi": p["rbi"], "runs": len(p["runs"])})
            for run in p["runs"]:
                run_rows.append({"game_id": gid, "player": run["player"], "pitcher": run["pitcher"],
                                 "earned": run["earned"], "batter": p["batter"], "via": "play",
                                 "inning": p["inning"]})
            if p["error_fielder"]:
                field_rows.append({"game_id": gid, "player": p["error_fielder"], "kind": "E", "how": None,
                                   "batter": p["batter"], "pitcher": p["pitcher"]})
            for d in p.get("out_details", []):
                if d.get("by"):
                    field_rows.append({"game_id": gid, "player": d["by"], "kind": "TO", "how": d.get("how"),
                                       "batter": p["batter"], "pitcher": p["pitcher"]})
        for ev in s.runner_events:
            if ev["runs"]:
                score_rows.append({"game_id": gid, "n": ev.get("n", 0),
                                   "inning": f"{'Top' if ev['half'] == 'top' else 'Bottom'} {ev['inning']}",
                                   "team": ev["team"], "player": ev["runner"], "outcome": "SB home",
                                   "rbi": 0, "runs": len(ev["runs"])})
            for run in ev["runs"]:
                run_rows.append({"game_id": gid, "player": run["player"], "pitcher": run["pitcher"],
                                 "earned": run["earned"], "batter": None, "via": ev["kind"],
                                 "inning": ev["inning"]})
            if ev["kind"] in ("CS", "PO"):
                out_rows.append({"game_id": gid, "pitcher": ev["pitcher"], "runner": ev["runner"], "kind": ev["kind"],
                                 "inning": ev["inning"]})
            if ev.get("by"):
                field_rows.append({"game_id": gid, "player": ev["by"], "kind": "TO", "how": ev.get("how"),
                                   "batter": None, "pitcher": ev["pitcher"]})
        for pitcher, batter, result in s.pitch_log:
            pitch_rows.append({"game_id": gid, "pitcher": pitcher, "batter": batter, "result": result})

    pa = pd.DataFrame(pa_rows, columns=PA_COLS)
    if not pa.empty:
        pa = pa.sort_values(["game_order", "seq"]).reset_index(drop=True)
        for col in ("rbi", "outs", "strikes", "balls"):
            pa[col] = _num(pa[col])
    return (pa, pd.DataFrame(run_rows, columns=RUN_COLS), pd.DataFrame(pitch_rows, columns=PITCH_COLS),
            pd.DataFrame(field_rows, columns=FIELD_COLS), pd.DataFrame(out_rows, columns=OUT_COLS),
            pd.DataFrame(score_rows, columns=SCORE_COLS).sort_values(["game_id", "n"]).reset_index(drop=True), problems)


# ------------------------------------------------------------------ aggregations

def batting(pa, runs=None, by="batter"):
    """Hitting line per player (or per game_id, etc. via `by`)."""
    cols = ["PA", "AB", "H", "1B", "2B", "3B", "HR", "BB", "K", "SF", "RBI", "R", "TB",
            "AVG", "OBP", "SLG", "OPS", "K%", "BB%", "G"]
    pa = pa.dropna(subset=[by])
    if pa.empty:
        return pd.DataFrame(columns=cols)
    o = pa["outcome"]
    t = pd.DataFrame({
        by: pa[by], "PA": 1, "BB": o.eq("BB"), "K": o.eq("K"), "SF": o.eq("SF"),
        "1B": o.eq("1B"), "2B": o.eq("2B"), "3B": o.eq("3B"), "HR": o.eq("HR"),
        "H": o.isin(HITS), "TB": o.map(TOTAL_BASES).fillna(0), "RBI": pa["rbi"], "live": pa["live"],
        "game_id": pa["game_id"],
    })
    g = t.groupby(by)
    out = g[["PA", "BB", "K", "SF", "1B", "2B", "3B", "HR", "H", "TB", "RBI"]].sum().astype(float)
    out["G"] = g["game_id"].nunique()
    out["AB"] = out["PA"] - out["BB"] - out["SF"]
    out["AVG"] = _div(out["H"], out["AB"])
    out["OBP"] = _div(out["H"] + out["BB"], out["AB"] + out["BB"] + out["SF"])
    out["SLG"] = _div(out["TB"], out["AB"])
    out["OPS"] = out["OBP"] + out["SLG"]
    out["K%"] = _div(out["K"], out["PA"])
    out["BB%"] = _div(out["BB"], out["PA"])
    # Runs scored: only live games record who scored
    has_live = g["live"].any()
    scored = runs.groupby("player").size() if runs is not None and by == "batter" and not runs.empty else pd.Series(dtype=float)
    out["R"] = [float(scored.get(name, 0)) if has_live.get(name, False) else np.nan for name in out.index]
    return out[cols]


def pitching(pa, runs=None, pitches=None, by="pitcher", outs=None):
    """Pitching line per pitcher. `outs`: runner-out rows (caught stealing / pickoffs) to add to OUTS."""
    cols = ["G", "BF", "OUTS", "IP", "H", "BB", "K", "HR", "ER", "R", "ERA", "WHIP", "K/9", "BB/9",
            "K%", "P", "STR", "STR%", "DP"]
    pa = pa.dropna(subset=[by])
    if pa.empty:
        return pd.DataFrame(columns=cols)
    o = pa["outcome"]
    t = pd.DataFrame({
        by: pa[by], "BF": 1, "OUTS": pa["outs"], "H": o.isin(HITS), "BB": o.eq("BB"), "K": o.eq("K"),
        "HR": o.eq("HR"), "DP": o.eq("DP"), "old_er": np.where(pa["live"], 0, pa["rbi"]),
        "live": pa["live"], "game_id": pa["game_id"],
    })
    g = t.groupby(by)
    out = g[["BF", "OUTS", "H", "BB", "K", "HR", "DP", "old_er"]].sum().astype(float)
    out["G"] = g["game_id"].nunique()
    has_live = g["live"].any()
    if outs is not None and not outs.empty and by in outs.columns:
        extra = outs.groupby(by).size()
        # A pitcher whose only outs were pickoffs still gets a line
        out = out.reindex(out.index.union(extra.index)).fillna(0)
        out["OUTS"] = out["OUTS"] + extra.reindex(out.index).fillna(0)
        has_live = has_live.reindex(out.index).fillna(True).astype(bool)

    runs = runs if runs is not None else pd.DataFrame(columns=RUN_COLS)
    charged = runs.groupby("pitcher").size() if not runs.empty else pd.Series(dtype=float)
    earned = runs[runs["earned"] == True].groupby("pitcher").size() if not runs.empty else pd.Series(dtype=float)  # noqa: E712
    out["ER"] = out["old_er"] + [float(earned.get(n, 0)) for n in out.index]
    out["R"] = [float(charged.get(n, 0)) if has_live.get(n, False) else np.nan for n in out.index]

    out["IP"] = out["OUTS"] / 3
    out["ERA"] = _div(out["ER"] * 9, out["IP"])
    out["WHIP"] = _div(out["BB"] + out["H"], out["IP"])
    out["K/9"] = _div(out["K"] * 9, out["IP"])
    out["BB/9"] = _div(out["BB"] * 9, out["IP"])
    out["K%"] = _div(out["K"], out["BF"])

    # Pitch counts. Live games: every pitch was tapped in (fouls with two strikes and the pitch put in
    # play included). Older games: only the count at the end of each at-bat was saved, so their
    # pitches = strikes + balls as recorded (a little low: two-strike fouls and the in-play pitch
    # weren't saved).
    pitches = pitches if pitches is not None else pd.DataFrame(columns=PITCH_COLS)
    if not pitches.empty:
        pc = pitches.groupby("pitcher")["result"].agg(P="size", STR=lambda r: r.isin(["S", "F", "X"]).sum())
    else:
        pc = pd.DataFrame(columns=["P", "STR"])
    old = pa[pa["live"] != True]          # noqa: E712
    old_str = old.groupby(by)["strikes"].sum() if not old.empty else pd.Series(dtype=float)
    old_p = (old.groupby(by)["strikes"].sum() + old.groupby(by)["balls"].sum()) if not old.empty else pd.Series(dtype=float)
    pc = pc.reindex(pc.index.union(old_p.index))
    pc["P"] = pc["P"].astype(float).fillna(0) + old_p.reindex(pc.index).fillna(0)
    pc["STR"] = pc["STR"].astype(float).fillna(0) + old_str.reindex(pc.index).fillna(0)
    out["P"] = [float(pc["P"].get(n)) if n in pc.index else (0.0 if has_live.get(n, False) else np.nan) for n in out.index]
    out["STR"] = [float(pc["STR"].get(n)) if n in pc.index else (0.0 if has_live.get(n, False) else np.nan) for n in out.index]
    out["STR%"] = _div(out["STR"], out["P"])
    return out[cols]


def fielding(fl, names=None):
    """Errors and throw-outs per player (live games only)."""
    cols = ["E", "TO"] + [f"TO {lab}" for lab in HOW_LABELS.values()]
    if fl.empty:
        out = pd.DataFrame(columns=cols, dtype=float)
    else:
        out = pd.DataFrame(index=sorted(fl["player"].dropna().unique()))
        out["E"] = fl[fl.kind == "E"].groupby("player").size()
        out["TO"] = fl[fl.kind == "TO"].groupby("player").size()
        for code, lab in HOW_LABELS.items():
            out[f"TO {lab}"] = fl[(fl.kind == "TO") & (fl.how == code)].groupby("player").size()
        out = out.fillna(0).astype(float)
    if names is not None:
        out = out.reindex(sorted(set(out.index) | set(names))).fillna(0)
    return out[cols]


def split_players(value):
    return [p.strip() for p in str(value or "").split(",") if p.strip()]


def all_time_hitter(game_row):
    setup = game_row.get("setup") if hasattr(game_row, "get") else None
    allt = (setup or {}).get("all_time") if isinstance(setup, dict) else None
    return allt["name"] if allt and allt.get("role") == "hitter" else None


def all_time_player(game_row):
    """The game's all-time player (hitter or pitcher), who plays for both teams, or None."""
    setup = game_row.get("setup") if hasattr(game_row, "get") else None
    allt = (setup or {}).get("all_time") if isinstance(setup, dict) else None
    return allt["name"] if allt and allt.get("name") else None


def team_of(game_row, player):
    """1 or 2 for the player's team in that game, or None (not in it, or the all-time hitter)."""
    if player in split_players(game_row["team1_players"]):
        return 1
    if player in split_players(game_row["team2_players"]):
        return 2
    return None


def records(games):
    """W-D-L per player over the given completed games. A draw is half a win.
    The all-time player's games (hitter or pitcher) count in 'Both', not in W/D/L."""
    rec = {}
    for _, g in games.iterrows():
        s1, s2 = g["team1_score"], g["team2_score"]
        if pd.isna(s1) or pd.isna(s2):
            continue
        t1, t2 = split_players(g["team1_players"]), split_players(g["team2_players"])
        if s1 > s2:
            outcomes = [(t1, "W"), (t2, "L")]
        elif s2 > s1:
            outcomes = [(t2, "W"), (t1, "L")]
        else:
            outcomes = [(t1 + t2, "D")]
        for team, res in outcomes:
            for p in team:
                rec.setdefault(p, {"W": 0, "D": 0, "L": 0, "Both": 0})[res] += 1
        shared = all_time_player(g)
        if shared:
            rec.setdefault(shared, {"W": 0, "D": 0, "L": 0, "Both": 0})["Both"] += 1
    out = pd.DataFrame.from_dict(rec, orient="index", columns=["W", "D", "L", "Both"]).fillna(0)
    if out.empty:
        return pd.DataFrame(columns=["W", "D", "L", "Both", "GP", "Pct"])
    out["GP"] = out["W"] + out["D"] + out["L"]
    out["Pct"] = _div(out["W"] + 0.5 * out["D"], out["GP"])
    return out


def ip_text(outs):
    """Baseball innings notation from outs: 47 outs -> '15.2'."""
    outs = int(outs or 0)
    return f"{outs // 3}.{outs % 3}"


# ------------------------------------------------------------------ WAR (wins above replacement)
# Each part is first measured in runs vs. the league-average player (0 = average), then a replacement
# credit is added so 0.0 means "a fill-in player" and regulars build up value as they play, like MLB WAR.
#
#   Batting runs   linear weights (MLB wOBA weights), vs. the league rate per PA, / wOBA scale
#   Pitching runs  "fip":   FIP, scaled so league FIP = league ERA (fWAR-style, what the pitcher controls)
#                  "ra":    ERA (bWAR-style, runs actually allowed)
#                  "blend": the default WAR. Mixes the two by how trustworthy each pitcher's run data is:
#                           runs-allowed share = 1/2 x (share of his innings from live-scored games),
#                           so old-games-only = 100% FIP and all-live = 50/50. Re-centered so the
#                           league still sums to zero.
#                  either way: (league ERA - pitcher's) / 9 * IP
#   Fielding runs  throw-outs (+0.3 runs) and errors (-0.5 runs) vs. the league rate per game (live games)
#   Replacement    REPLACEMENT_WAR_PER_GAME for a typical game played, half earned through plate appearances
#                  and half through innings pitched (so a player who only bats gets the batting half).
#                  At 0.07, a team of replacement players would win about 25% of its games.
#   Runs per win   league runs per game (both teams); low-scoring games make each run worth more
#
# Seasons: each season (calendar year) is measured against that season's own league average and runs per
# win. Career WAR is the sum of a player's seasons, the way Baseball Reference and FanGraphs do it.

REPLACEMENT_WAR_PER_GAME = 0.07      # change this one number to make replacement level stricter or looser

WOBA_WEIGHTS = {"BB": 0.69, "1B": 0.89, "2B": 1.27, "3B": 1.62, "HR": 2.10}
WOBA_SCALE = 1.2
FIP_WEIGHTS = {"HR": 13, "BB": 3, "K": -2}
THROW_OUT_RUNS = 0.3
ERROR_RUNS = 0.5


def live_games_played(lg):
    """Live games each player was in (lineup or pitching rotation)."""
    count = {}
    for setup in lg.games.loc[lg.games["mode"] == "live", "setup"]:
        if isinstance(setup, dict):
            names = set()
            for group in ("lineups", "rotations"):
                for lst in (setup.get(group) or {}).values():
                    names.update(lst)
            for n in names:
                count[n] = count.get(n, 0) + 1
    return pd.Series(count, dtype=float)


def runs_per_win(lg):
    done = lg.completed
    if done.empty:
        return 10.0
    rpg = (done["team1_score"].sum() + done["team2_score"].sum()) / len(done)
    return float(max(rpg, 3.0))      # floor so a couple of 1-0 games can't blow it up


def runs_allowed_share(lg):
    """Per pitcher: how much of the blended pitching runs comes from runs allowed (0 to 0.5)."""
    if lg.pa.empty:
        return pd.Series(dtype=float)
    total = lg.pitcher_outs
    ro = lg.runner_outs.groupby("pitcher").size() if not lg.runner_outs.empty else pd.Series(dtype=float)
    live = (lg.pa[lg.pa["live"]].groupby("pitcher")["outs"].sum().add(ro, fill_value=0)
            .reindex(total.index).fillna(0))
    return pd.Series(0.5 * _div(live, total), index=total.index).fillna(0)


def games_played(lg):
    """Games each player was in (any game: team lists for older games, lineups/rotations for live ones)."""
    count = {}
    for g in lg.games.itertuples(index=False):
        names = set(split_players(g.team1_players)) | set(split_players(g.team2_players))
        if isinstance(g.setup, dict):
            for group in ("lineups", "rotations"):
                for lst in (g.setup.get(group) or {}).values():
                    names.update(lst)
        for n in names:
            count[n] = count.get(n, 0) + 1
    return pd.Series(count, dtype=float)


def seasons(lg):
    """Seasons (years) with games, newest first."""
    return sorted(lg.games["date"].dt.year.dropna().astype(int).unique(), reverse=True)


WAR_COLS = ["Batting runs", "Pitching runs", "Fielding runs", "Replacement runs", "Runs", "WAA", "WAR",
            "PA", "IP", "G", "Live G"]


def _war_one(lg, pitching_method):
    """WAR for one block of games (a season), measured against that block's league."""
    names = lg.names
    if lg.pa.empty:
        return pd.DataFrame(0.0, index=names, columns=WAR_COLS)

    # Batting
    b = lg.batting()
    lw = sum(b[k] * w for k, w in WOBA_WEIGHTS.items())
    lg_rate = lw.sum() / b["PA"].sum() if b["PA"].sum() else 0
    bat_runs = (lw - lg_rate * b["PA"]) / WOBA_SCALE

    # Pitching
    p = lg.pitching()
    ip = p["IP"]
    lg_ip = ip.sum()
    lg_era = p["ER"].sum() * 9 / lg_ip if lg_ip else 0
    # Written as "runs an average pitcher allows in these innings minus this pitcher's runs", which
    # equals (lgERA - ERA or FIP) / 9 * IP but still charges a pitcher who gave up runs without an out.
    expected = lg_era * ip / 9
    core = sum(p[k] * w for k, w in FIP_WEIGHTS.items())
    const = lg_era - (core.sum() / lg_ip if lg_ip else 0)
    fip_runs = expected - (core + const * ip) / 9
    ra_runs = expected - p["ER"]
    if pitching_method == "fip":
        pit_runs = fip_runs
    elif pitching_method == "ra":
        pit_runs = ra_runs
    else:
        ra_share = runs_allowed_share(lg).reindex(p.index).fillna(0)
        pit_runs = (1 - ra_share) * fip_runs + ra_share * ra_runs
        if lg_ip:   # keep the league total at zero (average = 0.0)
            pit_runs = pit_runs - pit_runs.sum() * ip / lg_ip

    # Fielding (live games only)
    f = fielding(lg.fielding)
    g_live = live_games_played(lg)
    total_g = g_live.sum()
    to_pg = f["TO"].sum() / total_g if total_g else 0
    e_pg = f["E"].sum() / total_g if total_g else 0
    f = f.reindex(g_live.index).fillna(0)
    fld_runs = THROW_OUT_RUNS * (f["TO"] - to_pg * g_live) - ERROR_RUNS * (f["E"] - e_pg * g_live)

    gp = games_played(lg)
    everyone = sorted(set(names) | set(b.index) | set(p.index) | set(g_live.index) | set(gp.index))
    rpw = runs_per_win(lg)
    out = pd.DataFrame(index=everyone)
    out["Batting runs"] = bat_runs.reindex(everyone).fillna(0)
    out["Pitching runs"] = pit_runs.reindex(everyone).fillna(0)
    out["Fielding runs"] = fld_runs.reindex(everyone).fillna(0)
    out["PA"] = b["PA"].reindex(everyone).fillna(0)
    out["IP"] = ip.reindex(everyone).fillna(0)
    out["G"] = gp.reindex(everyone).fillna(0)
    out["Live G"] = g_live.reindex(everyone).fillna(0)

    # Replacement: half the credit per "typical game" of plate appearances, half per typical game of innings
    player_games = out["G"].sum()
    credit_runs = REPLACEMENT_WAR_PER_GAME * rpw
    pa_per_game = out["PA"].sum() / player_games if player_games else 0
    ip_per_game = out["IP"].sum() / player_games if player_games else 0
    rep = 0.0
    if pa_per_game:
        rep = rep + 0.5 * credit_runs * out["PA"] / pa_per_game
    if ip_per_game:
        rep = rep + 0.5 * credit_runs * out["IP"] / ip_per_game
    out["Replacement runs"] = rep

    out["Runs"] = out[["Batting runs", "Pitching runs", "Fielding runs"]].sum(axis=1)
    out["WAA"] = out["Runs"] / rpw                         # wins above average
    out["WAR"] = (out["Runs"] + out["Replacement runs"]) / rpw
    return out[WAR_COLS]


def season_league(lg, year):
    """The same League restricted to one season's games (no replays needed)."""
    return games_league(lg, lg.games.loc[lg.games["date"].dt.year == year, "game_id"])


def games_league(lg, game_ids):
    """The same League restricted to some games (no replays needed)."""
    sub = copy.copy(lg)
    ids = set(game_ids)
    sub.games = lg.games[lg.games["game_id"].isin(ids)]
    for name in ("pa", "runs", "pitches", "fielding", "runner_outs", "scoring"):
        t = getattr(lg, name)
        setattr(sub, name, t[t["game_id"].isin(ids)])
    return sub


def war_by_season(lg, pitching_method="blend"):
    """One row per player per season (column 'Season'), each season against its own league."""
    rows = []
    for year in seasons(lg):
        w = _war_one(season_league(lg, year), pitching_method)
        w = w[(w["G"] > 0) | (w["PA"] > 0) | (w["IP"] > 0)]
        rows.append(w.assign(Season=year))
    if not rows:
        return pd.DataFrame(columns=WAR_COLS + ["Season"])
    return pd.concat(rows)


def war(lg, pitching_method="blend", season=None):
    """WAR and its parts per player.

    season=None: career (the sum of every season). season=2026: that season only.
    pitching_method: 'blend' (default), 'fip' (fWAR-style) or 'ra' (bWAR-style)."""
    if season is not None:
        return _war_one(season_league(lg, season), pitching_method)
    by = war_by_season(lg, pitching_method)
    names = lg.names
    if by.empty:
        return pd.DataFrame(0.0, index=names, columns=WAR_COLS)
    out = by.drop(columns="Season").groupby(level=0).sum()
    return out.reindex(sorted(set(names) | set(out.index))).fillna(0)[WAR_COLS]


# ------------------------------------------------------------------ chart data (Visualizations page)

def war_race(lg):
    """Cumulative WAR after each completed game, oldest first.

    Returns (games, values): games has match_no / game_id / date per step; values has one column per
    player (NaN before his first game). Each step is the real WAR of the games played so far, so the
    league baseline moves as games are added, like a season-to-date leaderboard."""
    done = lg.completed.sort_values("game_order")
    ids, steps = [], []
    for gid in done["game_id"]:
        ids.append(gid)
        w = war(games_league(lg, ids))
        steps.append(w["WAR"].where(w["G"] > 0))
    if not steps:
        return done[["game_id", "date"]].assign(n=[]), pd.DataFrame()
    values = pd.DataFrame(steps).reset_index(drop=True)
    games = done[["game_id", "date", "match_no"]].reset_index(drop=True).assign(n=range(1, len(done) + 1))
    return games, values.dropna(axis=1, how="all")


OUTCOME_GROUPS = [   # (label, outcome codes), in the order the outcome-mix bar is drawn
    ("Strikeout", {"K"}),
    ("In play, no hit", {"GO", "PO", "LO", "SF", "DP", "TP", "FC", "E"}),
    ("Walk", {"BB"}),
    ("Single", {"1B"}),
    ("Double", {"2B"}),
    ("Triple", {"3B"}),
    ("Home run", {"HR"}),
]


def outcome_mix(pa, by="batter"):
    """Share of each hitter's plate appearances by result group (rows sum to 1), plus PA.
    by="pitcher": the same, for the batters each pitcher faced."""
    pa = pa.dropna(subset=[by])
    out = pd.DataFrame(index=sorted(pa[by].unique()))
    for label, codes in OUTCOME_GROUPS:
        out[label] = pa[pa["outcome"].isin(codes)].groupby(by).size()
    out = out.fillna(0)
    out["PA"] = out.sum(axis=1)
    shares = out.drop(columns="PA").div(out["PA"].where(out["PA"] > 0), axis=0)
    return shares.assign(PA=out["PA"])


def runner_splits(pa, by="batter"):
    """Hitting with runners on base vs. bases empty: OBP/SLG/OPS and PA for each side.
    Plate appearances with no runner info (if any) are left out."""
    pa = pa.dropna(subset=["runners_on"])
    on = batting(pa[pa["runners_on"].astype(float) > 0], by=by)
    empty = batting(pa[pa["runners_on"].astype(float) == 0], by=by)
    cols = ["PA", "OBP", "SLG", "OPS"]
    return on[cols].add_suffix(" on").join(empty[cols].add_suffix(" empty"), how="outer")


def matchup_grid(pa, stat="OBP"):
    """Batter x pitcher table of one hitting stat, and the PA behind each cell."""
    values, counts = {}, {}
    for pitcher, g in pa.dropna(subset=["pitcher", "batter"]).groupby("pitcher"):
        b = batting(g)
        values[pitcher], counts[pitcher] = b[stat], b["PA"]
    return pd.DataFrame(values), pd.DataFrame(counts)


def teammate_records(games):
    """Record of every pair of players when on the SAME team, from completed games.
    A draw is half a win. Returns a long table: a, b, GP, W, D, L, Pct (a < b alphabetically)."""
    rec = {}
    for _, g in games.iterrows():
        s1, s2 = g["team1_score"], g["team2_score"]
        if pd.isna(s1) or pd.isna(s2):
            continue
        for team, mine, theirs in ((split_players(g["team1_players"]), s1, s2),
                                   (split_players(g["team2_players"]), s2, s1)):
            res = "W" if mine > theirs else "L" if mine < theirs else "D"
            for i, a in enumerate(sorted(set(team))):
                for b in sorted(set(team))[i + 1:]:
                    r = rec.setdefault((a, b), {"W": 0, "D": 0, "L": 0})
                    r[res] += 1
    rows = [{"a": a, "b": b, **r} for (a, b), r in rec.items()]
    out = pd.DataFrame(rows, columns=["a", "b", "W", "D", "L"])
    out["GP"] = out["W"] + out["D"] + out["L"]
    out["Pct"] = _div(out["W"] + 0.5 * out["D"], out["GP"])
    return out


def inning_number(label):
    """'Top 3' / 'Bottom 3' / 3 -> 3 (None if there's no number)."""
    if label is None or (isinstance(label, float) and np.isnan(label)):
        return None
    if isinstance(label, (int, np.integer)):
        return int(label)
    digits = "".join(ch for ch in str(label) if ch.isdigit())
    return int(digits) if digits else None


def inning_runs(lg):
    """Runs allowed per inning pitched, by pitcher and inning of the game.

    Live games: every run charged to the pitcher. Older games: RBIs allowed (the only run data they
    have, the same stand-in ERA uses). Returns (runs per inning, innings pitched), pitcher x inning."""
    pa = lg.pa.assign(inn=lg.pa["inning"].map(inning_number)).dropna(subset=["inn", "pitcher"])
    outs = pa.groupby(["pitcher", "inn"])["outs"].sum()
    ro = lg.runner_outs.assign(inn=lg.runner_outs["inning"].map(inning_number)).dropna(subset=["inn"])
    if not ro.empty:
        outs = outs.add(ro.groupby(["pitcher", "inn"]).size(), fill_value=0)
    old_runs = pa[pa["live"] != True].groupby(["pitcher", "inn"])["rbi"].sum()      # noqa: E712
    live = lg.runs.assign(inn=lg.runs["inning"].map(inning_number)).dropna(subset=["inn", "pitcher"])
    runs = old_runs.add(live.groupby(["pitcher", "inn"]).size(), fill_value=0) if not live.empty else old_runs
    ip = (outs / 3).unstack()
    runs = runs.reindex(outs.index).fillna(0).unstack()
    ip.columns = runs.columns = [int(c) for c in ip.columns]
    return pd.DataFrame(_div(runs, ip), index=ip.index, columns=ip.columns), ip


# ------------------------------------------------------------------ advanced (sabermetric) stats
# All of them are measured against the league in the same table, so a season view compares a player
# with that season's league, and the career view with everyone's career.
#
#   wOBA   weighted on-base average: each way of reaching base counted by its run value (the same MLB
#          weights WAR uses), (0.69 BB + 0.89 1B + 1.27 2B + 1.62 3B + 2.10 HR) / (AB + BB + SF)
#   wRC+   wOBA as "100 = league average": 100 x (runs created per PA / league runs per PA)
#   ISO    isolated power, SLG - AVG
#   BABIP  batting average on balls in play, (H - HR) / (AB - K - HR + SF)
#   FIP    fielding-independent pitching, (13 HR + 3 BB - 2 K) / IP + constant (league FIP = league ERA)
#   ERA-   100 x ERA / league ERA: 100 = average, lower is better (80 = 20% better than the league)
#   K-BB%  (K - BB) / batters faced
#   Opp OPS  OBP + SLG of the hitters a pitcher faced

def league_runs_per_pa(lg):
    """Runs per plate appearance across completed games (both teams), for wRC+."""
    done = lg.completed
    pa = lg.pa[lg.pa["game_id"].isin(done["game_id"])]
    runs = done["team1_score"].sum() + done["team2_score"].sum()
    return float(runs / len(pa)) if len(pa) else float("nan")


def advanced_batting(bat, runs_per_pa):
    out = bat.copy()
    if out.empty:
        for c in ("wOBA", "wRC+", "ISO", "BABIP"):
            out[c] = pd.Series(dtype=float)
        return out
    weighted = sum(out[k] * w for k, w in WOBA_WEIGHTS.items())
    denom = out["AB"] + out["BB"] + out["SF"]
    out["wOBA"] = _div(weighted, denom)
    lg_woba = weighted.sum() / denom.sum() if denom.sum() else np.nan
    # runs above average per PA, plus the league's runs per PA, relative to the league's runs per PA
    out["wRC+"] = _div(((out["wOBA"] - lg_woba) / WOBA_SCALE + runs_per_pa) * 100, runs_per_pa)
    out["ISO"] = out["SLG"] - out["AVG"]
    out["BABIP"] = _div(out["H"] - out["HR"], out["AB"] - out["K"] - out["HR"] + out["SF"])
    return out


def advanced_pitching(pit, pa):
    out = pit.copy()
    if out.empty:
        for c in ("FIP", "ERA-", "K-BB%", "OPP_OPS"):
            out[c] = pd.Series(dtype=float)
        return out
    core = sum(out[k] * w for k, w in FIP_WEIGHTS.items())
    lg_ip = out["IP"].sum()
    lg_era = out["ER"].sum() * 9 / lg_ip if lg_ip else np.nan
    const = lg_era - (core.sum() / lg_ip if lg_ip else np.nan)
    out["FIP"] = _div(core, out["IP"]) + const
    out["ERA-"] = _div(out["ERA"] * 100, pd.Series(lg_era, index=out.index))
    out["K-BB%"] = _div(out["K"] - out["BB"], out["BF"])
    opp = batting(pa, by="pitcher")
    out["OPP_OPS"] = opp["OPS"].reindex(out.index)
    return out


# ------------------------------------------------------------------ awards and records (Awards page)
AWARD_MIN_PA = 15        # Hitter of the Year: at least this many plate appearances in the season


def _top(series, n=3, low=False):
    s = series.dropna().sort_values(ascending=low)
    return list(s.head(n).items())


def season_awards(lg, year):
    """{award: [(name, value), ...]} top three for one season. Gold Glove needs live fielding data, and
    Most Improved needs a previous season to compare with; either is left out when it can't be decided."""
    w = war(lg, season=year)
    w = w[w["G"] > 0]
    bat = season_league(lg, year).advanced_batting()
    out = {
        "MVP": _top(w["WAR"]),
        "Pitcher": _top(w.loc[w["IP"] > 0, "Pitching runs"]),
        "Hitter": _top(bat.loc[bat["PA"] >= AWARD_MIN_PA, "wRC+"]),
    }
    live_f = w.loc[w["Live G"] > 0, "Fielding runs"]
    if (live_f.abs() > 0.05).any():
        out["Glove"] = _top(live_f)
    earlier = [y for y in seasons(lg) if y < year]
    if earlier:
        wp = war(lg, season=earlier[0])
        both = w.index.intersection(wp[wp["G"] > 0].index)
        if len(both):
            out["Improved"] = _top(w.loc[both, "WAR"] - wp.loc[both, "WAR"])
            out["_improved_from"] = earlier[0]
    return {k: v for k, v in out.items() if v}


def _per_game(pa, who):
    """Batting (who='batter') or pitching (who='pitcher') lines per player per game."""
    pa = pa.dropna(subset=[who])
    if pa.empty:
        return pd.DataFrame()
    keyed = pa.assign(_key=pa["game_id"].astype(str) + "|" + pa[who].astype(str))
    t = batting(keyed, by="_key") if who == "batter" else pitching(keyed, by="_key")
    parts = t.index.to_series().str.split("|", n=1)
    return t.assign(game_id=parts.str[0].values, player=parts.str[1].values).reset_index(drop=True)


SINGLE_GAME = [  # (label, batting or pitching, column)
    ("Most hits", "batter", "H"), ("Most home runs", "batter", "HR"), ("Most RBI", "batter", "RBI"),
    ("Most walks", "batter", "BB"), ("Most strikeouts pitched", "pitcher", "K"),
    ("Most innings pitched", "pitcher", "OUTS"),
]


def single_game_records(lg):
    """[(label, column, [(player, game_id, value), ...ties]), ...]: the best single-game totals (ties all shown)."""
    tables = {"batter": _per_game(lg.pa, "batter"), "pitcher": _per_game(lg.pa, "pitcher")}
    out = []
    for label, who, col in SINGLE_GAME:
        t = tables[who]
        if t.empty or t[col].max() <= 0:
            continue
        best = t[col].max()
        rows = t[t[col] == best]
        out.append((label, col, [(r.player, r.game_id, float(best)) for r in rows.itertuples(index=False)]))
    return out


def hitting_streaks(lg):
    """[(longest, player, current), ...] best first. A streak counts games the player batted in with a hit,
    in game order; a game he didn't bat in doesn't break it."""
    per = _per_game(lg.pa, "batter")
    if per.empty:
        return []
    order = list(lg.games.sort_values("game_order")["game_id"])
    out = []
    for name, g in per.groupby("player"):
        hits = dict(zip(g["game_id"], g["H"]))
        run = longest = 0
        for gid in order:
            if gid in hits:
                run = run + 1 if hits[gid] > 0 else 0
                longest = max(longest, run)
        out.append((longest, name, run))
    return sorted(out, key=lambda x: (-x[0], -x[2], x[1]))


MILESTONES = {"HR": [5, 10, 25, 50, 100], "H": [25, 50, 100, 250], "RBI": [25, 50, 100, 250], "WAR": [1, 2, 5, 10, 20]}


def milestones(lg, n=5):
    """Players closest to their next round-number career total: [(player, stat, current, goal), ...]."""
    bat = lg.batting()
    w = war(lg)
    found = []
    for stat, steps in MILESTONES.items():
        values = w["WAR"] if stat == "WAR" else bat[stat]
        for name, v in values.dropna().items():
            goal = next((s for s in steps if s > v), None)
            if goal is None or v <= 0:
                continue
            found.append((1 - v / goal, name, stat, float(v), goal))   # how far there is left, as a share
    found.sort()
    return [(name, stat, v, goal) for _, name, stat, v, goal in found[:n]]