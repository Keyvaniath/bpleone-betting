"""
EdgeStat - Gradient Boosted Player-Prop Projection.

Trains a from-scratch gradient boosting regressor (no scikit-learn dependency)
on a synthetic but realistic player-prop dataset, then projects today's prop
slate. The same shape would drop into XGBoost/LightGBM in production.

Workflow:
  1. Generate synthetic player history (5,000 PA-style rows with features +
     observed counting stats).
  2. Train a gradient-boosted regression tree ensemble per stat (TB, HR, K, H).
  3. For each prop on today's slate, project the expected value AND the full
     distribution (Poisson-ish around the projection).
  4. Compare projected fair line vs. book line → edge.
  5. Write a JSON artifact the front-end consumes.

Pure Python so it runs in CI without numpy.
"""
from __future__ import annotations

import math
import random
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


# --------------------------- Synthetic data ---------------------------

FEATURES = [
    "wrc_plus",        # 70-160 typical
    "iso",             # 0.10 - 0.30
    "k_pct",           # 0.10 - 0.35
    "bb_pct",          # 0.05 - 0.18
    "speed",           # 0-100 (sprint-speed percentile)
    "park_factor",     # 0.85-1.20
    "opp_xfip",        # 2.5 - 5.0
    "opp_hand_match",  # 1 = platoon advantage, 0 = neutral
    "weather_adj",     # -0.10 to +0.10 (HR wind etc)
    "lineup_slot",     # 1-9
]


@dataclass
class PropSample:
    features: Dict[str, float]
    target: Dict[str, int]   # {"TB": 2, "HR": 0, "K": 1, "H": 1}


def _synthetic_player_game(rng: random.Random) -> PropSample:
    """Generate one player-game with features and observed stats."""
    f = {
        "wrc_plus":   rng.gauss(105, 22),
        "iso":        rng.gauss(0.175, 0.045),
        "k_pct":      rng.gauss(0.225, 0.045),
        "bb_pct":     rng.gauss(0.085, 0.025),
        "speed":      rng.gauss(50, 15),
        "park_factor": rng.gauss(1.0, 0.07),
        "opp_xfip":   rng.gauss(4.0, 0.6),
        "opp_hand_match": float(rng.random() < 0.4),  # 40% platoon advantage
        "weather_adj": rng.gauss(0.0, 0.04),
        "lineup_slot": float(rng.randint(1, 9)),
    }

    # Latent rates derived from features.
    # Expected TB: average ~1.5, scaled by wrc+, iso, opp_xfip, park, weather, hand match, slot.
    slot_pa_boost = (10 - int(f["lineup_slot"])) / 10.0 * 0.7 + 0.6   # top-of-order more PAs
    base_tb = 1.2 * (f["wrc_plus"] / 100) * (1 + (f["iso"] - 0.175) * 0.8) \
                  * (1 + (4.0 - f["opp_xfip"]) * 0.10) \
                  * f["park_factor"] \
                  * (1 + f["weather_adj"]) \
                  * (1 + 0.12 * f["opp_hand_match"]) \
                  * slot_pa_boost

    # Sample observed stats from Poisson around expectations.
    base_tb = max(0.1, min(base_tb, 6))
    tb = _poisson_sample(base_tb, rng)
    # HR is ~5-12% of TB on average.
    hr_rate = 0.06 * (1 + (f["iso"] - 0.175) * 4) * f["park_factor"] * (1 + f["weather_adj"]*2)
    hr = sum(1 for _ in range(int(tb / max(0.1, hr_rate * 4))) if rng.random() < hr_rate)
    hr = min(hr, max(tb // 4, 0))
    # Hits: TB minus HR-based padding.
    h_expectation = 1.0 * (f["wrc_plus"] / 100) * (1 - f["k_pct"] * 0.8) * slot_pa_boost
    h = _poisson_sample(max(0.2, h_expectation), rng)
    # Pitcher Ks (for K props): handled separately; this is just hitter Ks.
    k_expectation = 0.95 * f["k_pct"] * 4.2 * (1 + (4.0 - f["opp_xfip"]) * 0.15) * slot_pa_boost
    k = _poisson_sample(max(0.1, k_expectation), rng)

    return PropSample(features=f, target={"TB": tb, "HR": hr, "K": k, "H": h})


def _poisson_sample(lam: float, rng: random.Random) -> int:
    L = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= L:
            return k - 1


def generate_synthetic_dataset(n: int = 5000, seed: int = 17) -> List[PropSample]:
    rng = random.Random(seed)
    return [_synthetic_player_game(rng) for _ in range(n)]


# --------------------------- Gradient boosting from scratch ---------------------------
#
# Simple regression tree → boosted ensemble.  Not as fast as XGBoost, but
# transparent.  Trains in seconds on synthetic 5k-row data.

@dataclass
class TreeNode:
    feature: Optional[str] = None
    threshold: Optional[float] = None
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None
    value: Optional[float] = None


def _best_split_fast(X: List[Dict[str, float]], y: List[float]) -> Tuple[Optional[str], Optional[float], float]:
    """Find best (feature, threshold) split by minimizing post-split SSE.

    O(n * F * C) where F = num features and C = num candidate thresholds.
    """
    n = len(y)
    if n < 4:
        return None, None, float("inf")
    total = sum(y)
    sse_parent = sum(v * v for v in y) - total * total / n
    best_sse = sse_parent
    best_feat = None
    best_thresh = None
    for feat in FEATURES:
        # Use quantile thresholds for speed - only 4 candidates per feature.
        vals = sorted(row[feat] for row in X)
        cuts = [vals[int(n * q / 5)] for q in range(1, 5)]
        for thresh in cuts:
            sum_l = 0.0; n_l = 0; sq_l = 0.0
            for i in range(n):
                if X[i][feat] <= thresh:
                    sum_l += y[i]; n_l += 1; sq_l += y[i] * y[i]
            if n_l < 2 or n_l > n - 2:
                continue
            n_r = n - n_l
            sum_r = total - sum_l
            sq_r = (sum(v * v for v in y)) - sq_l
            sse_l = sq_l - sum_l * sum_l / n_l
            sse_r = sq_r - sum_r * sum_r / n_r
            sse = sse_l + sse_r
            if sse < best_sse:
                best_sse = sse
                best_feat = feat
                best_thresh = thresh
    return best_feat, best_thresh, best_sse


def _grow_tree(X: List[Dict[str, float]], y: List[float],
               max_depth: int = 3, min_samples: int = 20) -> TreeNode:
    """Greedy regression-tree growth."""
    if len(X) <= min_samples or max_depth == 0:
        return TreeNode(value=sum(y) / max(len(y), 1))
    feat, thresh, _ = _best_split_fast(X, y)
    if feat is None:
        return TreeNode(value=sum(y) / max(len(y), 1))
    l_idx = [i for i in range(len(X)) if X[i][feat] <= thresh]
    r_idx = [i for i in range(len(X)) if X[i][feat] > thresh]
    if not l_idx or not r_idx:
        return TreeNode(value=sum(y) / max(len(y), 1))
    node = TreeNode(feature=feat, threshold=thresh)
    node.left  = _grow_tree([X[i] for i in l_idx], [y[i] for i in l_idx], max_depth - 1, min_samples)
    node.right = _grow_tree([X[i] for i in r_idx], [y[i] for i in r_idx], max_depth - 1, min_samples)
    return node


def _predict_tree(node: TreeNode, x: Dict[str, float]) -> float:
    if node.value is not None:
        return node.value
    if x[node.feature] <= node.threshold:
        return _predict_tree(node.left, x)
    return _predict_tree(node.right, x)


@dataclass
class GBM:
    """Gradient boosting regressor."""
    n_estimators: int = 80
    learning_rate: float = 0.08
    max_depth: int = 3
    trees: List[TreeNode] = field(default_factory=list)
    init_value: float = 0.0
    target_name: str = ""

    def fit(self, samples: List[PropSample], target: str) -> None:
        self.target_name = target
        X = [s.features for s in samples]
        y = [float(s.target[target]) for s in samples]
        self.init_value = sum(y) / len(y)
        preds = [self.init_value] * len(y)
        for _ in range(self.n_estimators):
            residuals = [yi - pi for yi, pi in zip(y, preds)]
            tree = _grow_tree(X, residuals, max_depth=self.max_depth)
            self.trees.append(tree)
            for i, xi in enumerate(X):
                preds[i] += self.learning_rate * _predict_tree(tree, xi)

    def predict(self, x: Dict[str, float]) -> float:
        p = self.init_value
        for tree in self.trees:
            p += self.learning_rate * _predict_tree(tree, x)
        return max(0.0, p)


# --------------------------- Distribution & pricing ---------------------------

def poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def prop_over_prob(projection: float, line: float) -> float:
    """P(stat > line) assuming Poisson around projection."""
    if line <= 0:
        return 1.0 - poisson_pmf(0, projection)
    k_int = int(math.floor(line))
    # Half-line: P(stat >= k_int+1)
    # Whole-line: P(stat > k_int) = P(stat >= k_int+1) (no push for over)
    p_over = 1.0 - sum(poisson_pmf(k, projection) for k in range(k_int + 1))
    if line == k_int:  # whole number - half push
        p_push = poisson_pmf(k_int, projection)
        return p_over + 0.5 * p_push
    return p_over


def american_from_prob(p: float) -> int:
    if p <= 0 or p >= 1: return 0
    dec = 1 / p
    return int(round((dec - 1) * 100)) if dec >= 2 else -int(round(100 / (dec - 1)))


def american_to_decimal(am: int) -> float:
    if am == 0: return 1.0
    return 1.0 + am / 100.0 if am > 0 else 1.0 + 100.0 / abs(am)


def edge_pct(model_p: float, am: int) -> float:
    ev = model_p * (american_to_decimal(am) - 1) - (1 - model_p)
    return ev * 100.0


# --------------------------- Training entry point ---------------------------

@dataclass
class TrainedPropModels:
    tb: GBM
    hr: GBM
    k:  GBM
    h:  GBM


def train_models(n_samples: int = 1500, seed: int = 17) -> TrainedPropModels:
    """Train one GBM per stat. Returns the ensemble."""
    data = generate_synthetic_dataset(n_samples, seed)
    # Train/test split, 80/20.
    split = int(len(data) * 0.8)
    train, test = data[:split], data[split:]

    models = {}
    metrics = {}
    for target in ("TB", "HR", "K", "H"):
        gbm = GBM(n_estimators=25, learning_rate=0.08, max_depth=3)
        gbm.fit(train, target)
        # OOS MAE.
        preds = [gbm.predict(s.features) for s in test]
        actuals = [s.target[target] for s in test]
        mae = sum(abs(p - a) for p, a in zip(preds, actuals)) / len(preds)
        bias = sum(p - a for p, a in zip(preds, actuals)) / len(preds)
        models[target] = gbm
        metrics[target] = {"mae": round(mae, 3), "bias": round(bias, 3),
                           "n_train": len(train), "n_test": len(test)}
        print(f"  {target}: MAE={mae:.3f}  bias={bias:+.3f}  (train={len(train)}, test={len(test)})")
    return TrainedPropModels(tb=models["TB"], hr=models["HR"], k=models["K"], h=models["H"]), metrics


# --------------------------- Slate projection ---------------------------

# Sample today's prop slate (player feature vectors + book lines).
TODAY_SLATE = [
    {"player": "Aaron Judge", "team": "NYY", "stat": "TB", "line": 1.5, "price": +115,
     "features": {"wrc_plus": 178, "iso": 0.296, "k_pct": 0.281, "bb_pct": 0.184,
                  "speed": 50, "park_factor": 1.08, "opp_xfip": 3.05,
                  "opp_hand_match": 1, "weather_adj": 0.04, "lineup_slot": 2}},
    {"player": "Shohei Ohtani", "team": "LAD", "stat": "HR", "line": 0.5, "price": +260,
     "features": {"wrc_plus": 184, "iso": 0.336, "k_pct": 0.255, "bb_pct": 0.131,
                  "speed": 75, "park_factor": 0.91, "opp_xfip": 4.12,
                  "opp_hand_match": 0, "weather_adj": -0.02, "lineup_slot": 2}},
    {"player": "Mookie Betts", "team": "LAD", "stat": "H", "line": 0.5, "price": -150,
     "features": {"wrc_plus": 140, "iso": 0.205, "k_pct": 0.142, "bb_pct": 0.112,
                  "speed": 72, "park_factor": 0.91, "opp_xfip": 4.12,
                  "opp_hand_match": 0, "weather_adj": -0.02, "lineup_slot": 1}},
    {"player": "Bobby Witt Jr.", "team": "KCR", "stat": "TB", "line": 1.5, "price": +108,
     "features": {"wrc_plus": 162, "iso": 0.245, "k_pct": 0.158, "bb_pct": 0.080,
                  "speed": 95, "park_factor": 1.02, "opp_xfip": 3.62,
                  "opp_hand_match": 0, "weather_adj": 0.0, "lineup_slot": 2}},
    {"player": "Freddie Freeman", "team": "LAD", "stat": "TB", "line": 1.5, "price": +130,
     "features": {"wrc_plus": 142, "iso": 0.221, "k_pct": 0.144, "bb_pct": 0.131,
                  "speed": 45, "park_factor": 0.91, "opp_xfip": 4.12,
                  "opp_hand_match": 1, "weather_adj": -0.02, "lineup_slot": 3}},
    {"player": "Juan Soto", "team": "NYM", "stat": "H", "line": 0.5, "price": -180,
     "features": {"wrc_plus": 158, "iso": 0.265, "k_pct": 0.151, "bb_pct": 0.181,
                  "speed": 50, "park_factor": 0.95, "opp_xfip": 3.11,
                  "opp_hand_match": 1, "weather_adj": 0.02, "lineup_slot": 2}},
    {"player": "Garrett Crochet", "team": "BOS", "stat": "K", "line": 7.5, "price": +100,
     "features": {"wrc_plus": 100, "iso": 0.0, "k_pct": 0.30, "bb_pct": 0.08,
                  "speed": 0, "park_factor": 1.08, "opp_xfip": 4.0,
                  "opp_hand_match": 0, "weather_adj": 0.0, "lineup_slot": 0}},
]


def project_slate(models: TrainedPropModels) -> List[dict]:
    out = []
    for p in TODAY_SLATE:
        gbm = {"TB": models.tb, "HR": models.hr, "K": models.k, "H": models.h}[p["stat"]]
        projection = gbm.predict(p["features"])
        # For K props from pitchers, scale up since we trained on hitter-Ks
        if p["stat"] == "K" and p["features"].get("speed", 0) == 0:
            projection *= 4.0  # rough proxy: pitchers face ~24 batters; use as multiplier
        prob_over = prop_over_prob(projection, p["line"])
        fair = american_from_prob(prob_over)
        edge = edge_pct(prob_over, p["price"])
        out.append({
            "player": p["player"], "team": p["team"], "stat": p["stat"],
            "line": p["line"], "price": p["price"],
            "projection": round(projection, 2),
            "model_prob_over": round(prob_over, 4),
            "fair_price": fair,
            "edge_pct": round(edge, 2),
            "play": "BET" if edge >= 3 else ("LEAN" if edge >= 1.5 else "PASS"),
        })
    out.sort(key=lambda x: -x["edge_pct"])
    return out


# --------------------------- CLI ---------------------------

if __name__ == "__main__":
    print("Training gradient boosted prop models on synthetic data…")
    models, metrics = train_models(n_samples=1500, seed=23)
    print("\nSlate projections:")
    print(f"{'Player':22}{'Stat':>4}{'Line':>6}{'Price':>8}{'Proj':>7}{'Model P':>9}{'Fair':>7}{'Edge':>8}{'Play':>7}")
    out = project_slate(models)
    for row in out:
        print(f"{row['player']:<22}{row['stat']:>4}{row['line']:>6.1f}"
              f"{('+' if row['price']>0 else '')+str(row['price']):>8}"
              f"{row['projection']:>7.2f}{row['model_prob_over']:>9.3f}"
              f"{('+' if row['fair_price']>0 else '')+str(row['fair_price']):>7}"
              f"{row['edge_pct']:>+7.2f}%{row['play']:>7}")
    # Write artifact.
    os.makedirs("../data", exist_ok=True)
    with open("../data/props_projections.json", "w") as f:
        json.dump({"slate": out, "metrics": metrics}, f, indent=2)
    print("\nWrote ../data/props_projections.json")
open("../data/props_projections.json", "w") as f:
        json.dump({"slate": out, "metrics": metrics}, f, indent=2)
    print("\nWrote ../data/props_projections.json")
