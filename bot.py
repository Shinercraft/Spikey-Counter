import discord
from discord.ext import commands, tasks
import os
import json
import asyncio
import time
from dotenv import load_dotenv 

load_dotenv() 

TOKEN = os.getenv("DISCORD_SECRET")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

PRIMARY_COUNTS_FILE = 'message_counts.json'
BACKUP_COUNTS_FILE = 'messages.txt'
DELAYED_COUNTS_FILE = 'msg_delay.txt'

message_counts = {}
delayed_message_counts = {}
last_message_times = {}

COOLDOWN_SECONDS = 10

def load_message_counts():
    global message_counts
    if os.path.exists(PRIMARY_COUNTS_FILE):
        try:
            with open(PRIMARY_COUNTS_FILE, 'r') as f:
                message_counts = json.load(f)
            print(f"Loaded primary message counts from {PRIMARY_COUNTS_FILE}")
        except json.JSONDecodeError:
            print(f"Error reading {PRIMARY_COUNTS_FILE}. Starting with empty primary counts.")
            message_counts = {}
        except Exception as e:
            print(f"An error occurred while loading primary message counts: {e}")
            message_counts = {}
    else:
        print(f"No {PRIMARY_COUNTS_FILE} found. Starting with empty primary counts.")
        message_counts = {}

def save_primary_message_counts():
    try:
        with open(PRIMARY_COUNTS_FILE, 'w') as f:
            json.dump(message_counts, f, indent=4)
        print(f"Saved primary message counts to {PRIMARY_COUNTS_FILE}")
    except Exception as e:
        print(f"An error occurred while saving primary message counts: {e}")

def save_backup_message_counts():
    try:
        with open(BACKUP_COUNTS_FILE, 'w') as f:
            for member_id, count in message_counts.items():
                f.write(f"{member_id}: {count}\n")
        print(f"Saved all-messages backup to {BACKUP_COUNTS_FILE}")
    except Exception as e:
        print(f"An error occurred while saving all-messages backup: {e}")

def load_delayed_message_counts():
    global delayed_message_counts
    if os.path.exists(DELAYED_COUNTS_FILE):
        try:
            with open(DELAYED_COUNTS_FILE, 'r') as f:
                for line in f:
                    try:
                        member_id, count_str = line.strip().split(': ', 1)
                        delayed_message_counts[member_id] = int(count_str)
                    except ValueError:
                        print(f"Skipping malformed line in {DELAYED_COUNTS_FILE}: {line.strip()}")
            print(f"Loaded delayed message counts from {DELAYED_COUNTS_FILE}")
        except Exception as e:
            print(f"An error occurred while loading delayed message counts: {e}")
            delayed_message_counts = {}
    else:
        print(f"No {DELAYED_COUNTS_FILE} found. Starting with empty delayed counts.")
        delayed_message_counts = {}

def save_delayed_message_counts():
    try:
        with open(DELAYED_COUNTS_FILE, 'w') as f:
            for member_id, count in delayed_message_counts.items():
                f.write(f"{member_id}: {count}\n")
        print(f"Saved delayed-messages backup to {DELAYED_COUNTS_FILE}")
    except Exception as e:
        print(f"An error occurred while saving delayed-messages backup: {e}")

@tasks.loop(minutes=5)
async def periodic_backup():
    print("Initiating periodic backup for all counts...")
    save_primary_message_counts()
    save_backup_message_counts()
    save_delayed_message_counts()
    print("Periodic backup complete.")

@bot.event
async def on_ready():
    print(f'Bot connected as {bot.user} (ID: {bot.user.id})')
    print('------')
    load_message_counts()
    load_delayed_message_counts()
    periodic_backup.start()
    print('Bot is online and tracking messages with primary and delayed backups!')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    member_id = str(message.author.id)
    current_time = time.time()

    message_counts[member_id] = message_counts.get(member_id, 0) + 1

    if member_id not in last_message_times or (current_time - last_message_times[member_id]) >= COOLDOWN_SECONDS:
        delayed_message_counts[member_id] = delayed_message_counts.get(member_id, 0) + 1
        last_message_times[member_id] = current_time

    await bot.process_commands(message)

@bot.command()
async def lb(ctx, limit: int = 10):
    if not message_counts:
        await ctx.send("No total message counts recorded yet.")
        return

    sorted_counts = sorted(message_counts.items(), key=lambda item: item[1], reverse=True)
    response = "📊 **Top Total Message Senders:**\n"
    for i, (member_id, count) in enumerate(sorted_counts[:limit]):
        try:
            member = await bot.fetch_user(int(member_id))
            response += f"{i+1}. {member.display_name}: {count} messages\n"
        except discord.NotFound:
            response += f"{i+1}. Unknown User (ID: {member_id}): {count} messages\n"
        except Exception as e:
            response += f"{i+1}. Error fetching user (ID: {member_id}): {count} messages ({e})\n"

    await ctx.send(response)

@bot.command()
async def messages(ctx):
    member_id = str(ctx.author.id)
    count = message_counts.get(member_id, 0)
    await ctx.send(f"Hey {ctx.author.display_name}! You have sent {count} total messages.")


if __name__ == '__main__':
    try:
        if TOKEN == "YOUR_BOT_TOKEN_HERE" or not TOKEN:
            print("\nERROR: Please replace 'YOUR_BOT_TOKEN_HERE' with your actual bot token.")
            print("Go to https://discord.com/developers/applications, select your bot, and copy its token.")
            print("Also, ensure 'Message Content Intent' and 'Server Members Intent' are enabled under 'Bot' tab.")
        else:
            bot.run(TOKEN)
    except discord.errors.LoginFailure:
        print("\nERROR: Invalid bot token. Please double-check your token. It might be old or incorrect.")
    except discord.errors.PrivilegedIntentsRequired:
        print("\nERROR: Privileged Intents are not enabled. Go to https://discord.com/developers/applications,")
        print("select your bot, go to the 'Bot' tab, and enable 'Message Content Intent' and 'Server Members Intent'.")
    except Exception as e:
        print(f"\nAn unexpected error occurred during bot execution: {e}")
    finally:
        print("Bot is shutting down. Saving all data...")
        save_primary_message_counts()
        save_backup_message_counts()
        save_delayed_message_counts()
        print("Data saved. Goodbye!")
