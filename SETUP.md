# Fantasy Disc Golf Automation — Setup Guide

## What this does
- Fetches live/final PDGA scores for your league's tracked players
- Calculates individual placement points and team mini-game points
- Posts a summary to Discord
- Updates the SEASON SCORE tab in your Google Sheet

---

## Quick Start (local test)

```bash
pip install requests gspread google-auth

# Test with Supreme Flight Open (no Discord/Sheets needed first)
python fantasy_disc_golf.py --tourn-id 101154 --event "Supreme Flight Open" --no-discord --no-sheets

# Live round update
python fantasy_disc_golf.py --tourn-id 101154 --event "Supreme Flight Open" --round 1

# Final results
python fantasy_disc_golf.py --tourn-id 101154 --event "Supreme Flight Open" --final

# Look up a tournament ID by name
python fantasy_disc_golf.py --lookup-id "Champions Cup"
```

---

## Discord Setup (5 minutes)

1. In your Discord server, go to **Server Settings → Integrations → Webhooks**
2. Click **New Webhook**, name it "Fantasy Disc Golf Bot", pick your channel
3. Copy the webhook URL
4. Set it in the script: replace `YOUR_DISCORD_WEBHOOK_URL_HERE` in the CONFIG block,
   or set the environment variable: `export DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."`

---

## Google Sheets Setup (15 minutes)

1. Go to https://console.cloud.google.com
2. Create a new project (e.g. "Fantasy Disc Golf")
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts** → Create service account
5. Create a JSON key and download it as `credentials.json` in the same folder as the script
6. Share your Google Sheet with the service account email (looks like `xxx@xxx.iam.gserviceaccount.com`)
   — give it **Editor** access

---

## GitHub Actions Setup (automated scheduling)

This lets it run automatically every weekend without you doing anything.

1. Push this repo to GitHub
2. Go to **Settings → Secrets and Variables → Actions** and add:
   - `DISCORD_WEBHOOK` — your Discord webhook URL
   - `GOOGLE_SHEETS_ID` — the ID from your Google Sheet URL (the part between `/d/` and `/edit`)
   - `GOOGLE_CREDENTIALS` — paste the full contents of your `credentials.json` file
3. The workflow file is already at `.github/workflows/fantasy_disc_golf_github_action.yml`

---

## Discord Bot Setup (trigger scoring from Discord)

Instead of manually editing workflow files, use the Discord bot to trigger scoring with a simple `/score` command.

### 1. Create a Discord Bot Application
1. Go to https://discord.com/developers/applications
2. Click **New Application**, name it "Fantasy Disc Golf Bot"
3. Go to the **Bot** tab → click **Reset Token** → copy the token (you'll need this)
4. Under **Privileged Gateway Intents**, no special intents are needed
5. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Use Slash Commands`
6. Copy the generated URL and open it in your browser to invite the bot to your server

### 2. Create a GitHub Personal Access Token
1. Go to https://github.com/settings/tokens → **Generate new token (classic)**
2. Give it the `repo` scope (needed to trigger workflows)
3. Copy the token

### 3. Set Environment Variables
```bash
export DISCORD_BOT_TOKEN="your-discord-bot-token"
export GITHUB_TOKEN="your-github-personal-access-token"
export GITHUB_REPO="yourusername/fantasy-dg-auto-scoring"
```

### 4. Run the Bot
```bash
pip install -r requirements.txt
python discord_bot.py
```

### 5. Use It!
In any channel your bot can see, type:
```
/score tourn_id:101154 event_name:Supreme Flight Open
/score tourn_id:101154 event_name:Supreme Flight Open final:True
/score-help
```

### Hosting (keep it running 24/7)
The bot needs to stay online to listen for commands. Free options:
- **[Railway](https://railway.app)** — free tier supports small bots
- **[Render](https://render.com)** — free web service tier
- **[Fly.io](https://fly.io)** — free for small apps

Set the same 3 environment variables (`DISCORD_BOT_TOKEN`, `GITHUB_TOKEN`, `GITHUB_REPO`) in your hosting platform's dashboard.

---

## Each Tournament Weekend — Checklist

1. **Find the PDGA Tournament ID** (run `--lookup-id "Event Name"` or check pdga.com/tour/event/XXXXX)
2. **Update SCHEDULE dict** in `fantasy_disc_golf.py` with the ID
3. **Commit and push** — GitHub Actions will auto-run every 2 hours Fri-Sun
4. **Monday**: Run with `--final` flag to post final results and update the sheet

---

## Roster Updates

Edit the `TEAMS` dict in `fantasy_disc_golf.py` when roster changes happen mid-season.
The draft sheet shows your current rosters are only partially filled — add remaining picks after your draft completes.

---

## Known Limitations / Manual Steps Still Needed

- **Hole-in-one bonus** (1pt): The API does include hole scores, but tracking HIO requires
  checking every hole score == 1 on a par 3. This CAN be automated — let me know and I'll add it.
- **Cut rule penalty**: Automatically applied for teams with fewer than 3 MPO/FPO players competing.
  If a player misses the cut, you'll need to manually flag them as not competing.
- **US Women's Championship**: Top 4 FPO scores count instead of top 3 — update `get_team_score()` call for that event.
- **PDGA Worlds / USDGC**: Double mini-game points are handled automatically via `"special": "double"` in SCHEDULE.
