import discord
import asyncio
import requests
from bs4 import BeautifulSoup
import os
import json
from dotenv import load_dotenv
from discord.ext import commands

# Load environment variables
load_dotenv()

# Get and validate environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
USER_ID = os.getenv("USER_ID")

if not TOKEN or not CHANNEL_ID:
    raise ValueError("❌ Missing DISCORD_TOKEN or CHANNEL_ID in .env")

CHANNEL_ID = int(CHANNEL_ID)
USER_ID = int(USER_ID) if USER_ID else None

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

client = commands.Bot(command_prefix='!', intents=intents)

# Track fruit stock
previous_normal_stock = []
previous_mirage_stock = []

# Role mapping for fruit name -> role ID
fruit_roles = {}
ROLES_FILE = "fruit_roles.json"

# ---------------- ROLE PERSISTENCE ----------------
def load_roles():
    global fruit_roles
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, "r") as f:
            fruit_roles = json.load(f)

def save_roles():
    with open(ROLES_FILE, "w") as f:
        json.dump(fruit_roles, f)

# ---------------- STOCK SCRAPER ----------------
async def fetch_stock():
    try:
        url = "https://fruityblox.com/stock"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.select("div.grid > div")

        normal_stock = []
        mirage_stock = []

        for card in cards:
            name_tag = card.find("h3")
            stock_type_tag = card.find("span", class_="text-xs text-gray-400")

            if name_tag and stock_type_tag:
                fruit_name = name_tag.text.strip()
                stock_type = stock_type_tag.text.strip()

                if "Mirage" in stock_type:
                    mirage_stock.append(fruit_name)
                else:
                    normal_stock.append(fruit_name)

        return normal_stock, mirage_stock

    except Exception as e:
        print(f"Error fetching stock: {e}")
        return [], []

# ---------------- STOCK CHECKER TASK ----------------
async def check_stock():
    global previous_normal_stock, previous_mirage_stock
    await client.wait_until_ready()

    while not client.is_closed():
        try:
            channel = await client.fetch_channel(CHANNEL_ID)
            normal_stock, mirage_stock = await fetch_stock()

            if normal_stock != previous_normal_stock or mirage_stock != previous_mirage_stock:
                embed = discord.Embed(title="📦 **Current Stock Update**", color=discord.Color.blue())

                # Normal stock
                if normal_stock:
                    embed.add_field(name="✅ **Normal Stock**", value=", ".join(normal_stock), inline=False)
                else:
                    embed.add_field(name="✅ **Normal Stock**", value="None", inline=False)

                # Mirage stock
                if mirage_stock:
                    embed.add_field(name="🌌 **Mirage Stock**", value=", ".join(mirage_stock), inline=False)
                else:
                    embed.add_field(name="🌌 **Mirage Stock**", value="None", inline=False)

                await channel.send(embed=embed)

                # Role pings for newly stocked fruits
                combined = normal_stock + mirage_stock
                for fruit in combined:
                    if fruit_roles.get(fruit):
                        role_id = fruit_roles[fruit]
                        role = channel.guild.get_role(role_id)
                        if role:
                            await channel.send(f"{role.mention} **{fruit}** is now in stock!")

                previous_normal_stock = normal_stock
                previous_mirage_stock = mirage_stock

        except Exception as e:
            print(f"Error in stock checker: {e}")

        await asyncio.sleep(300)  # Check every 5 minutes

# ---------------- DISCORD EVENTS ----------------
@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    load_roles()  # Load roles at startup
    client.loop.create_task(check_stock())

# ---------------- BOT COMMANDS ----------------
@client.command()
async def setrole(ctx, fruit_name: str, role: discord.Role):
    fruit_roles[fruit_name] = role.id
    save_roles()
    await ctx.send(f"✅ Set role {role.mention} for fruit **{fruit_name}**")

@client.command()
async def removerole(ctx, fruit_name: str):
    if fruit_name in fruit_roles:
        del fruit_roles[fruit_name]
        save_roles()
        await ctx.send(f"✅ Removed role for fruit **{fruit_name}**")
    else:
        await ctx.send(f"❌ No role set for **{fruit_name}**")

@client.command()
async def listroles(ctx):
    if not fruit_roles:
        await ctx.send("📭 No roles assigned to any fruits.")
        return

    desc = "\n".join([f"**{fruit}** → <@&{rid}>" for fruit, rid in fruit_roles.items()])
    embed = discord.Embed(title="🍍 Tracked Fruit Roles", description=desc, color=discord.Color.green())
    await ctx.send(embed=embed)

# ---------------- START BOT ----------------
client.run(TOKEN)
