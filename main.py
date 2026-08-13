import discord, json, os, random
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)

DB_FILE = "db.json"
db = {}
if os.path.exists(DB_FILE):
    try: db = json.load(open(DB_FILE))
    except: db = {}

def save(): json.dump(db, open(DB_FILE, "w"))
def get(k): return db.get(k, 0)
def add(k,v): db[k]=get(k)+v; save()
def sub(k,v): db[k]=get(k)-v; save()

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(e)

@bot.tree.command(name="balance", description="Check your balance")
async def balance_slash(interaction: discord.Interaction):
    id = str(interaction.user.id)
    embed = discord.Embed(color=0xFFC800)
    embed.set_author(name=f"{interaction.user.name}'s balance")
    embed.description = f"💰 Balance `{get(f'money_{id}'):,}`\n📥 Deposited `{get(f'deposited_{id}'):,}`\n📤 Withdrawn `{get(f'wagered_{id}'):,}`\n📈 Profit `{get(f'profit_{id}'):,}`"
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim 1M daily")
async def daily_slash(interaction: discord.Interaction):
    add(f"money_{interaction.user.id}", 1000000)
    await interaction.response.send_message("Claimed 1M! Use /balance")

@bot.tree.command(name="deposit", description="Deposit money to bank")
@app_commands.describe(amount="Amount to deposit")
async def deposit_slash(interaction: discord.Interaction, amount: int):
    id = str(interaction.user.id)
    if get(f"money_{id}") < amount:
        return await interaction.response.send_message("No money")
    sub(f"money_{id}", amount)
    add(f"bank_{id}", amount)
    add(f"deposited_{id}", amount)
    await interaction.response.send_message(f"Deposited {amount:,} -> /balance")

@bot.tree.command(name="cf", description="Coinflip gamble")
@app_commands.describe(amount="Amount to gamble")
async def cf_slash(interaction: discord.Interaction, amount: int):
    id = str(interaction.user.id)
    if get(f"money_{id}") < amount:
        return await interaction.response.send_message("No money")
    sub(f"money_{id}", amount)
    add(f"wagered_{id}", amount)
    if random.random() > 0.5:
        add(f"money_{id}", amount*2)
        add(f"profit_{id}", amount)
        await interaction.response.send_message(f"WON {amount*2:,}")
    else:
        sub(f"profit_{id}", amount)
        await interaction.response.send_message(f"LOST {amount:,}")

bot.run(os.getenv("TOKEN"))
