#!/usr/bin/env python3
"""
Fantasy Disc Golf — Discord Bot
Listens for slash commands and triggers GitHub Actions to run scoring.

Required environment variables:
  DISCORD_BOT_TOKEN  — Your Discord bot token
  GITHUB_TOKEN       — GitHub Personal Access Token (needs 'repo' scope)
  GITHUB_REPO        — e.g. "youruser/fantasy-dg-auto-scoring"
"""

import os
import discord
from discord import app_commands
import requests

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "") # 
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")  # e.g. "neilhutcheon/fantasy-dg-auto-scoring" 
WORKFLOW_FILENAME = "fantasy_disc_golf_github_action.yml"

# ─────────────────────────────────────────────
# GITHUB API
# ─────────────────────────────────────────────

def trigger_github_workflow(tourn_id: int, event_name: str, final: bool = False) -> dict:
    """
    Trigger the GitHub Actions workflow via workflow_dispatch.
    Returns a dict with 'success' (bool) and 'message' (str).
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return {"success": False, "message": "GitHub token or repo not configured."}

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILENAME}/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "ref": "main",
        "inputs": {
            "tourn_id": str(tourn_id),
            "event_name": event_name,
            "final": "true" if final else "false",
        },
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 204:
        return {"success": True, "message": "Workflow triggered successfully."}
    else:
        return {"success": False, "message": f"GitHub API error {resp.status_code}: {resp.text}"}

# ─────────────────────────────────────────────
# DISCORD BOT
# ─────────────────────────────────────────────

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@tree.command(name="score", description="Trigger fantasy disc golf scoring for a tournament")
@app_commands.describe(
    tourn_id="PDGA Tournament ID (e.g. 101154)",
    event_name="Event name matching the SCHEDULE (e.g. 'Supreme Flight Open')",
    final="Fetch final results instead of live scores",
)
async def score_command(
    interaction: discord.Interaction,
    tourn_id: int,
    event_name: str,
    final: bool = False,
):
    mode = "🏁 Final" if final else "🔴 Live"
    await interaction.response.defer(thinking=True)

    result = trigger_github_workflow(tourn_id, event_name, final)

    if result["success"]:
        embed = discord.Embed(
            title="🥏 Scoring Triggered!",
            description=(
                f"**Event:** {event_name}\n"
                f"**Tournament ID:** {tourn_id}\n"
                f"**Mode:** {mode}\n\n"
                f"⏳ GitHub Actions is running the scoring now.\n"
                f"Results will be posted here automatically when done."
            ),
            color=0x2ECC71,
        )
    else:
        embed = discord.Embed(
            title="❌ Failed to Trigger Scoring",
            description=f"**Error:** {result['message']}",
            color=0xE74C3C,
        )

    await interaction.followup.send(embed=embed)


@tree.command(name="score-help", description="Show help for fantasy disc golf commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🥏 Fantasy Disc Golf Bot — Help",
        description="Use these commands to trigger tournament scoring:",
        color=0x3498DB,
    )
    embed.add_field(
        name="/score",
        value=(
            "Trigger scoring for a tournament.\n"
            "**Parameters:**\n"
            "• `tourn_id` — PDGA Tournament ID (find it at pdga.com/tour/event/XXXXX)\n"
            "• `event_name` — Must match a key in the SCHEDULE (e.g. \"Supreme Flight Open\")\n"
            "• `final` — Set to True for final results (default: False for live)\n\n"
            "**Examples:**\n"
            "`/score tourn_id:101154 event_name:Supreme Flight Open`\n"
            "`/score tourn_id:101154 event_name:Supreme Flight Open final:True`"
        ),
        inline=False,
    )
    embed.add_field(
        name="📋 How It Works",
        value=(
            "1. You run `/score` with the tournament details\n"
            "2. The bot triggers a GitHub Actions workflow\n"
            "3. GitHub Actions fetches scores from PDGA\n"
            "4. Results are posted to Discord and Google Sheets is updated (if final)"
        ),
        inline=False,
    )
    await interaction.response.send(embed=embed)


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot is online as {client.user}")
    print(f"   Connected to {len(client.guilds)} server(s)")
    print(f"   Slash commands synced")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN environment variable not set.")
        print("   1. Create a bot at https://discord.com/developers/applications")
        print("   2. Copy the bot token")
        print("   3. Run: export DISCORD_BOT_TOKEN='your-token-here'")
        exit(1)

    if not GITHUB_TOKEN:
        print("⚠️  GITHUB_TOKEN not set — /score command will fail.")
        print("   Create a token at https://github.com/settings/tokens")
        print("   It needs the 'repo' scope.")

    if not GITHUB_REPO:
        print("⚠️  GITHUB_REPO not set — /score command will fail.")
        print("   Set it to your repo, e.g.: export GITHUB_REPO='youruser/fantasy-dg-auto-scoring'")

    client.run(DISCORD_BOT_TOKEN)
