# IA / Page-Consolidation Roadmap

**Goal:** fold the 126-page maze into a handful of dense, filterable pages without
losing capability or breaking inbound links. The nav is already sectioned cleanly
(6 dropdowns), so the sprawl is in **overlapping page clusters** that each show the
same data sliced slightly differently. This doc scopes the merge so it can be done
as small, safe, one-cluster-at-a-time PRs.

## Method (per cluster, repeatable + reversible)
1. Pick the **canonical** page in the cluster (the densest / most-maintained one).
2. Diff the others against it; migrate any unique panel into the canonical page (as a
   tab/filter) so nothing is lost.
3. Convert each retired page to a **thin client-side redirect stub** to the canonical
   (`<script>location.replace('canonical.html'+location.hash)</script>` + a `<noscript>`
   link). Inbound links + bookmarks keep working; the maze shrinks.
4. Trim the retired entries from `js/nav.js`.
5. Verify the canonical page renders all migrated content with zero console errors.

Redirect-don't-delete keeps it 100% reversible: restore a stub to a full page anytime.

## Clusters (highest payoff first)

### 1. Picks hub  — ~10 pages → 1 filterable board
Today's recommended picks, sliced differently: `todays-top-plays`, `top-3-picks`,
`alpha-pick`, `high-confidence`, `locks-of-day`, `best-bets`, `consensus-picks`,
`convergence`, `confluence`, `fade-picks`.
**Target:** one **Today's Picks** page with a filter/tab row (All · Locks · Alpha ·
High-Conf · Consensus · Fades) over the unified `bet_slate` / `all_picks_ledger`
pending set. Keep `play-of-day` (the flagship deep-dive) separate.
**Win:** ~9 nav links → 2; the single highest felt-UX reduction.

### 2. Proof / performance hub  — ~8 pages → 2
`track-record`, `accuracy`, `module-performance`, `model-health`, `reliability`,
`pod-history`, `lifecycle`, `audit`. All read the same ledger/summary artifacts.
**Target:** `track-record` (canonical public proof, now leads with forward-test + CI)
+ `module-performance` (the deep per-source/sport/market breakdown). Redirect
`accuracy` → `module-performance`; `reliability` → `model-health`; fold `lifecycle`
+ `pod-history` panels into `track-record` tabs.

### 3. Learning hub  — 6 pages → 2
`live-learning` (the consolidated dashboard already built), `self-learning`,
`learning`, `training`, `learning-integrity`, `model-control`.
**Target:** `live-learning` (canonical "is the model learning" dashboard) +
`learning-integrity` (the rigor/guards page). Redirect `learning`, `training`,
`self-learning` → `live-learning` after migrating any unique panel.

### 4. Daily reads  — 3 → 1
`todays-brief` (master brief), `daily-summary`, `brief`. Keep `todays-brief`;
redirect the other two into it.

### 5. System / data  — 3 → 1
`status` (public status page), `data-health`, `data-integrity`. Keep `status` as the
public face; fold the other two in as expandable sections.

## Net effect
~30 redundant pages collapse to ~8 canonical ones (≈ 126 → ~100 reachable, far fewer
in the nav). Zero capability lost; every old URL still resolves via its redirect stub.

## Done already
- Literal duplicate `methodology.html` nav entry removed (was in both Models and More).
- 17 dead boards (generated, surfaced by nothing) deleted — see the cleanup commit.

## Not started (needs a green light per cluster)
Clusters 1-5 above. Recommend starting with **Picks hub** (biggest win) as the
template PR, then repeating the method for 2-5.
