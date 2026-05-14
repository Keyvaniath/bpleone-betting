@echo off
REM EdgeStat - one-shot deploy to GitHub Pages.
REM Run this from inside the bpleone-site folder on Windows.
REM
REM Usage (in PowerShell or CMD, from this folder):
REM   deploy.bat
REM
REM Prereqs: git installed (https://git-scm.com/download/win),
REM          GitHub account, repo created at github.com/bpleone/bpleone-betting

SET REPO_URL=https://github.com/Keyvaniath/bpleone-betting.git
SET BRANCH=main

echo === EdgeStat deploy to %REPO_URL% ===

REM Sanity check
IF NOT EXIST index.html (
  echo X Run this from inside the bpleone-site folder.
  exit /b 1
)
IF NOT EXIST CNAME (
  echo X CNAME file missing - cannot deploy without it.
  exit /b 1
)

REM Init if needed
IF NOT EXIST .git (
  echo Initializing git...
  git init -b %BRANCH%
)

echo Staging files...
git add .

git diff --cached --quiet
IF %ERRORLEVEL% NEQ 0 (
  echo Committing...
  git commit -m "Deploy: %DATE% %TIME%"
)

REM Set remote
git remote get-url origin >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
  git remote add origin %REPO_URL%
) ELSE (
  git remote set-url origin %REPO_URL%
)

echo Pushing to GitHub...
git push -u origin %BRANCH%

echo.
echo ============================================================
echo  PUSHED. Next:
echo  1. Open your repo on GitHub
echo  2. Settings -> Pages -> Source: Deploy from branch, branch: main, folder: /
echo  3. Wait 60 seconds, visit https://keyvaniath.github.io/bpleone-betting/
echo  4. Custom domain is already configured (CNAME file)
echo  5. Final URL: https://betting.bpleone.com
echo ============================================================
pause
