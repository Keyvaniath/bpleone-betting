# Data licensing decision matrix (Tier 1 #3)

The one Tier-1 item that needs spend, not just code. Goal: move off free/public feeds
(whose ToS generally bar commercial use) onto licensed data before marketing the site
commercially. **Prioritize odds first** — it's the biggest legal exposure *and* it
unlocks real book-vs-model edges + CLV (the lapsed `ODDS_API_KEY` is the visible tip).

The integration is already key-ready: set `ODDS_API_KEY` as a GitHub secret and the
prop/edge paths light up (see `python/espn_odds.py`, `book_vs_model_team.py`). The
decision below is purely which provider/tier to buy.

## Odds (do this first)

| Provider | Rough cost | Best for | Notes |
|---|---|---|---|
| **The Odds API** | ~$30–$300/mo by call volume | Fastest restart — already wired | Drop-in; restores `ODDS_API_KEY`. Good first step. |
| **OpticOdds** | ~$mid (quote) | Deeper markets, player props, low latency | Strong props coverage; upgrade path once revenue justifies it. |
| **SportsDataIO** | tiered (quote) | Odds + stats in one contract | Bundles odds with official-ish stats. |
| **Sportradar / Genius** | enterprise $$$$ | Official league data + partnerships | Only when you want official data rights / scale. |

**Recommendation:** start with **The Odds API paid tier** (cheapest, already integrated),
move to **OpticOdds** when prop volume/revenue warrants richer markets.

## Stats / schedules / results
- **MLB Stats API** — terms are relatively permissive; likely OK to keep near-term
  (confirm with counsel for commercial use).
- **ESPN / Daum / bo3.gg / PrizePicks public** — public endpoints currently used under
  their terms; these are the ones to replace or license for a fully clean commercial
  footing. SportsDataIO / Sportradar can cover the licensed-stats side if/when needed.

## Suggested sequence
1. **Now:** buy The Odds API paid tier → set `ODDS_API_KEY` secret. Immediate compliance
   win on the highest-exposure feed + unlocks prop edges/CLV.
2. **Next:** evaluate OpticOdds for props once the subscription/affiliate revenue starts.
3. **Later (scale):** licensed stats (SportsDataIO/Sportradar) to replace the public
   stat/schedule feeds for a fully licensed stack.

Confirm each provider's license scope with counsel as part of the
`ATTORNEY_REVIEW_PACKET.md` review (question 7).
