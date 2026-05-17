"""Generate WNBA + NHL real player pages (template-based, run once)."""
import os

root = os.path.join(os.path.dirname(__file__), "..")
with open(os.path.join(root, "nba-players-real.html"), "r", encoding="utf-8") as f:
    src = f.read()

# === WNBA: same basketball pattern, just swap title/file/color ===
wnba = src
wnba = wnba.replace('<title>NBA Player Props (REAL)', '<title>WNBA Player Props (REAL)')
wnba = wnba.replace('class="page-nba-real"', 'class="page-wnba-real"')
wnba = wnba.replace('nba-players-real.html" class="active">NBA Players (REAL)',
                     'nba-players-real.html">NBA Players (REAL)')
wnba = wnba.replace('wnba-players-real.html">WNBA Players (REAL)',
                     'wnba-players-real.html" class="active">WNBA Players (REAL)')
wnba = wnba.replace('data/real_player_props_nba.json', 'data/real_player_props_wnba.json')
wnba = wnba.replace('NBA Player Props', 'WNBA Player Props')
wnba = wnba.replace('NBA players', 'WNBA players')
wnba = wnba.replace('NBA starter', 'WNBA starter')
wnba = wnba.replace('NBA player props', 'WNBA player props')
wnba = wnba.replace('#c43e3e', '#fa6e21')
wnba = wnba.replace('rgba(196,62,62', 'rgba(250,110,33')
with open(os.path.join(root, "wnba-players-real.html"), "w", encoding="utf-8") as f:
    f.write(wnba)
print("Wrote wnba-players-real.html")

# === NHL: hockey stats (goals/assists/shots/points) ===
nhl = src
nhl = nhl.replace('<title>NBA Player Props (REAL)', '<title>NHL Player Props (REAL)')
nhl = nhl.replace('class="page-nba-real"', 'class="page-nhl-real"')
nhl = nhl.replace('nba-players-real.html" class="active">NBA Players (REAL)',
                   'nba-players-real.html">NBA Players (REAL)')
nhl = nhl.replace('nhl-players-real.html">NHL Players (REAL)',
                   'nhl-players-real.html" class="active">NHL Players (REAL)')
nhl = nhl.replace('data/real_player_props_nba.json', 'data/real_player_props_nhl.json')
nhl = nhl.replace('NBA Player Props', 'NHL Player Props')
nhl = nhl.replace('NBA players', 'NHL skaters')
nhl = nhl.replace('NBA starter', 'NHL skater')
nhl = nhl.replace('NBA player props', 'NHL player props')
nhl = nhl.replace('#c43e3e', '#0080a3')
nhl = nhl.replace('rgba(196,62,62', 'rgba(0,128,163')

# Replace basketball stat block w/ hockey
old_stat_block = '''        <div><span class="muted" style="font-size:10px;">MIN:</span> <strong>${s.min_per_game}</strong></div>
        <div><span class="muted" style="font-size:10px;">PTS:</span> <strong>${s.pts_per_game}</strong></div>
        <div><span class="muted" style="font-size:10px;">REB:</span> <strong>${s.reb_per_game}</strong></div>
        <div><span class="muted" style="font-size:10px;">AST:</span> <strong>${s.ast_per_game}</strong></div>
        <div><span class="muted" style="font-size:10px;">3PM:</span> <strong>${s.threes_per_game}</strong></div>
        <div><span class="muted" style="font-size:10px;">FG%:</span> <strong>${s.fg_pct}</strong></div>'''
new_stat_block = '''        <div><span class="muted" style="font-size:10px;">G/G:</span> <strong>${s.goals_per_game || 0}</strong></div>
        <div><span class="muted" style="font-size:10px;">A/G:</span> <strong>${s.assists_per_game || 0}</strong></div>
        <div><span class="muted" style="font-size:10px;">PTS/G:</span> <strong>${s.points_per_game || 0}</strong></div>
        <div><span class="muted" style="font-size:10px;">SOG/G:</span> <strong>${s.shots_per_game || 0}</strong></div>
        <div></div><div></div>'''
nhl = nhl.replace(old_stat_block, new_stat_block)
nhl = nhl.replace('${s.pts_per_game} PPG', '${s.points_per_game || 0} P/G')
nhl = nhl.replace('s.pts_per_game >= 25', '(s.points_per_game||0) >= 1.5')
nhl = nhl.replace('s.pts_per_game >= 20', '(s.points_per_game||0) >= 1.0')
nhl = nhl.replace('(p.stats.pts_per_game || 0) >= 20', '(p.stats.points_per_game || 0) >= 1.5')
nhl = nhl.replace('return pts >= 12 && pts < 20', 'return pts >= 0.8 && pts < 1.5')
nhl = nhl.replace('p.stats.pts_per_game || 0;\n    return pts',
                   'p.stats.points_per_game || 0;\n    return pts')
nhl = nhl.replace('(p.stats.pts_per_game || 0) < 12', '(p.stats.points_per_game || 0) < 0.8')
nhl = nhl.replace('20+ PPG', '1.5+ Pts/G')
nhl = nhl.replace('12-19 PPG', '0.8-1.5 Pts/G')
nhl = nhl.replace('Stars (20+', 'Top scorers (1.5+ Pts/G)')
nhl = nhl.replace('Role players (12-19', 'Mid (0.8-1.5')
nhl = nhl.replace('Bench (under 12)', 'Depth (under 0.8)')
nhl = nhl.replace('Top Scorer', 'Top Skater')
with open(os.path.join(root, "nhl-players-real.html"), "w", encoding="utf-8") as f:
    f.write(nhl)
print("Wrote nhl-players-real.html")
