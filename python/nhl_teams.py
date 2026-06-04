"""
EdgeStat -- shared NHL team-name -> abbreviation resolver.

nhl_state serves FULL scoreboard names ("Vegas Golden Knights"), but the prop
generators key players/goalies by abbrev ("VGK"). Several generators matched via
name[:3] ("VEG"), which is wrong for ~half the league (VGK, TBL, WSH, NJD, NYR,
SJS, CBJ, LAK, WPG, MTL, NSH, CGY, STL, NYI ...) and SILENTLY DROPPED those teams
from the slate. This single resolver fixes that bug class in one place.
"""
from __future__ import annotations

TEAM_FULL = {
    "anaheim ducks": "ANA", "boston bruins": "BOS", "buffalo sabres": "BUF",
    "calgary flames": "CGY", "carolina hurricanes": "CAR", "chicago blackhawks": "CHI",
    "colorado avalanche": "COL", "columbus blue jackets": "CBJ", "dallas stars": "DAL",
    "detroit red wings": "DET", "edmonton oilers": "EDM", "florida panthers": "FLA",
    "los angeles kings": "LAK", "minnesota wild": "MIN", "montreal canadiens": "MTL",
    "montréal canadiens": "MTL", "nashville predators": "NSH", "new jersey devils": "NJD",
    "new york islanders": "NYI", "new york rangers": "NYR", "ottawa senators": "OTT",
    "philadelphia flyers": "PHI", "pittsburgh penguins": "PIT", "san jose sharks": "SJS",
    "seattle kraken": "SEA", "st. louis blues": "STL", "st louis blues": "STL",
    "tampa bay lightning": "TBL", "toronto maple leafs": "TOR", "utah hockey club": "UTA",
    "utah mammoth": "UTA", "vancouver canucks": "VAN", "vegas golden knights": "VGK",
    "washington capitals": "WSH", "winnipeg jets": "WPG",
}

# Common abbrev aliases / already-abbreviated inputs that aren't a team's name[:3].
_VALID_ABBR = set(TEAM_FULL.values())


def abbr(name: str) -> str:
    """Resolve a team name (full scoreboard name OR an abbrev) to its abbrev.

    Returns "" for empty input. Falls back to an UPPERCASED first-3-letters only
    when the input is neither a known full name nor an already-valid abbrev."""
    if not name:
        return ""
    s = name.strip()
    key = s.lower()
    if key in TEAM_FULL:
        return TEAM_FULL[key]
    up = s.upper()
    if up in _VALID_ABBR:        # already an abbrev (e.g. "VGK")
        return up
    return up[:3]                # last-resort fallback


if __name__ == "__main__":
    for n in ("Vegas Golden Knights", "Carolina Hurricanes", "VGK", "Tampa Bay Lightning",
              "Washington Capitals", "New Jersey Devils", "St. Louis Blues", ""):
        print(f"{n!r:28} -> {abbr(n)!r}")
