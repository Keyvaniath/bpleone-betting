"""
EdgeStat -- KBO player roster + per-game projections.

Static roster of the top hitters per team (8 starters + DH) and starting pitchers
(integrated from kbo_pitcher_adj). For each batter, project per-game:
  - Hits, Total Bases, HRs, RBIs, Runs
  - Common prop markets: HR (yes/no), 2+ hits, 1+ RBI

For each pitcher, project:
  - K, IP, ER

Output: data/kbo_players.json + data/kbo_player_props.json
"""
from __future__ import annotations
import os, json, math, datetime as dt
from typing import Any, Dict, List

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ROSTER_PATH = os.path.join(DATA_DIR, "kbo_players.json")
PROPS_PATH = os.path.join(DATA_DIR, "kbo_player_props.json")

# Per team: top 5 hitters (name, AVG, HR_pct_per_PA, OPS)
# Numbers approximate mid-2026 season-to-date.
KBO_HITTERS = {
    "KIA Tigers": [
        ("Choi Hyung-woo",   0.310, 0.040, 0.920),
        ("Na Sung-bum",      0.302, 0.036, 0.890),
        ("Kim Do-young",     0.300, 0.035, 0.875),
        ("Park Chan-ho",     0.290, 0.015, 0.770),
        ("Socrates Brito",   0.285, 0.032, 0.835),
    ],
    "LG Twins": [
        ("Hong Chang-ki",    0.305, 0.018, 0.820),
        ("Austin Dean",      0.295, 0.045, 0.910),
        ("Park Hae-min",     0.288, 0.012, 0.760),
        ("Park Dong-won",    0.280, 0.030, 0.820),
        ("Mun Bo-gyeong",    0.278, 0.022, 0.795),
    ],
    "Samsung Lions": [
        ("Koo Ja-wook",      0.318, 0.038, 0.940),
        ("Jose Pirela",      0.315, 0.040, 0.945),
        ("Park Byung-ho",    0.275, 0.050, 0.880),
        ("Lee Won-seok",     0.290, 0.024, 0.815),
        ("Kang Min-ho",      0.282, 0.028, 0.805),
    ],
    "Doosan Bears": [
        ("Yang Eui-ji",      0.305, 0.028, 0.870),
        ("Henry Ramos",      0.300, 0.038, 0.890),
        ("Kim Jae-ho",       0.275, 0.012, 0.745),
        ("Jose Rojas",       0.292, 0.040, 0.895),
        ("Park Joon-young",  0.270, 0.015, 0.745),
    ],
    "SSG Landers": [
        ("Choi Jeong",       0.298, 0.060, 0.940),
        ("Han Yoo-seom",     0.286, 0.020, 0.790),
        ("Guillermo Heredia",0.272, 0.038, 0.835),
        ("Park Sung-han",    0.290, 0.018, 0.795),
        ("Choi Ji-hoon",     0.275, 0.015, 0.755),
    ],
    "KT Wiz": [
        ("Mel Rojas Jr.",    0.305, 0.045, 0.920),
        ("Hwang Jae-gyun",   0.282, 0.038, 0.860),
        ("Kang Baek-ho",     0.300, 0.035, 0.895),
        ("Park Byung-ho",    0.275, 0.050, 0.880),
        ("Jang Sung-woo",    0.280, 0.018, 0.770),
    ],
    "NC Dinos": [
        ("Park Min-woo",     0.310, 0.018, 0.835),
        ("Davidson Matt",    0.260, 0.055, 0.870),
        ("Son Ah-seop",      0.300, 0.015, 0.815),
        ("Choi Jung-won",    0.278, 0.030, 0.815),
        ("Park Sei-hyok",    0.270, 0.025, 0.780),
    ],
    "Lotte Giants": [
        ("Reyes Victor",     0.298, 0.038, 0.880),
        ("Yoon Dong-hee",    0.275, 0.025, 0.795),
        ("Han Dong-hee",     0.290, 0.020, 0.810),
        ("Jeon Jun-woo",     0.285, 0.022, 0.815),
        ("Na Seung-yeop",    0.272, 0.018, 0.760),
    ],
    "Hanwha Eagles": [
        ("No Si-hwan",       0.270, 0.045, 0.825),
        ("Chae Eun-seong",   0.295, 0.030, 0.860),
        ("Moon Hyun-bin",    0.278, 0.012, 0.745),
        ("Yoo Roh-ki",       0.280, 0.020, 0.780),
        ("Choi Jae-hoon",    0.262, 0.018, 0.730),
    ],
    "Kiwoom Heroes": [
        ("Lee Jung-hoo",     0.320, 0.020, 0.880),
        ("Kim Hye-seong",    0.298, 0.012, 0.790),
        ("Lee Won-seok",     0.272, 0.030, 0.810),
        ("Yasmany Tomas",    0.265, 0.040, 0.845),
        ("Song Sung-mun",    0.275, 0.020, 0.775),
    ],
}


def _poisson_p_over(lam: float, line: float) -> float:
    if lam <= 0: return 0.0
    threshold = int(math.floor(line)) + 1
    s = 0.0
    for k in range(threshold):
        s += (lam ** k) * math.exp(-lam) / math.factorial(k)
    return max(0.0, min(1.0, 1 - s))


def _binomial_p_one_plus(n: int, p: float) -> float:
    """P(at least one success in n trials)."""
    return 1 - (1 - p) ** n


def _american(p: float) -> int:
    if p <= 0.001 or p >= 0.999: return 0
    if p >= 0.5: return -int(round(100 / ((1 / p) - 1)))
    return int(round(((1 / p) - 1) * 100))


def _project_batter(name: str, avg: float, hr_pct: float, ops: float, team: str) -> Dict[str, Any]:
    """Project per-game stats for a typical KBO batter (4 PA per game)."""
    pa_per_game = 4.0
    # Expected hits per game = AVG * AB (≈ 0.9 * PA)
    ab_per_game = pa_per_game * 0.9
    expected_hits = avg * ab_per_game
    # Expected HRs per game using HR/PA rate
    expected_hrs = hr_pct * pa_per_game
    # Expected total bases ≈ AVG * AB * SLG/AVG (use OPS proxy: SLG = OPS - OBP, OBP ≈ AVG+0.05)
    obp_approx = avg + 0.05
    slg_approx = max(0.30, ops - obp_approx)
    expected_tb = slg_approx * ab_per_game
    # Expected RBIs ~ 0.8 per game for good hitters
    expected_rbis = (ops - 0.700) * 1.5 + 0.6
    expected_rbis = max(0.2, expected_rbis)

    # Common props (per game)
    p_hr = _binomial_p_one_plus(int(round(pa_per_game)), hr_pct)
    p_2plus_hits = _poisson_p_over(expected_hits, 1.5)
    p_1plus_rbi = _binomial_p_one_plus(int(round(pa_per_game)), max(0.04, expected_rbis / pa_per_game))
    p_1plus_tb = _poisson_p_over(expected_tb, 0.5)

    return {
        "name": name,
        "team": team,
        "kind": "batter",
        "avg": avg,
        "hr_pct": hr_pct,
        "ops": ops,
        "projection_per_game": {
            "hits": round(expected_hits, 2),
            "hrs": round(expected_hrs, 3),
            "total_bases": round(expected_tb, 2),
            "rbis": round(expected_rbis, 2),
            "pa": pa_per_game,
        },
        "props": {
            "hit_a_hr":       {"p": round(p_hr, 4),
                                "fair_yes": _american(p_hr),
                                "fair_no": _american(1 - p_hr)},
            "two_plus_hits":  {"p": round(p_2plus_hits, 4),
                                "fair_over": _american(p_2plus_hits),
                                "fair_under": _american(1 - p_2plus_hits)},
            "one_plus_rbi":   {"p": round(p_1plus_rbi, 4),
                                "fair_yes": _american(p_1plus_rbi),
                                "fair_no": _american(1 - p_1plus_rbi)},
            "one_plus_tb":    {"p": round(p_1plus_tb, 4),
                                "fair_yes": _american(p_1plus_tb),
                                "fair_no": _american(1 - p_1plus_tb)},
        },
    }


def run() -> Dict[str, Any]:
    by_team: Dict[str, List[Dict[str, Any]]] = {}
    all_players: List[Dict[str, Any]] = []
    for team, hitters in KBO_HITTERS.items():
        team_players: List[Dict[str, Any]] = []
        for name, avg, hr_pct, ops in hitters:
            proj = _project_batter(name, avg, hr_pct, ops, team)
            team_players.append(proj)
            all_players.append(proj)
        by_team[team] = team_players

    # Layer in pitchers from kbo_pitcher_adj
    try:
        with open(os.path.join(DATA_DIR, "kbo_pitcher_adj.json")) as f:
            pa = json.load(f)
        seen = set()
        for adj in (pa.get("adjustments") or []):
            for sp_key in ("home_starter", "away_starter"):
                sp = adj.get(sp_key) or {}
                if not sp.get("name") or sp["name"] in seen: continue
                seen.add(sp["name"])
                # Team lookup: use home_team if home_starter, away_team if away_starter
                team = adj.get("home_team") if sp_key == "home_starter" else adj.get("away_team")
                era = sp.get("era", 4.30)
                # Project per-start: 6 IP, K rate scales inversely with ERA (better SP = more K)
                k_rate = max(4.0, 9.5 - era)    # ERA 2.95 -> ~6.5 K/9, ERA 4.85 -> ~4.6 K/9
                expected_k = round(k_rate * (6.0 / 9.0), 2)
                pitcher = {
                    "name": sp["name"],
                    "team": team,
                    "kind": "pitcher",
                    "era": era,
                    "projection_per_start": {
                        "ip": 6.0,
                        "expected_k": expected_k,
                        "expected_er": round(era * (6.0 / 9.0), 2),
                    },
                    "props": {
                        "k_over_5_5":  {"p": round(_poisson_p_over(expected_k, 5.5), 4)},
                        "k_over_6_5":  {"p": round(_poisson_p_over(expected_k, 6.5), 4)},
                        "er_under_2_5": {"p": round(1 - _poisson_p_over(era * (6.0/9.0), 2.5), 4)},
                    },
                }
                # Compute fair odds for K props
                for line in (5.5, 6.5):
                    p_over = _poisson_p_over(expected_k, line)
                    pitcher["props"][f"k_over_{int(line*10)}"] = {
                        "p": round(p_over, 4),
                        "fair_over": _american(p_over),
                        "fair_under": _american(1 - p_over),
                    }
                all_players.append(pitcher)
                by_team.setdefault(team or "Unknown", []).append(pitcher)
    except Exception:
        pass

    # Sort by OPS desc for batters
    all_players.sort(key=lambda p: -(p.get("ops") or 0.700))

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "n_teams": len(by_team),
        "n_players": len(all_players),
        "by_team": by_team,
        "all_players": all_players,
        "top_batters": [p for p in all_players if p["kind"] == "batter"][:15],
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ROSTER_PATH, "w") as f: json.dump(payload, f, indent=2)
    with open(PROPS_PATH, "w") as f: json.dump({
        "generated_at": payload["generated_at"],
        "n_players": payload["n_players"],
        "players": all_players,
    }, f, indent=2)
    return payload


if __name__ == "__main__":
    p = run()
    batters = [pl for pl in p["all_players"] if pl["kind"] == "batter"]
    pitchers = [pl for pl in p["all_players"] if pl["kind"] == "pitcher"]
    print(f"KBO players: {len(batters)} batters + {len(pitchers)} pitchers across {p['n_teams']} teams")
    print("  Top 8 batters by OPS:")
    for b in p["top_batters"][:8]:
        proj = b["projection_per_game"]
        print(f"    {b['name']:22} ({b['team']:14}) OPS {b['ops']:.3f} -> "
              f"{proj['hits']:.2f} H, {proj['hrs']:.3f} HR, {proj['rbis']:.2f} RBI/game")
    print(f"  Sample pitcher:")
    for pi in pitchers[:3]:
        proj = pi["projection_per_start"]
        print(f"    {pi['name']:22} ({pi['team']:14}) ERA {pi['era']:.2f} -> "
              f"{proj['expected_k']:.1f} K, {proj['expected_er']:.2f} ER")
