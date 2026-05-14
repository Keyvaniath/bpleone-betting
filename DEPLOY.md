# Deployment Guide — betting.bpleone.com

Goal: get this site live at `betting.bpleone.com`, alongside `pokemon.bpleone.com`.

Estimated time: 10-15 minutes.

---

## Step 1 — Create the GitHub repo

1. Go to https://github.com/new
2. Name: `bpleone-betting`
3. Visibility: **Public** (required for free GitHub Pages)
4. Do NOT initialize with README, .gitignore, or license (we have our own)
5. Click "Create repository"

---

## Step 2 — Upload the files (easiest path: web UI drag & drop)

1. On the new empty repo page, click **"uploading an existing file"** (the link in the middle of the page).
2. In a separate window, open the `bpleone-site` folder on your computer.
3. **Select ALL files** inside `bpleone-site/` (NOT the folder itself — the contents). On Mac/Windows: Cmd/Ctrl-A inside the folder.
4. Drag them all into the GitHub upload window.
   - This includes hidden files like `.gitignore`, `.nojekyll`, `.github/`, and `CNAME` — make sure your file explorer is showing hidden files.
   - If hidden files are tricky, see "Alternate: git CLI" below.
5. Scroll down, commit message: `Initial deploy`
6. Click **"Commit changes"**.

### Alternate: git CLI (if you're comfortable)

```bash
cd path/to/bpleone-site
git init -b main
git add .
git commit -m "Initial deploy"
git remote add origin https://github.com/bpleone/bpleone-betting.git
git push -u origin main
```

---

## Step 3 — Enable GitHub Pages

1. In your repo, go to **Settings** (top tab) → **Pages** (left sidebar).
2. Source: **Deploy from a branch**
3. Branch: **main**, folder: **/ (root)**
4. Click **Save**.
5. Wait ~60 seconds. GitHub will give you a URL like:
   `https://bpleone.github.io/bpleone-betting/`
6. Visit that URL — the site should load.

---

## Step 4 — Custom domain (betting.bpleone.com)

The `CNAME` file in the repo already tells GitHub Pages your custom domain. You just need DNS.

### Check if the subdomain already exists in Squarespace

1. Squarespace → **Settings** → **Domains** → click `bpleone.com`.
2. Click **DNS Settings**.
3. Look for an existing record where **Host = `betting`** (type CNAME).
   - If it exists and points to `<somewhere>.github.io`, you may be able to just **edit its data** to `bpleone.github.io`.
   - If it points to Pokémon's location, leave Pokémon's alone — that's a DIFFERENT subdomain (`pokemon`).

### Add the CNAME for betting (if not present)

In Squarespace DNS Settings, click **Add Custom Record**:

| Field | Value |
|---|---|
| Host | `betting` |
| Type | `CNAME` |
| Data / Target | `bpleone.github.io` |
| TTL | 3600 (or default) |

Save.

### Verify in GitHub

1. Back in your repo → Settings → Pages.
2. Under "Custom domain", you should see `betting.bpleone.com`.
3. Check **"Enforce HTTPS"** (may need to wait 5-30 min for SSL cert to provision).

---

## Step 5 — Verify

1. Wait 5-10 minutes for DNS propagation.
2. Open https://betting.bpleone.com in a private/incognito window.
3. You should see the EdgeStat dashboard with the dark theme.

If you see a 404 or "There isn't a GitHub Pages site here":
- DNS hasn't propagated yet. Wait 15 more minutes.
- Or the CNAME file got missed in the upload. Confirm `CNAME` exists in the repo root with contents `betting.bpleone.com`.

---

## Step 6 — Update Squarespace landing page

On the bpleone.com landing page (the screenshot you sent), update the Sports Betting / DFS card:

1. Change `betting.bpleone.com` link target (already correct, just confirm it's a clickable link).
2. Change the status pill from `COMING SOON` to `● LIVE` (matching the Pokémon card style).
3. Optionally add a short marketing summary that matches what's on the new site:
   > Quant-grade sports betting analytics. ML-driven probability models for MLB. Play of the Day + sharp money flow + live in-game win expectancy.

---

## Step 7 — Optional: Wire the daily ML pipeline

The repo includes `.github/workflows/daily-pipeline.yml` which can auto-refresh data on a cron. To enable it:

1. Sign up for The Odds API at https://the-odds-api.com/ ($30/mo for the MLB tier).
2. In your repo: Settings → Secrets and variables → Actions → **New repository secret**.
3. Name: `ODDS_API_KEY`, Value: (paste your key).
4. Settings → Actions → General → Workflow permissions: **Read and write**.
5. The cron will fire 3x daily and commit fresh data to `data/today.json`.

Without this, the site shows the seeded demo data from `js/data.js` — which is fine for launch.

---

## Troubleshooting

**"Domain's DNS record could not be retrieved"** in GitHub Pages settings:
DNS hasn't propagated. Wait 15-30 min. You can confirm propagation with `dig betting.bpleone.com` from a terminal or https://dnschecker.org.

**SSL certificate not ready**:
GitHub auto-provisions Let's Encrypt certs after DNS resolves. Can take up to 24 hours but usually under 30 min. Uncheck and re-check "Enforce HTTPS" if it's stuck.

**Files won't upload (hidden files like .github):**
On Mac: Cmd+Shift+. to show hidden files. On Windows: View → Show → Hidden items.

Or use git CLI (Step 2 alternate).

---

## What you'll have when done

- **bpleone.com** → Squarespace marketing site (unchanged)
- **pokemon.bpleone.com** → your existing Pokémon TCG tool
- **betting.bpleone.com** → this EdgeStat sports betting analytics site

All on the same root domain, all in your control.
