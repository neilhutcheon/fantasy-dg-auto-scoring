#!/usr/bin/env python3
"""
Fantasy Disc Golf Automation Script
Fetches PDGA scores and calculates fantasy points for your league.

Usage:
  python fantasy_disc_golf.py --tourn-id 12345 --round 1 --division MPO
  python fantasy_disc_golf.py --tourn-id 12345 --final   # full tournament scoring
  python fantasy_disc_golf.py --lookup-id "Champions Cup" --year 2026

Setup:
  pip install requests gspread google-auth

Discord: Set DISCORD_WEBHOOK env var, or paste URL directly in CONFIG below.
Google Sheets: Set GOOGLE_SHEETS_ID env var, or paste ID directly in CONFIG below.
  - Share your sheet with your service account email (from credentials.json)
"""

import requests
import json
import os
import sys
import argparse
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG — edit these
# ─────────────────────────────────────────────

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
GOOGLE_SHEETS_ID = os.environ.get("GOOGLE_SHEETS_ID", "")
GOOGLE_CREDS_FILE = "credentials.json"  # path to your Google service account JSON

# ─────────────────────────────────────────────
# ROSTER — derived from your Teams sheet
# ─────────────────────────────────────────────

TEAMS = {
    "Scoober Steves": {
        "FPO": ["Evelina Salonen", "Cat Allen"],
        "MPO": ["Gannon Buhr", "Ricky Wysocki", "Chris Dickerson"],
    },
    "Rob's Roll-Aways": {
        "FPO": ["Ohn Scoggins", "Paige Pierce", "Anniken Steen"],
        "MPO": ["Adam Hammes", "Evan Smith"],
    },
    "Brian's Bogiers": {
        "FPO": ["Ella Hansen", "Rebecca Cox"],
        "MPO": ["Calvin Heimburg", "Kyle Klein", "Gavin Babcock"],
    },
    "Donny's Diamonds": {
        "FPO": ["Holyn Handley", "Val Mandujano", "Jessica Gurthie"],
        "MPO": ["Niklas Anttila", "Andrew Marwede", "Paul Krans"],
    },
    "Sage": {
        "FPO": ["Missy Gannon", "Henna Blomroos"],
        "MPO": ["Aaron Gossage", "Cole Redalan", "Luke Taylor", "Corey Ellis"],
    },
    "Rem's Rippers": {
        "FPO": ["Silva Saarinen", "Hailey King"],
        "MPO": ["Isaac Robinson", "Ezra Robinson"],
    },
    "Caldwell's Chuckers": {
        "FPO": ["Cadence Burge", "Hanna Huynh", "Rebecca Don", "Lisa Fajkus"],
        "MPO": ["Anthony Barela", "Ezra Aderhold", "Sullivan Tipton"],
    },
    "Neil's Nukes": {
        "FPO": ["Kat Mertsch", "Sofia Donnecke", "Anneli Tougjas Manniste"],
        "MPO": ["Paul McBeth", "Simon Lizotte", "Austin Turner"],
    },
}

# Tournament schedule with PDGA IDs (fill in as the season progresses)
# Find IDs at: https://api.pdga.com/services/json/event?tier=ES,NT&start_date=2026-01-01&end_date=2026-12-31
SCHEDULE = {
    "Supreme Flight Open":          {"id": 101154, "type": "individual", "dates": "Feb 27-Mar 1"},
    "Big Easy":                     {"id": None,   "type": "individual", "dates": "Mar 13-15"},
    "Queen City Classic":           {"id": None,   "type": "individual", "dates": "Mar 27-29"},
    "PDGA Champions Cup":           {"id": None,   "type": "full",       "dates": "Apr 9-12"},
    "Jonesboro Open":               {"id": None,   "type": "individual", "dates": "Apr 17-19"},
    "Kansas City Wide Open":        {"id": None,   "type": "individual", "dates": "Apr 24-26"},
    "Open at Austin":               {"id": None,   "type": "full",       "dates": "May 7-10"},
    "OTB Open":                     {"id": None,   "type": "full",       "dates": "May 21-24"},
    "Northwest Championship":       {"id": None,   "type": "full",       "dates": "Jun 4-7"},
    "European Disc Golf Festival":  {"id": None,   "type": "full",       "dates": "Jun 18-21"},
    "Swedish Open":                 {"id": None,   "type": "individual", "dates": "Jun 26-28"},
    "Ale Open":                     {"id": None,   "type": "individual", "dates": "Jul 3-5"},
    "Heinola Open":                 {"id": None,   "type": "individual", "dates": "Jul 10-12"},
    "US Women's Championship":      {"id": None,   "type": "full",       "dates": "Jul 16-19", "special": "womens"},
    "Ledgestone":                   {"id": None,   "type": "full",       "dates": "Jul 30-Aug 2"},
    "Discmania Challenge":          {"id": None,   "type": "individual", "dates": "Aug 7-9"},
    "Preserve Championship":        {"id": None,   "type": "individual", "dates": "Aug 14-16"},
    "PDGA World's":                 {"id": None,   "type": "full",       "dates": "Aug 26-30", "special": "double"},
    "Idlewild":                     {"id": None,   "type": "individual", "dates": "Sep 4-6"},
    "GMC":                          {"id": None,   "type": "full",       "dates": "Sep 17-20"},
    "MVP Open":                     {"id": None,   "type": "full",       "dates": "Sep 24-27"},
    "USDGC":                        {"id": None,   "type": "full",       "dates": "Oct 8-11",  "special": "double"},
}

# ─────────────────────────────────────────────
# SCORING RULES
# ─────────────────────────────────────────────

def individual_placement_points(place, division="MPO"):
    """Points awarded for finishing position in either division."""
    if place == 1:
        return 7
    elif place <= 3:
        return 4
    elif place <= 7:
        return 2
    elif place <= 16 and division == "MPO":
        return 1
    elif place <= 12 and division == "FPO":
        return 1
    return 0

MINI_GAME_POINTS = {1: 10, 2: 7, 3: 5, 4: 3}
WEAK_ROSTER_PENALTY = 3  # extra strokes over worst opponent's top-3

# ─────────────────────────────────────────────
# PDGA API
# ─────────────────────────────────────────────

PDGA_LIVE_API = "https://www.pdga.com/apps/tournament/live-api/live_results_fetch_round"
PDGA_EVENT_API = "https://api.pdga.com/services/json/event"

def fetch_round_scores(tourn_id, division, round_num):
    """Fetch scores for a specific round from PDGA live API."""
    resp = requests.get(PDGA_LIVE_API, params={
        "TournID": tourn_id,
        "Division": division,
        "Round": round_num,
    }, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data["data"]["scores"]

def fetch_final_scores(tourn_id, division):
    """Fetch final tournament results (use round 99 which gives cumulative)."""
    # Try progressively higher round numbers to find the final
    for round_num in [4, 3, 2, 1]:
        try:
            scores = fetch_round_scores(tourn_id, division, round_num)
            if scores and any(s.get("Completed") for s in scores):
                return scores
        except Exception:
            continue
    return []

def lookup_tournament_id(name, year=2026):
    """Look up a PDGA tournament ID by name."""
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    resp = requests.get(PDGA_EVENT_API, params={
        "tier": "ES,NT,M",
        "start_date": start,
        "end_date": end,
        "limit": 100,
    }, headers={"Cookie": "session_name=sessid"}, timeout=15)
    if resp.status_code != 200:
        print(f"Warning: Could not reach PDGA events API (status {resp.status_code})")
        return None
    events = resp.json()
    name_lower = name.lower()
    for event in events:
        if name_lower in event.get("name", "").lower():
            print(f"Found: {event['name']} → TournID {event['tournament_id']}")
            return event["tournament_id"]
    print(f"No match found for '{name}'")
    return None

# ─────────────────────────────────────────────
# SCORE CALCULATION
# ─────────────────────────────────────────────

def normalize_name(name):
    """Lowercase + strip for fuzzy matching."""
    return name.lower().strip()

def find_player_result(scores, player_name):
    """Find a player's result in the scores list by name (fuzzy)."""
    target = normalize_name(player_name)
    for s in scores:
        if normalize_name(s["Name"]) == target:
            return s
        # Try last name match as fallback
        last = normalize_name(s["LastName"])
        first = normalize_name(s["FirstName"])
        if target in f"{first} {last}" or f"{first} {last}" in target:
            return s
    return None

def calculate_individual_points(scores_mpo, scores_fpo, event_name=""):
    """
    Calculate individual placement fantasy points for all teams.
    Returns dict: {team_name: {player_name: {place, score, points}}}
    """
    results = {}

    for team_name, roster in TEAMS.items():
        results[team_name] = {"MPO": {}, "FPO": {}, "total_placement_points": 0}

        for player in roster["MPO"]:
            result = find_player_result(scores_mpo, player)
            if result:
                place = result["RunningPlace"]
                pts = individual_placement_points(place, "MPO")
                results[team_name]["MPO"][player] = {
                    "place": place,
                    "score": result["ToPar"],
                    "total": result["GrandTotal"],
                    "points": pts,
                    "completed": bool(result.get("Completed")),
                }
                results[team_name]["total_placement_points"] += pts

        for player in roster["FPO"]:
            result = find_player_result(scores_fpo, player)
            if result:
                place = result["RunningPlace"]
                pts = individual_placement_points(place, "FPO")
                results[team_name]["FPO"][player] = {
                    "place": place,
                    "score": result["ToPar"],
                    "total": result["GrandTotal"],
                    "points": pts,
                    "completed": bool(result.get("Completed")),
                }
                results[team_name]["total_placement_points"] += pts

    return results

def get_team_score(team_result, division, top_n=3):
    """Get the combined score of the top N players for team mini-game."""
    players = team_result[division]
    if not players:
        return None
    sorted_players = sorted(players.items(), key=lambda x: x[1]["total"])
    top = sorted_players[:top_n]
    return sum(p[1]["total"] for p in top), [p[0] for p in top]

def calculate_mini_game_points(individual_results, is_double=False):
    """
    Calculate team mini-game points (best combined top-3 MPO + top-3 FPO scores).
    Returns sorted team standings with mini-game points.
    """
    team_totals = {}

    # Gather all top-3 scores for weak roster penalty calculation
    all_mpo_top3 = []
    all_fpo_top3 = []
    for team_name, result in individual_results.items():
        mpo = get_team_score(result, "MPO")
        fpo = get_team_score(result, "FPO")
        if mpo:
            all_mpo_top3.append(mpo[0])
        if fpo:
            all_fpo_top3.append(fpo[0])

    worst_mpo = max(all_mpo_top3) if all_mpo_top3 else None
    worst_fpo = max(all_fpo_top3) if all_fpo_top3 else None

    for team_name, result in individual_results.items():
        mpo = get_team_score(result, "MPO")
        fpo = get_team_score(result, "FPO")

        # Apply weak roster penalty if fewer than 3 players
        mpo_score = mpo[0] if mpo else (worst_mpo + WEAK_ROSTER_PENALTY if worst_mpo else 999)
        fpo_score = fpo[0] if fpo else (worst_fpo + WEAK_ROSTER_PENALTY if worst_fpo else 999)
        mpo_players = mpo[1] if mpo else ["(penalty)"]
        fpo_players = fpo[1] if fpo else ["(penalty)"]

        combined = mpo_score + fpo_score
        team_totals[team_name] = {
            "combined_score": combined,
            "mpo_score": mpo_score,
            "fpo_score": fpo_score,
            "mpo_players": mpo_players,
            "fpo_players": fpo_players,
            "mini_game_points": 0,
        }

    # Rank teams and assign mini-game points
    ranked = sorted(team_totals.items(), key=lambda x: x[1]["combined_score"])
    for i, (team_name, data) in enumerate(ranked):
        place = i + 1
        pts = MINI_GAME_POINTS.get(place, 0)
        if is_double:
            pts *= 2
        team_totals[team_name]["mini_game_place"] = place
        team_totals[team_name]["mini_game_points"] = pts

    return team_totals

# ─────────────────────────────────────────────
# OUTPUT FORMATTING
# ─────────────────────────────────────────────

def format_score(to_par):
    if to_par == 0:
        return "E"
    return f"+{to_par}" if to_par > 0 else str(to_par)

def build_discord_message(event_name, event_type, individual_results, mini_game=None, is_live=True):
    """Build a Discord message summarizing fantasy scores for an event."""
    status = "🔴 LIVE" if is_live else "✅ FINAL"
    lines = [f"## 🥏 Fantasy Disc Golf — {event_name} ({status})\n"]

    # Individual placement points summary
    lines.append("### 📊 Individual Placement Points")
    sorted_teams = sorted(
        individual_results.items(),
        key=lambda x: -x[1]["total_placement_points"]
    )
    for team_name, result in sorted_teams:
        pts = result["total_placement_points"]
        notables = []
        for div in ["MPO", "FPO"]:
            for player, pdata in result[div].items():
                if pdata["points"] > 0:
                    notables.append(f"{player} (#{pdata['place']}, {format_score(pdata['score'])}, +{pdata['points']}pts)")
        notable_str = ", ".join(notables) if notables else "no points yet"
        lines.append(f"**{team_name}**: {pts} pts — {notable_str}")

    # Mini-game results (full tournaments only)
    if mini_game and event_type == "full":
        lines.append("\n### 🏆 Team Mini-Game (Top 3 MPO + Top 3 FPO)")
        mg_sorted = sorted(mini_game.items(), key=lambda x: x[1]["mini_game_place"])
        for team_name, mg in mg_sorted:
            place_emoji = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣"][mg["mini_game_place"]-1]
            mpo_str = ", ".join(mg["mpo_players"])
            fpo_str = ", ".join(mg["fpo_players"])
            lines.append(
                f"{place_emoji} **{team_name}** — {mg['combined_score']} total "
                f"(MPO: {mg['mpo_score']} [{mpo_str}] | FPO: {mg['fpo_score']} [{fpo_str}]) "
                f"→ **{mg['mini_game_points']} pts**"
            )

    lines.append(f"\n_Updated: {datetime.now().strftime('%b %d %I:%M %p')}_")
    return "\n".join(lines)

def post_to_discord(message):
    """Post a message to Discord via webhook."""
    if DISCORD_WEBHOOK == "YOUR_DISCORD_WEBHOOK_URL_HERE":
        print("[Discord] Webhook not configured, printing message instead:\n")
        print(message)
        return
    resp = requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
    if resp.status_code in (200, 204):
        print("✅ Posted to Discord")
    else:
        print(f"❌ Discord error: {resp.status_code} {resp.text}")

def update_google_sheets(event_name, individual_results, mini_game=None):
    """Update the SEASON SCORE tab in Google Sheets."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("⚠️  gspread not installed. Run: pip install gspread google-auth")
        return

    if not os.path.exists(GOOGLE_CREDS_FILE):
        print(f"⚠️  Google credentials not found at '{GOOGLE_CREDS_FILE}'. Skipping Sheets update.")
        return

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)
    ws = sh.worksheet("SEASON SCORE")

    # Find the event row
    col_a = ws.col_values(1)
    try:
        event_row = next(i+1 for i, v in enumerate(col_a) if event_name.lower() in v.lower())
    except StopIteration:
        print(f"⚠️  Could not find '{event_name}' in SEASON SCORE sheet. Skipping update.")
        return

    # Column order matches sheet: Scoober Steves, Rob's, Brian's, Donny's, Sage, Rem's, Caldwell's, Neil's
    team_order = [
        "Scoober Steves", "Rob's Roll-Aways", "Brian's Bogiers", "Donny's Diamonds",
        "Sage", "Rem's Rippers", "Caldwell's Chuckers", "Neil's Nukes"
    ]

    row_values = []
    for team in team_order:
        pts = individual_results[team]["total_placement_points"]
        if mini_game and team in mini_game:
            pts += mini_game[team]["mini_game_points"]
        row_values.append(pts)

    # Update columns B through I (indices 2-9)
    ws.update(f"B{event_row}:I{event_row}", [row_values])
    print(f"✅ Updated Google Sheets row {event_row} ({event_name})")

def print_summary(event_name, event_type, individual_results, mini_game=None):
    """Print a readable summary to the terminal."""
    print(f"\n{'='*60}")
    print(f"  {event_name.upper()} — FANTASY RESULTS")
    print(f"{'='*60}")

    print("\n📍 Individual Placement Points:")
    for team_name, result in sorted(individual_results.items(), key=lambda x: -x[1]["total_placement_points"]):
        print(f"  {team_name}: {result['total_placement_points']} pts")
        for div in ["MPO", "FPO"]:
            for player, pdata in sorted(result[div].items(), key=lambda x: x[1]["place"]):
                flag = "✓" if pdata["completed"] else "~"
                print(f"    {flag} [{div}] {player}: #{pdata['place']} ({format_score(pdata['score'])}) → {pdata['points']} pts")

    if mini_game and event_type == "full":
        print("\n🏆 Team Mini-Game:")
        for team_name, mg in sorted(mini_game.items(), key=lambda x: x[1]["mini_game_place"]):
            print(f"  #{mg['mini_game_place']} {team_name}: {mg['combined_score']} combined → {mg['mini_game_points']} pts")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(tourn_id, event_name, event_type, round_num=None, is_final=False, double_points=False, post_discord=True, update_sheets=True):
    """Main run function."""
    print(f"\n🥏 Fetching scores for {event_name} (TournID: {tourn_id})...")

    if is_final or round_num is None:
        print("  Mode: Final results")
        scores_mpo = fetch_final_scores(tourn_id, "MPO")
        scores_fpo = fetch_final_scores(tourn_id, "FPO")
        is_live = False
    else:
        print(f"  Mode: Round {round_num} (live)")
        scores_mpo = fetch_round_scores(tourn_id, "MPO", round_num)
        scores_fpo = fetch_round_scores(tourn_id, "FPO", round_num)
        is_live = True

    if not scores_mpo and not scores_fpo:
        print("❌ No scores returned. Check the TournID and round number.")
        return

    print(f"  Got {len(scores_mpo)} MPO scores, {len(scores_fpo)} FPO scores")

    individual_results = calculate_individual_points(scores_mpo, scores_fpo, event_name)

    mini_game = None
    if event_type == "full":
        mini_game = calculate_mini_game_points(individual_results, is_double=double_points)

    print_summary(event_name, event_type, individual_results, mini_game)

    if post_discord:
        msg = build_discord_message(event_name, event_type, individual_results, mini_game, is_live)
        post_to_discord(msg)

    if update_sheets and is_final:
        update_google_sheets(event_name, individual_results, mini_game)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fantasy Disc Golf Score Fetcher")
    parser.add_argument("--tourn-id", type=int, help="PDGA Tournament ID")
    parser.add_argument("--event", type=str, help="Event name (must match SCHEDULE keys)")
    parser.add_argument("--round", type=int, dest="round_num", help="Round number (omit for final)")
    parser.add_argument("--final", action="store_true", help="Fetch final results")
    parser.add_argument("--lookup-id", type=str, help="Look up tournament ID by name")
    parser.add_argument("--no-discord", action="store_true", help="Skip Discord post")
    parser.add_argument("--no-sheets", action="store_true", help="Skip Google Sheets update")
    args = parser.parse_args()

    if args.lookup_id:
        lookup_tournament_id(args.lookup_id)
        sys.exit(0)

    # Resolve event from schedule or direct args
    tourn_id = args.tourn_id
    event_name = args.event or "Unknown Event"
    event_type = "individual"
    double = False

    if args.event and args.event in SCHEDULE:
        ev = SCHEDULE[args.event]
        tourn_id = tourn_id or ev["id"]
        event_type = ev["type"]
        double = ev.get("special") == "double"
        event_name = args.event

    if not tourn_id:
        print("❌ No tournament ID provided. Use --tourn-id or fill in SCHEDULE dict.")
        sys.exit(1)

    run(
        tourn_id=tourn_id,
        event_name=event_name,
        event_type=event_type,
        round_num=args.round_num,
        is_final=args.final,
        double_points=double,
        post_discord=not args.no_discord,
        update_sheets=not args.no_sheets,
    )
