# Quickstart — Deploy to betting.bpleone.com

You have 3 things to do. Should take 10 minutes total.

---

## 1. Create the GitHub repo (90 seconds)

1. Go to https://github.com/new (sign in if needed)
2. Repository name: `bpleone-betting`
3. Public ✓
4. Do NOT add README, .gitignore, or license
5. Click **Create repository**

Leave the page open. The next page shows you setup commands — ignore them, we have a script.

---

## 2. Run the deploy script (3 minutes)

The `bpleone-site` folder is on your computer (this is where you opened these files from).

### On Windows

1. Open File Explorer, navigate into the `bpleone-site` folder.
2. Double-click **`deploy.bat`**.
3. If prompted: type your GitHub username + password (or personal access token).

### On Mac/Linux

1. Open Terminal.
2. `cd` into the `bpleone-site` folder. Easiest: drag the folder into the Terminal window after typing `cd ` (with a trailing space), then press Enter.
3. Run: `bash deploy.sh`

### If you don't have git installed

- Windows: install from https://git-scm.com/download/win
- Mac: open Terminal, run `xcode-select --install`

---

## 3. Enable GitHub Pages + DNS (5 minutes)

### A. GitHub Pages

1. In your `bpleone-betting` repo on GitHub, click **Settings**.
2. Left sidebar → **Pages**.
3. Source: **Deploy from a branch**.
4. Branch: **main**, folder: **/ (root)**. Save.
5. Wait ~60 seconds. You should see `Your site is live at https://bpleone.github.io/bpleone-betting/`.
6. Click that URL — confirm the site loads.

### B. Squarespace DNS

This may already be set up from your Pokémon deploy. Check first:

1. Squarespace dashboard → **Settings** → **Domains** → click `bpleone.com`.
2. **DNS Settings** → look for a CNAME record with **Host = `betting`**.

**If `betting` CNAME exists**: edit its Data/Target to `bpleone.github.io` and save.

**If it doesn't exist**: click **Add Custom Record**:
- Host: `betting`
- Type: `CNAME`
- Data: `bpleone.github.io`
- TTL: default
- Save.

### C. Verify

1. Wait 5-15 minutes for DNS to propagate.
2. Visit https://betting.bpleone.com in a private/incognito window.
3. The EdgeStat dashboard should load.

If you get "There isn't a GitHub Pages site here" — DNS hasn't propagated yet, just wait.

---

## Done. Now update bpleone.com

On your Squarespace landing page, find the **Sports Betting / DFS** card and:

1. Make sure its link points to `https://betting.bpleone.com`.
2. Swap the "COMING SOON" pill for `● LIVE` (matching the Pokémon card style).

That's it — `betting.bpleone.com` is live alongside `pokemon.bpleone.com`.

---

## When you want to push updates later

After making any edits to the site:

```bash
# from inside bpleone-site
git add .
git commit -m "what changed"
git push
```

GitHub Pages auto-redeploys in ~30 seconds.

---

## Need more detail?

See `DEPLOY.md` for the long-form version with troubleshooting and the optional ML pipeline cron setup.
