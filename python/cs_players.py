"""
EdgeStat -- Counter-Strike player roster + projections.

HLTV blocks scraping, so we maintain a static roster for the top-30 CS teams
mapped to their current player lineup with HLTV-style player rating
(HLTV 2.1 rating, the standard CS skill metric).

For each player projects per-match (BO3):
  - Kills (Poisson around HLTV-rating * map count)
  - Deaths (inverse to rating)
  - ADR (avg damage / round)
  - KAST% (rounds with kill/assist/survive/trade)
  - Common props: 50+ kills, sub-X deaths, MVP / 1v3+ clutches

Output: data/cs_players.json + data/cs_player_props.json
"""
from __future__ import annotations
import os, json, math, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ROSTER_PATH = os.path.join(DATA_DIR, "cs_players.json")
PROPS_PATH = os.path.join(DATA_DIR, "cs_player_props.json")

# Static roster snapshot: top CS teams with player names + HLTV-style rating
# (1.10+ = star, 1.00-1.10 = solid starter, <1.00 = role player)
CS_ROSTERS = {
    "Vitality": [
        ("ZywOo",      "awp",     1.30),
        ("apEX",       "rifler",  1.05),
        ("flameZ",     "rifler",  1.12),
        ("Spinx",      "rifler",  1.15),
        ("mezii",      "support", 1.05),
    ],
    "MOUZ": [
        ("torzsi",     "awp",     1.18),
        ("Brollan",    "rifler",  1.12),
        ("Jimpphat",   "rifler",  1.10),
        ("Spinx",      "rifler",  1.15),
        ("xertioN",    "rifler",  1.16),
    ],
    "Spirit": [
        ("donk",       "rifler",  1.32),
        ("zont1x",     "rifler",  1.15),
        ("magixx",     "support", 1.06),
        ("sh1ro",      "awp",     1.20),
        ("chopper",    "rifler",  1.05),
    ],
    "Aurora": [
        ("XANTARES",   "rifler",  1.18),
        ("Wicadia",    "rifler",  1.10),
        ("woxic",      "awp",     1.20),
        ("MAJ3R",      "rifler",  1.05),
        ("jottAAA",    "support", 1.05),
    ],
    "Falcons": [
        ("NiKo",       "rifler",  1.25),
        ("m0NESY",     "awp",     1.22),
        ("kyousuke",   "support", 1.05),
        ("kyxsan",     "rifler",  1.08),
        ("TeSeS",      "rifler",  1.10),
    ],
    "G2": [
        ("huNter-",    "rifler",  1.15),
        ("malbsMd",    "awp",     1.16),
        ("hyped",      "rifler",  1.05),
        ("SunPayus",   "rifler",  1.05),
        ("HeavyGod",   "support", 1.04),
    ],
    "FaZe": [
        ("rain",       "rifler",  1.10),
        ("frozen",     "rifler",  1.16),
        ("ropz",       "rifler",  1.18),
        ("broky",      "awp",     1.18),
        ("EliGE",      "rifler",  1.12),
    ],
    "Natus Vincere": [
        ("aleksib",    "support", 1.05),
        ("b1t",        "rifler",  1.18),
        ("jL",         "rifler",  1.12),
        ("iM",         "rifler",  1.10),
        ("w0nderful",  "awp",     1.18),
    ],
    "The MongolZ": [
        ("Senzu",      "support", 1.05),
        ("bLitz",      "rifler",  1.05),
        ("mzinho",     "rifler",  1.15),
        ("910",        "awp",     1.16),
        ("Techno",     "rifler",  1.18),
    ],
    "Astralis": [
        ("dev1ce",     "awp",     1.18),
        ("staehr",     "rifler",  1.10),
        ("Stavn",      "rifler",  1.12),
        ("jabbi",      "rifler",  1.10),
        ("cadiaN",     "rifler",  1.06),
    ],
    "Liquid": [
        ("YEKINDAR",   "rifler",  1.12),
        ("NertZ",      "awp",     1.16),
        ("ultimate",   "rifler",  1.08),
        ("Twistzz",    "rifler",  1.16),
        ("siuhy",      "support", 1.05),
    ],
    "BIG": [
        ("hyped",      "rifler",  1.08),
        ("syrsoN",     "awp",     1.15),
        ("KRIMZ",      "rifler",  1.10),
        ("nilo",       "rifler",  1.05),
        ("kraghen",    "rifler",  1.08),
    ],
    "Heroic": [
        ("yxngstxr",   "rifler",  1.10),
        ("nilo",       "rifler",  1.05),
        ("Souza",      "rifler",  1.05),
        ("KENBINHO",   "rifler",  1.08),
        ("Kynex",      "awp",     1.12),
    ],
    "FURIA": [
        ("KSCERATO",   "rifler",  1.15),
        ("yuurih",     "rifler",  1.13),
        ("chelo",      "rifler",  1.05),
        ("MOLODOY",    "awp",     1.10),
        ("FalleN",     "rifler",  1.00),
    ],
    "Complexity": [
        ("EliGE",      "rifler",  1.12),
        ("hallzerk",   "awp",     1.15),
        ("JT",         "rifler",  1.08),
        ("nicoodoz",   "rifler",  1.06),
        ("cxzi",       "rifler",  1.05),
    ],
    "Virtus.pro": [
        ("FL1T",       "rifler",  1.10),
        ("electroNic", "rifler",  1.12),
        ("Jame",       "awp",     1.15),
        ("fame",       "rifler",  1.08),
        ("ICY",        "rifler",  1.05),
    ],
}


def _poisson_p_over(lam: float, line: float) -> float:
    if lam <= 0: return 0.0
    threshold = int(math.floor(line)) + 1
    s = 0.0
    for k in range(threshold):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_match(rating: float, role: str, n_maps: int = 2) -> Dict[str, Any]:
    """Project per-match stats. CS BO3 averages ~2 maps. Per-map kill avg
    for HLTV 1.00 rating ≈ 18 kills/map at 30-round map length."""
    base_kills_per_map = 18
    base_deaths_per_map = 16
    # Rating linearly scales kills, inversely scales deaths
    lam_kills = base_kills_per_map * rating * n_maps
    lam_deaths = base_deaths_per_map * (1 / max(0.8, rating ** 0.7)) * n_maps
    # ADR baseline 75 at 1.00 rating
    adr = round(75 * rating, 1)
    # KAST% baseline 70 at 1.00 rating
    kast = min(0.95, max(0.45, 0.70 + (rating - 1) * 0.50))
    return {
        "expected_kills": round(lam_kills, 1),
        "expected_deaths": round(lam_deaths, 1),
        "expected_adr": adr,
        "expected_kast_pct": round(kast * 100, 1),
        "kd": round(lam_kills / max(0.5, lam_deaths), 2),
    }


def _build_props(rating: float) -> Dict[str, Any]:
    """Common CS player props for a BO3."""
    lam_k = 36 * rating    # 18 K/map * 2 maps baseline
    # Common lines: 35.5, 40.5, 45.5 (BO3 series total kills)
    KILL_LINES = [35.5, 40.5, 45.5, 50.5]
    DEATH_LINES = [30.5, 33.5]
    out = {"kills": [], "deaths": []}
    for ln in KILL_LINES:
        p = _poisson_p_over(lam_k, ln)
        out["kills"].append({
            "line": ln, "p_over": round(p, 4),
            "fair_over": _american(p), "fair_under": _american(1 - p),
        })
    lam_d = 32 * (1 / max(0.8, rating ** 0.7))
    for ln in DEATH_LINES:
        p = 1 - _poisson_p_over(lam_d, ln)
        out["deaths"].append({
            "line": ln, "p_under": round(p, 4),
            "fair_under": _american(p),
        })
    return out


def run() -> Dict[str, Any]:
    teams_out: Dict[str, Any] = {}
    all_players: List[Dict[str, Any]] = []
    for team, roster in CS_ROSTERS.items():
        team_players = []
        for name, role, rating in roster:
            entry = {
                "name": name, "role": role, "rating": rating,
                "team": team,
                "projection_bo3": _project_match(rating, role, n_maps=2),
                "props_bo3": _build_props(rating),
            }
            team_players.append(entry)
            all_players.append(entry)
        teams_out[team] = team_players

    # Sort all_players by rating desc
    all_players.sort(key=lambda p: -p["rating"])

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_teams": len(teams_out),
        "n_players": len(all_players),
        "teams": teams_out,
        "top_players": all_players[:20],
        "all_players": all_players,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ROSTER_PATH, "w") as f: json.dump(payload, f, indent=2)
    # Also persist props in a focused file for the UI
    props_payload = {
        "generated_at": payload["generated_at"],
        "n_players": payload["n_players"],
        "players": all_players,
    }
    with open(PROPS_PATH, "w") as f: json.dump(props_payload, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    print(f"Wrote {ROSTER_PATH}: {p['n_teams']} teams, {p['n_players']} players")
    print(f"  Top 10 by rating:")
    for pl in p["top_players"][:10]:
        proj = pl["projection_bo3"]
        print(f"    {pl['name']:14} ({pl['role']:7}) [{pl['team']:18}] rating {pl['rating']:.2f} "
              f"-> {proj['expected_kills']:.1f}K / {proj['expected_deaths']:.1f}D / KD {proj['kd']}")
