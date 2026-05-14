"""
EdgeStat - Master training entry point.

Runs every module in order and writes all JSON artifacts to ../data/:
  - today.json            (daily slate w/ recommendations)
  - ratings.json          (Elo + Glicko-2 team ratings)
  - props_projections.json (gradient-boosted prop edges)
  - backtest.json         (walk-forward backtest results)
  - linemaker.json        (sample line-move timeline)
  - arbitrage.json        (cross-book arb / middle / low-vig scan)
  - bankroll_mc.json      (bankroll Monte Carlo distribution)
  - kelly_heatmap.json    (Kelly fraction grid)
  - correlations.json     (SGP / correlated-parlay analysis)

Cron this with the GH Actions workflow.  ~60s wall-clock end-to-end.
"""
from __future__ import annotations

import sys
import time
import traceback


def run(name: str, fn) -> None:
    t0 = time.time()
    print(f"\n>>> {name}", flush=True)
    try:
        fn()
        print(f"<<< {name} done in {time.time() - t0:.1f}s", flush=True)
    except Exception as e:
        print(f"!!! {name} FAILED: {e}")
        traceback.print_exc()


def train_pipeline():
    from pipeline import run_pipeline, write_manifest, DEMO_SLATE
    manifest = run_pipeline(DEMO_SLATE)
    write_manifest(manifest)


def train_ratings():
    from ratings import generate_synthetic_season, elo_run, fit_glicko_season, TEAMS, write_artifact
    games = generate_synthetic_season(TEAMS, seed=42, games_per_team=162)
    elo = elo_run(games, TEAMS)
    glk = fit_glicko_season(games, TEAMS, period_games=6)
    write_artifact("../data/ratings.json", elo, glk)


def train_props():
    from prop_model import train_models, project_slate
    import os, json
    models, metrics = train_models(n_samples=1500, seed=23)
    out = project_slate(models)
    os.makedirs("../data", exist_ok=True)
    with open("../data/props_projections.json", "w") as f:
        json.dump({"slate": out, "metrics": metrics}, f, indent=2)
    print(f"Wrote ../data/props_projections.json")


def train_backtest():
    from backtest import run_walk_forward, write_backtest
    r = run_walk_forward(n_days=90, seed=7)
    write_backtest(r)


def train_linemaker():
    from linemaker import write_linemaker_demo
    write_linemaker_demo()


def train_arbitrage():
    from arbitrage import scan_all, write_artifact
    out = scan_all()
    write_artifact(out)


def train_risk():
    import json, os
    from risk import monte_carlo_bankroll, kelly_heatmap
    mc = monte_carlo_bankroll(p_win=0.55, american_price=-110,
                              n_plays=200, kelly_fraction=0.25,
                              n_sims=2000, seed=99)
    os.makedirs("../data", exist_ok=True)
    with open("../data/bankroll_mc.json", "w") as f:
        json.dump(mc, f, indent=2)
    print("Wrote ../data/bankroll_mc.json")
    # Heatmap takes longer; only run if --full passed.
    if "--full" in sys.argv:
        heat = kelly_heatmap(price=-110, n_plays=200, n_sims=400)
        with open("../data/kelly_heatmap.json", "w") as f:
            json.dump(heat, f, indent=2)
        print("Wrote ../data/kelly_heatmap.json")


def train_correlations():
    import json, os
    from correlations import sgp_analysis
    legs = [0.59, 0.27, 0.53]
    corr = [[1.00, 0.30, 0.55], [0.30, 1.00, 0.35], [0.55, 0.35, 1.00]]
    out1 = sgp_analysis(legs, +500, corr)
    legs2 = [0.45, 0.40]
    corr2 = [[1.0, -0.15], [-0.15, 1.0]]
    out2 = sgp_analysis(legs2, +220, corr2)
    os.makedirs("../data", exist_ok=True)
    with open("../data/correlations.json", "w") as f:
        json.dump({
            "example_yankees_sgp": out1,
            "example_both_teams_score": out2,
        }, f, indent=2)
    print("Wrote ../data/correlations.json")


def train_neural_net():
    from neural_net import train_and_evaluate, write_artifact
    net, metrics = train_and_evaluate(n_samples=1800, seed=23)
    write_artifact(net, metrics, "../data/neural_net.json")


def train_ensemble_model():
    import json, os
    from ensemble import train_ensemble
    ens, m = train_ensemble()
    os.makedirs("../data", exist_ok=True)
    with open("../data/ensemble.json", "w") as f:
        json.dump(m, f, indent=2)
    print("Wrote ../data/ensemble.json")


def train_features():
    import json, os
    from features import example_raw_game, extract_features, to_vector, describe_features, LEAGUE
    g = example_raw_game()
    feats = extract_features(g)
    vec = to_vector(feats)
    os.makedirs("../data", exist_ok=True)
    with open("../data/features.json", "w") as f:
        json.dump({
            "schema": describe_features(),
            "example_game": {
                "home": g.home, "away": g.away,
                "features": {k: round(v, 4) for k, v in feats.items()},
                "vector":   [round(v, 4) for v in vec],
            },
            "league_constants": LEAGUE,
        }, f, indent=2)
    print("Wrote ../data/features.json")


def train_calibration():
    import json, os
    from calibration import _synth_predictions_and_outcomes, calibration_report
    preds, y = _synth_predictions_and_outcomes(1500, seed=11)
    report = calibration_report(preds, y)
    os.makedirs("../data", exist_ok=True)
    with open("../data/calibration.json", "w") as f:
        json.dump(report, f, indent=2)
    print("Wrote ../data/calibration.json")


def train_live():
    from live import write_artifact as write_live
    write_live()


if __name__ == "__main__":
    print("================================")
    print("    EdgeStat Training Pipeline   ")
    print("================================")
    t_start = time.time()
    run("Daily pipeline + today.json",  train_pipeline)
    run("Feature engineering schema",   train_features)
    run("Team ratings (Elo + Glicko)",  train_ratings)
    run("Prop projections (GBM)",       train_props)
    run("Neural Network (MLP)",         train_neural_net)
    run("Ensemble (4-model stack)",     train_ensemble_model)
    run("Calibration / reliability",    train_calibration)
    run("Walk-forward backtest",        train_backtest)
    run("Linemaker timeline",           train_linemaker)
    run("Arbitrage / middle scan",      train_arbitrage)
    run("Bankroll Monte Carlo",         train_risk)
    run("Correlation / SGP pricer",     train_correlations)
    run("Live in-game model",           train_live)
    print(f"\nTotal wall-clock: {time.time() - t_start:.1f}s")
    print("All artifacts written to ../data/")


# Late additions:

def train_series():
    import json, os
    from series import fair_series_market, rotation_adjusted
    base = [0.62, 0.61, 0.55]
    a = [2.89, 3.20, 4.10]; b = [4.12, 3.85, 2.95]
    market = fair_series_market(base, 4.5)
    adjusted = fair_series_market(rotation_adjusted(base, a, b), 4.5)
    os.makedirs("../data", exist_ok=True)
    with open("../data/series.json", "w") as f:
        json.dump({"matchup": "LAD vs SDP (3-game home series)",
                   "base": market, "adjusted": adjusted,
                   "rotation_starters_a": ["Yamamoto","Snell","Glasnow"],
                   "rotation_starters_b": ["Darvish","Cease","King"]}, f, indent=2)
    print("Wrote ../data/series.json")


def train_playoff():
    from playoff import write_artifact as wpa
    wpa()


def train_portfolio():
    import json, os
    from portfolio import DEMO_BETS, optimize_portfolio
    stakes, metrics = optimize_portfolio(DEMO_BETS, bankroll_pct=0.10, lambda_risk=0.5)
    os.makedirs("../data", exist_ok=True)
    with open("../data/portfolio.json", "w") as f:
        json.dump({"bets": [{
            "label": b.label, "p_win": b.p_win, "price": b.american_price,
            "ev": round(b.ev_per_dollar, 4), "kelly": round(b.kelly_fraction, 4),
            "stake_pct_bankroll": round(stakes[i]*100, 4),
            "stake_units": round(stakes[i]*100, 2)
        } for i, b in enumerate(DEMO_BETS)],
            "metrics": metrics,
            "total_bankroll_pct": round(sum(stakes)*100, 4)}, f, indent=2)
    print("Wrote ../data/portfolio.json")


def train_hedge():
    import json, os
    from hedge import hedge_for_equal_payout, hedge_for_breakeven, arbitrage_check
    r1 = hedge_for_equal_payout(100, +1400, +250)
    r2 = hedge_for_breakeven(100, +1400, +250)
    r3 = arbitrage_check(+145, -125)
    os.makedirs("../data", exist_ok=True)
    with open("../data/hedge_examples.json", "w") as f:
        json.dump({"examples": {"ws_hedge_equal_payout": r1,
                                "ws_hedge_break_even":   r2,
                                "arb_check":             r3}}, f, indent=2)
    print("Wrote ../data/hedge_examples.json")


def train_sos():
    import json, os
    from sos import LAD_SCHEDULE, DEMO_RATINGS, past_sos, future_sos, strength_adjusted_record, project_remaining_wins
    past = past_sos(LAD_SCHEDULE, DEMO_RATINGS)
    fut = future_sos(LAD_SCHEDULE, DEMO_RATINGS)
    sar = strength_adjusted_record(LAD_SCHEDULE, 0.625, DEMO_RATINGS)
    proj = project_remaining_wins(LAD_SCHEDULE, 0.625, DEMO_RATINGS)
    os.makedirs("../data", exist_ok=True)
    with open("../data/sos.json", "w") as f:
        json.dump({"team": "LAD", "past_sos": past, "future_sos": fut,
                   "strength_adjusted_record": sar,
                   "projected_remaining_wins": proj,
                   "season_end_projection_wins": round(past["wins"]+proj, 1)}, f, indent=2)
    print("Wrote ../data/sos.json")


def train_injury():
    import json, os
    from injury import DEMO_INJURIES, single_game_wp_hit, season_wp_hit, implied_line_move
    payload = []
    for label, p, r in DEMO_INJURIES:
        wp = single_game_wp_hit(p, r)
        sw = season_wp_hit(p, r) if p.games_remaining_in_season > 0 else 0.0
        payload.append({"scenario": label, "single_game_wp_hit_pp": wp,
                        "season_wins_lost": sw, "line_move": implied_line_move(wp)})
    os.makedirs("../data", exist_ok=True)
    with open("../data/injuries.json", "w") as f:
        json.dump({"examples": payload}, f, indent=2)
    print("Wrote ../data/injuries.json")


if __name__ == "__main__":
    # Run the additional modules.
    pass
