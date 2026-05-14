#!/usr/bin/env bash
# EdgeStat — one-shot deploy to GitHub Pages.
# Run this from inside the bpleone-site folder on Mac/Linux/WSL.
#
# Usage:
#   bash deploy.sh
#
# Prereqs: git installed, GitHub account, repo created at
#   github.com/bpleone/bpleone-betting (Step 1 in DEPLOY.md).

set -e

REPO_URL="https://github.com/Keyvaniath/bpleone-betting.git"
BRANCH="main"

echo "=== EdgeStat deploy → $REPO_URL ==="

# Sanity: confirm we're in the right folder.
if [ ! -f "index.html" ] || [ ! -f "CNAME" ]; then
  echo "❌ Run this from inside the bpleone-site folder (where index.html and CNAME live)."
  exit 1
fi

# Init if not already a git repo.
if [ ! -d ".git" ]; then
  echo "→ git init"
  git init -b "$BRANCH"
fi

# Stage + commit.
echo "→ git add ."
git add .

if git diff --cached --quiet; then
  echo "→ nothing to commit, working tree clean"
else
  echo "→ git commit"
  git commit -m "Deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi

# Configure remote (idempotent).
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "→ git remote add origin $REPO_URL"
  git remote add origin "$REPO_URL"
else
  echo "→ git remote set-url origin $REPO_URL"
  git remote set-url origin "$REPO_URL"
fi

# Push.
echo "→ git push -u origin $BRANCH"
git push -u origin "$BRANCH"

echo ""
echo "✅ Pushed. Next:"
echo "   1. Repo: $REPO_URL"
echo "   2. Settings → Pages → Source: 'Deploy from branch', Branch: '$BRANCH', Folder: /"
echo "   3. Wait 60s. Site will be at https://keyvaniath.github.io/bpleone-betting/"
echo "   4. Custom domain (CNAME file already in repo) → ensure DNS CNAME 'betting' → bpleone.github.io exists in Squarespace."
echo "   5. Final URL: https://betting.bpleone.com"
