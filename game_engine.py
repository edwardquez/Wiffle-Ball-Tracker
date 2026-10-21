"""Live game engine for the Scorekeeper.

The whole game state (inning, outs, bases, score, count, batter, pitcher, earned runs)
is rebuilt by replaying a game's setup plus its list of recorded events in order.
Nothing about the live state is stored separately, so undo is just "drop the last event".

This module has no Streamlit or MongoDB code, so it can be tested on its own.

Setup (dict):
    lineups        {1: [names in batting order], 2: [...]}   Team 1 bats in the top half
    rotations      {1: [Team 1 pitchers], 2: [Team 2 pitchers]}  (a team pitches while the other bats)
    outs_per_half  2 or 3
    all_time       optional {"name": ..., "role": "hitter" | "pitcher"}

Events (dicts, in the order they happened):
    {"type": "pitch", "result": "B" | "S" | "F"}
    {"type": "play", "outcome": "1B", "dest": {...}, "error_fielder": None, "rbi": None}
        outcome: 1B 2B 3B HR GO PO LO FC SF DP TP E
        dest: optional overrides of where each runner ended up, keyed by where they started:
              "B" (the batter), 1, 2, 3  ->  1, 2, 3, "H" (scored) or "out"
        outs_detail: optional, for anyone in dest set to "out": {"B" | 1 | 2 | 3: {"how": ..., "by": name}}
              how: "throw" | "runner" (hit with the ball) | "sign" (sign hit before he scored) | "tag"
    {"type": "runner", "kind": "SB" | "CS" | "PO", "base": 1, "to": 2, "how": None, "by": None}
        steal / caught stealing / pickoff (how/by optional, for CS and PO)
    {"type": "pitcher", "name": "Vera"}           change the current pitcher (reliever)
    {"type": "outs", "value": 2}                  outs per half, from the next half-inning on
    {"type": "last_inning", "inning": 6}          None clears it
    {"type": "continue", "one_inning": True}      tied after the last inning: play another inning, which
                                                  becomes the new last inning (walk-off and tie rules apply
                                                  again). Without one_inning (games saved before this was
                                                  added) the game goes on with no last inning set.
    {"type": "end"}                               end the game now (a tie is a draw)
"""

from dataclasses import dataclass, field
from copy import deepcopy

HITS = {"1B": 1, "2B": 2, "3B": 3, "HR": 4}
BATTER_OUT = {"K", "GO", "PO", "LO", "SF", "DP", "TP"}
OUTCOMES = set(HITS) | BATTER_OUT | {"BB", "FC", "E"}
NO_RBI = {"E", "DP", "TP"}
# How an out was made, when the scorekeeper records it (optional): a normal throw to a base,
# hitting the runner with the ball, hitting the metal strike-zone sign before he scores, or a tag.
OUT_HOW = {"throw", "runner", "sign", "tag"}


class GameError(ValueError):
    """An event that can't happen in the current state (the UI should prevent these)."""


@dataclass
class Runner:
    name: str
    pitcher: str            # pitcher responsible if this runner scores
    on_error: bool = False  # reached on an error -> scoring is unearned
    ghost: bool = False     # the player is batting again; a ghost holds their base


@dataclass
class State:
    setup: dict
    inning: int = 1
    half: str = "top"                     # "top" (Team 1 bats) or "bottom" (Team 2 bats)
    outs: int = 0
    outs_limit: int = 3
    pending_outs_limit: int = None
    phantom_outs: int = 0                 # outs + reached-on-error, for earned runs
    bases: dict = field(default_factory=lambda: {1: None, 2: None, 3: None})
    score: dict = field(default_factory=lambda: {1: 0, 2: 0})
    order_idx: dict = field(default_factory=lambda: {1: 0, 2: 0})
    rotation_idx: dict = field(default_factory=lambda: {1: 0, 2: 0})
    pitcher: str = None                   # current pitcher for the fielding team
    balls: int = 0
    strikes: int = 0
    pa_pitches: str = ""
    last_inning: int = None
    status: str = "live"                  # live | tied (decision needed) | final
    result: str = None                    # "1" | "2" | "draw" when final
    walk_off: bool = False
    plate_appearances: list = field(default_factory=list)
    runner_events: list = field(default_factory=list)
    pitch_log: list = field(default_factory=list)       # (pitcher, batter, result)
    line: dict = field(default_factory=lambda: {1: [], 2: []})   # runs per inning
    hits: dict = field(default_factory=lambda: {1: 0, 2: 0})
    errors: dict = field(default_factory=lambda: {1: 0, 2: 0})   # errors committed BY the team
    half_log: list = field(default_factory=list)        # summary of each finished half-inning
    _half_runs: int = 0
    _half_hits: int = 0
    _half_errors: int = 0
    _half_pitches: int = 0
    _seq: int = 0                         # order of plate appearances and runner events

    # ---- who's up ----
    @property
    def batting_team(self):
        return 1 if self.half == "top" else 2

    @property
    def fielding_team(self):
        return 2 if self.half == "top" else 1

    @property
    def batter(self):
        lineup = self.setup["lineups"][self.batting_team]
        return lineup[self.order_idx[self.batting_team] % len(lineup)]

    @property
    def on_deck(self):
        lineup = self.setup["lineups"][self.batting_team]
        return lineup[(self.order_idx[self.batting_team] + 1) % len(lineup)]

    def runners(self):
        return {b: r for b, r in self.bases.items() if r is not None}


# ------------------------------------------------------------------ setup checks

def validate_setup(setup):
    lineups, rotations = setup["lineups"], setup["rotations"]
    for t in (1, 2):
        if not lineups.get(t):
            raise GameError(f"Team {t} needs at least one batter.")
        if not rotations.get(t):
            raise GameError(f"Team {t} needs at least one pitcher.")
        if len(set(lineups[t])) != len(lineups[t]):
            raise GameError(f"Team {t} has a player listed twice in the batting order.")
    if setup.get("outs_per_half", 3) not in (2, 3):
        raise GameError("Outs per half-inning must be 2 or 3.")

    shared = (setup.get("all_time") or {}).get("name")
    role = (setup.get("all_time") or {}).get("role")
    both = set(lineups[1]) & set(lineups[2])
    if both - ({shared} if role == "hitter" else set()):
        raise GameError(f"{', '.join(sorted(both))} can't bat for both teams unless they're the all-time hitter.")
    for t in (1, 2):
        other = 2 if t == 1 else 1
        clash = set(rotations[t]) & set(lineups[other])
        if clash:
            raise GameError(f"{', '.join(sorted(clash))} can't pitch for Team {t} and bat for Team {other}.")
    if role == "hitter" and (shared in rotations[1] or shared in rotations[2]):
        raise GameError(f"{shared} is the all-time hitter, so he can't pitch.")


# ------------------------------------------------------------------ helpers

def _forced(bases):
    """Which occupied bases are forced to move if the batter goes to first."""
    f = set()
    if bases[1]:
        f.add(1)
        if bases[2]:
            f.add(2)
            if bases[3]:
                f.add(3)
    return f


def _advance(base, n):
    to = base + n
    return "H" if to >= 4 else to


def default_dest(state, outcome):
    """The usual result of a play: where the batter ("B") and each runner (1, 2, 3) end up.
    The live screen shows this as the pre-filled answer the scorekeeper confirms or changes."""
    occ = [b for b in (1, 2, 3) if state.bases[b]]
    forced = _forced(state.bases)
    dest = {}

    if outcome in HITS:
        n = HITS[outcome]
        dest["B"] = _advance(0, n)
        for b in occ:
            dest[b] = _advance(b, n)
    elif outcome == "E":
        dest["B"] = 1
        for b in occ:
            dest[b] = _advance(b, 1)
    elif outcome == "BB":
        dest["B"] = 1
        for b in occ:
            dest[b] = _advance(b, 1) if b in forced else b
    elif outcome in ("K", "PO", "LO"):
        dest["B"] = "out"
        for b in occ:
            dest[b] = b
    elif outcome == "GO":
        dest["B"] = "out"
        for b in occ:
            dest[b] = _advance(b, 1) if b in forced else b
    elif outcome == "SF":
        dest["B"] = "out"
        for b in occ:
            dest[b] = "H" if b == 3 else b
    elif outcome == "FC":
        if not occ:
            raise GameError("A fielder's choice needs a runner on base.")
        dest["B"] = 1
        lead = max(forced) if forced else max(occ)
        for b in occ:
            if b == lead:
                dest[b] = "out"
            else:
                dest[b] = _advance(b, 1) if b in forced else b
    elif outcome == "DP":
        if not occ:
            raise GameError("A double play needs a runner on base.")
        dest["B"] = "out"
        out_runner = 1 if 1 in occ else max(occ)
        for b in occ:
            if b == out_runner:
                dest[b] = "out"
            else:
                dest[b] = _advance(b, 1) if b in forced else b
    elif outcome == "TP":
        if len(occ) < 2:
            raise GameError("A triple play needs at least two runners on base.")
        dest["B"] = "out"
        outs = sorted(occ)[:2]
        for b in occ:
            dest[b] = "out" if b in outs else b
    else:
        raise GameError(f"Unknown outcome {outcome}.")
    return dest


def _check_dest(state, dest):
    taken = {}
    for who, to in dest.items():
        if who != "B" and not state.bases.get(who):
            raise GameError(f"There's no runner on base {who}.")
        if to in (1, 2, 3):
            if to in taken:
                raise GameError(f"Two runners can't both end up on base {to}.")
            if who != "B" and to < who:
                raise GameError("Runners can't move backwards.")
            taken[to] = who
        elif to not in ("H", "out"):
            raise GameError(f"Unknown destination {to}.")
    # Runners who stay in the play can't pass each other (home counts as base 4; several can score).
    staying = sorted((0 if who == "B" else who, 4 if to == "H" else to)
                     for who, to in dest.items() if to != "out")
    for (_, a), (_, b) in zip(staying, staying[1:]):
        if a > b or (a == b != 4):
            raise GameError("A runner can't pass the runner ahead of him.")


def _score_run(state, runner, earned, play_ref):
    state.score[state.batting_team] += 1
    state._half_runs += 1
    run = {"player": runner.name, "ghost": runner.ghost, "earned": earned, "pitcher": runner.pitcher}
    play_ref.setdefault("runs", []).append(run)
    return run


# ------------------------------------------------------------------ half-inning flow

def _start_half(state):
    if state.pending_outs_limit:
        state.outs_limit = state.pending_outs_limit
        state.pending_outs_limit = None
    state.outs = 0
    state.phantom_outs = 0
    state.bases = {1: None, 2: None, 3: None}
    state._half_runs = state._half_hits = state._half_errors = state._half_pitches = 0
    team = state.fielding_team
    rot = state.setup["rotations"][team]
    state.pitcher = rot[state.rotation_idx[team] % len(rot)]
    state.rotation_idx[team] += 1
    state.line[state.batting_team].append(0)
    state.balls = state.strikes = 0
    state.pa_pitches = ""


def _end_half(state):
    lob = len(state.runners())
    state.half_log.append({
        "inning": state.inning, "half": state.half, "team": state.batting_team,
        "runs": state._half_runs, "hits": state._half_hits, "errors": state._half_errors,
        "lob": lob, "pitches": state._half_pitches,
    })
    li = state.last_inning
    final_inning = li is not None and state.inning >= li

    if state.half == "top":
        if final_inning and state.score[2] > state.score[1]:
            _finish(state)       # home team already ahead: bottom half isn't played
            return
        state.half = "bottom"
    else:
        if final_inning:
            if state.score[1] != state.score[2]:
                _finish(state)
            else:
                state.status = "tied"   # ask: draw or another inning (see "continue")
            return
        state.half, state.inning = "top", state.inning + 1
    _start_half(state)


def _finish(state):
    state.status = "final"
    if state.score[1] > state.score[2]:
        state.result = "1"
    elif state.score[2] > state.score[1]:
        state.result = "2"
    else:
        state.result = "draw"


def _check_walk_off(state):
    li = state.last_inning
    if (state.status == "live" and state.half == "bottom" and li is not None
            and state.inning >= li and state.score[2] > state.score[1]):
        state.walk_off = True
        _finish(state)
        return True
    return False


def _after_outs(state):
    if state.outs >= state.outs_limit:
        _end_half(state)


def _prepare_batter(state):
    """A batter coming up who is already on base leaves a ghost runner there."""
    for r in state.runners().values():
        if r.name == state.batter and not r.ghost:
            r.ghost = True


# ------------------------------------------------------------------ events

def _pitch(state, result):
    if result not in ("B", "S", "F"):
        raise GameError(f"Unknown pitch {result}.")
    _prepare_batter(state)
    state.pitch_log.append((state.pitcher, state.batter, result))
    state._half_pitches += 1
    state.pa_pitches += result
    if result == "B":
        state.balls += 1
        if state.balls >= 4:
            _play(state, "BB", None, None, None, from_pitch=True)
    elif result == "S":
        state.strikes += 1
        if state.strikes >= 3:
            _play(state, "K", None, None, None, from_pitch=True)
    else:  # foul: a strike, except with two strikes
        if state.strikes < 2:
            state.strikes += 1


def _check_how(how):
    if how is not None and how not in OUT_HOW:
        raise GameError(f"Unknown way of making an out: {how}.")


def _play(state, outcome, dest_over, error_fielder, rbi_over, from_pitch=False, outs_detail=None):
    if outcome not in OUTCOMES:
        raise GameError(f"Unknown outcome {outcome}.")
    if outcome in ("BB", "K") and not from_pitch:
        raise GameError("Walks and strikeouts come from the pitch buttons.")
    _prepare_batter(state)
    if not from_pitch:
        state.pitch_log.append((state.pitcher, state.batter, "X"))
        state._half_pitches += 1
        state.pa_pitches += "X"

    dest = default_dest(state, outcome)
    for k, v in (dest_over or {}).items():
        key = "B" if k in ("B", "b") else int(k)
        dest[key] = v
    _check_dest(state, dest)

    details = []
    for k, d in (outs_detail or {}).items():
        key = "B" if k in ("B", "b") else int(k)
        if dest.get(key) != "out":
            raise GameError("Only players who were out can have how-they-were-out details.")
        d = d or {}
        _check_how(d.get("how"))
        if d.get("how") or d.get("by"):
            name = state.batter if key == "B" else state.bases[key].name
            details.append({"player": name, "from": key, "how": d.get("how"), "by": d.get("by")})

    team = state.batting_team
    outs_before = state.outs
    outs_on_play = sum(1 for v in dest.values() if v == "out")
    if outs_before + outs_on_play > state.outs_limit:
        raise GameError("That's more outs than are left in the half-inning.")
    ends_half = outs_before + outs_on_play >= state.outs_limit
    if outcome == "SF" and ends_half:
        raise GameError("A fly out for the last out isn't a sac fly; record it as a pop out.")

    batter_runner = Runner(state.batter, state.pitcher, on_error=(outcome == "E"))
    pa = {
        "inning": state.inning, "half": state.half, "team": team,
        "batter": state.batter, "pitcher": state.pitcher, "pitches": state.pa_pitches,
        "outcome": outcome, "outs_before": outs_before, "outs_on_play": outs_on_play,
        "bases_before": {b: (r.name if r else None) for b, r in state.bases.items()},
        "error_fielder": error_fielder, "runs": [], "out_details": details,
    }

    # Earned-run bookkeeping: once the inning "should" have ended (counting errors as outs),
    # every later run is unearned; runs scoring on a play with an error are unearned too.
    inning_should_be_over = state.phantom_outs >= state.outs_limit
    error_on_play = outcome == "E" or bool(error_fielder)

    old = dict(state.bases)
    new = {1: None, 2: None, 3: None}
    scorers = []
    for who in sorted([k for k in dest if k != "B"], reverse=True) + ["B"]:
        runner = batter_runner if who == "B" else old[who]
        to = dest[who]
        if to == "H":
            scorers.append(runner)
        elif to in (1, 2, 3):
            new[to] = runner
    state.bases = new
    state.outs += outs_on_play
    state.phantom_outs += outs_on_play + (1 if outcome == "E" else 0)

    # Runs don't count when the last out is a force or the batter's out on a ball in play.
    # On a hit or an error the batter reached, so a runner who crossed the plate before a
    # later out on the same play (a "time play") still scores.
    if not ends_half or outcome in HITS or outcome == "E":
        # Walk-off (bottom of the last inning): on anything but a home run, only the runs
        # up to the winning run count, like MLB. A walk-off homer counts every run.
        li = state.last_inning
        if (outcome != "HR" and state.half == "bottom" and li is not None and state.inning >= li):
            needed = state.score[1] - state.score[2] + 1
            if 0 < needed < len(scorers):
                scorers = scorers[:needed]
        for r in scorers:
            earned = not (r.on_error or inning_should_be_over or error_on_play)
            _score_run(state, r, earned, pa)
        state.line[team][-1] = state.line[team][-1] + len(scorers)

    if outcome in HITS:
        state.hits[team] += 1
        state._half_hits += 1
    if error_fielder or outcome == "E":
        state.errors[state.fielding_team] += 1
        state._half_errors += 1

    runs_here = len(pa["runs"])
    pa["rbi"] = rbi_over if rbi_over is not None else (0 if outcome in NO_RBI else runs_here)
    pa["bases_after"] = {b: (r.name if r else None) for b, r in state.bases.items()}
    state._seq += 1
    pa["n"] = state._seq
    state.plate_appearances.append(pa)

    # Next batter
    state.order_idx[team] += 1
    state.balls = state.strikes = 0
    state.pa_pitches = ""

    if _check_walk_off(state):
        return
    _after_outs(state)


def _runner_event(state, kind, base, to, how=None, by=None):
    runner = state.bases.get(base)
    if not runner:
        raise GameError(f"There's no runner on base {base}.")
    state._seq += 1
    rec = {"inning": state.inning, "half": state.half, "team": state.batting_team, "kind": kind,
           "runner": runner.name, "from": base, "pitcher": state.pitcher, "runs": [], "n": state._seq}
    if kind == "SB":
        to = to if to is not None else _advance(base, 1)
        to_num = 4 if to == "H" else to
        if to_num <= base or any(state.bases.get(b) for b in range(base + 1, min(to_num, 3) + 1)):
            raise GameError("That base isn't free.")
        state.bases[base] = None
        if to == "H":
            earned = not (runner.on_error or state.phantom_outs >= state.outs_limit)
            _score_run(state, runner, earned, rec)
            state.line[state.batting_team][-1] += 1
        else:
            state.bases[to] = runner
        rec["to"] = to
        state.runner_events.append(rec)
        _check_walk_off(state)
    elif kind in ("CS", "PO"):
        state.bases[base] = None
        state.outs += 1
        state.phantom_outs += 1
        _check_how(how)
        rec["to"] = "out"
        rec["how"], rec["by"] = how, by
        state.runner_events.append(rec)
        # The batter's turn isn't over: if this ends the half-inning, he leads off next time,
        # with a fresh count (his pitches still count for the pitcher).
        if state.outs >= state.outs_limit:
            state.balls = state.strikes = 0
            state.pa_pitches = ""
        _after_outs(state)
    else:
        raise GameError(f"Unknown runner event {kind}.")


def apply(state, event):
    t = event.get("type")
    if state.status == "final":
        raise GameError("The game is over.")
    if state.status == "tied" and t not in ("continue", "end"):
        raise GameError("Tied after the last inning: end it as a draw or play another inning.")

    if t == "pitch":
        _pitch(state, event["result"])
    elif t == "play":
        _play(state, event["outcome"], event.get("dest"), event.get("error_fielder"), event.get("rbi"),
              outs_detail=event.get("outs_detail"))
    elif t == "runner":
        _runner_event(state, event["kind"], int(event["base"]), event.get("to"), event.get("how"), event.get("by"))
    elif t == "pitcher":
        if event["name"] in state.setup["lineups"][state.batting_team]:
            raise GameError(f"{event['name']} is batting for the other team.")
        state.pitcher = event["name"]
    elif t == "outs":
        if event["value"] not in (2, 3):
            raise GameError("Outs per half-inning must be 2 or 3.")
        state.pending_outs_limit = event["value"]
    elif t == "last_inning":
        state.last_inning = event.get("inning")
        if _check_walk_off(state):
            state.walk_off = False   # ended by the setting, not by a play
    elif t == "continue":
        if state.status != "tied":
            raise GameError("Nothing to continue.")
        state.status = "live"
        state.last_inning = state.inning + 1 if event.get("one_inning") else None
        state.half, state.inning = "top", state.inning + 1
        _start_half(state)
    elif t == "end":
        _finish(state)
    else:
        raise GameError(f"Unknown event {t}.")
    return state


def replay(setup, events):
    """Rebuild the game from its setup and every event so far."""
    setup = deepcopy(setup)
    setup["lineups"] = {int(k): v for k, v in setup["lineups"].items()}
    setup["rotations"] = {int(k): v for k, v in setup["rotations"].items()}
    validate_setup(setup)
    state = State(setup=setup, outs_limit=setup.get("outs_per_half", 3))
    _start_half(state)
    for e in events:
        apply(state, e)
    return state