# EdgeStat on X — Launch Kit

Everything needed to stand up the betting-Twitter channel and start broadcasting
the daily Alpha Pick. **Account creation is your 5-minute manual step** (I can't
create accounts); after that the machine runs itself and posting is one tap a day.

> Brand note: this is a SEPARATE brand from @Bpleonresearch (equity research).
> Keep them apart — different audience, different compliance posture.

---

## 1. Account setup (5 minutes, you)

**Handle options** (in preference order — check availability):
1. `@EdgeStatBet` — clean, brandable, says what it is
2. `@EdgeStatHQ`
3. `@EdgeStat_io`
4. `@GetEdgeStat`

**Display name:** `EdgeStat` (add 🎯 if you want: `EdgeStat 🎯`)

**Bio (160 chars):**
> Quantitative sports-betting research. One Alpha Pick a day, every result
> public & graded on the box score. Receipts > hype. 21+ | Not betting advice

**Location:** `SoCal` · **Website:** `betting.bpleone.com`

**Avatar:** `assets/x-avatar.png` (400×400, the ⟁ mark on brand dark — also at
https://betting.bpleone.com/assets/x-avatar.png once deployed).
**Banner:** `assets/x-banner.png` (1500×500 — wordmark + "One pick a day. Every
result public — win or lose." + url + 21+ chip). No numbers on the banner by
design: records go stale, taglines don't.

Settings: enable 2FA; turn OFF "let people tag you in photos" (bot-magnet).

---

## 2. First three posts (day one, in order)

**Post 1 — the announcement (pin this):**
> Every morning we post ONE pick — the highest-EV play our model finds.
>
> Every result gets graded on the box score and posted the next day, win or lose.
> No deleted tweets. No "DM for picks." The whole ledger is public:
> betting.bpleone.com/track-record
>
> Current record: 45-7 · 87% · +50% ROI. Receipts start tomorrow. 21+

**Post 2 — the proof link (reply to Post 1, making a mini-thread):**
> How it works, in 60 seconds:
> • hand-coded models price every game & prop
> • isotonic calibration makes the probabilities honest
> • families that lose get hard-excluded (curation is the edge)
> • forward-tested on frozen rules — zero hindsight
> betting.bpleone.com/methodology

**Post 3 — the day's actual Alpha Pick** (from the machine — see §3).

---

## 3. The daily broadcast (already built — one tap)

- **9:03 AM PT**: the scheduled task `daily-alpha-tweet-9am-pt` hands you the
  ready-to-post tweet + one-tap link.
- Or anytime: open **betting.bpleone.com/alpha-pick** → "📣 Share today's pick"
  → **Post to X** (composer opens pre-filled; you hit Post).
- The format is engineered for growth — every post carries a fresh receipt:
  ```
  🎯 Alpha Pick of the Day

  Juan Soto — 3+ hits+runs+RBIs (-129) · model 56%

  Yesterday: Noelvi Marte under 3.5 HRR ✅ +0.73u
  Record: 45-7 · 87% hit · +50% ROI

  Full slate + receipts → betting.bpleone.com/alpha-pick

  21+ · not betting advice
  ```
- **Losses post too.** The ❌ days are what make the ✅ days credible. Never skip
  a down day — that's the whole brand.

---

## 4. Growth playbook (adapted from what worked for the research account)

The @Bpleonresearch blitz proved the loop: **reply-borrowing on the biggest live
posts in the niche → algo starts recommending you → followers compound.**

**Daily (10-15 min):**
1. Post the Alpha Pick (one tap, 9am PT).
2. Find 3-5 of the biggest LIVE posts on betting Twitter (search "MLB picks",
   "player props", big cappers' slates, breaking injury news) and leave a
   *substantive* reply — a number they don't have ("our model has this at 62%,
   the line implies 54% — value is real"), never "nice pick bro", never a link
   in the reply (link-spam kills reach; your profile carries the link).
3. Reply to EVERY comment on your own pick post within the first hour.

**Weekly:**
- One receipts thread: the week's picks, graded, with the running record.
- One educational post (Kelly, CLV, why hit-rate alone lies) → link Academy.

**Never:** buy followers, join engagement pods, post picks without stakes/odds,
claim guaranteed wins, or DM picks. One brand-safe rule: if a post would look
bad screenshotted on a losing week, don't post it.

**On catalyst days post manually** (learned the hard way on the research
account — scheduled sends silently failed on a big day).

---

## 5. Compliance guardrails (non-negotiable, every post)

- `21+` and `not betting advice` on every pick post (already baked into the composer).
- Never "lock", "guaranteed", "can't lose". "Highest-EV play our model found" is
  the ceiling.
- If gambling-problem topics come up: reply with 1-800-GAMBLER, nothing else.
- No affiliate links until the affiliate framework is actually signed (the site's
  affiliate-disclosure page governs).

---

## 6. The weekly receipts thread (built)

`weekly_receipts_thread.py` drafts a rolling trailing-week thread on every
pipeline run — hook (week record), day-by-day ✅/❌ receipts, closer with the
running record + link. Find it on **betting.bpleone.com/alpha-pick** under the
share card → "🧵 Weekly receipts thread": post tweet 1 with the 𝕏 button, then
Copy/paste each numbered tweet as a reply. Best cadence: Sunday or Monday morning.

## 7. Still available on request

- Auto-posting via the X API — needs YOU to create an X developer account + app
  keys first; until then, manual one-tap posting is the durable design.
