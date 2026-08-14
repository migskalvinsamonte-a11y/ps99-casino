import discord, json, os, random, time
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
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

COOLDOWN = 86400 # 24 hours
DAILY_AMOUNT = 15000000

@bot.event
async def on_ready():
    print(f"Online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

@bot.tree.command(name="balance", description="Check your balance")
async def balance(interaction: discord.Interaction):
    id = str(interaction.user.id)
    embed = discord.Embed(color=0xFFC800, title=f"{interaction.user.name}'s balance")
    embed.description = f"💰 Balance `{get(f'money_{id}'):,}`\n📥 Deposited `{get(f'deposited_{id}'):,}`\n📤 Wagered `{get(f'wagered_{id}'):,}`\n📈 Profit `{get(f'profit_{id}'):,}`"
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M daily")
async def daily(interaction: discord.Interaction):
    id = str(interaction.user.id)
    now = time.time()
    last = get(f"last_daily_{id}")

    if now - last < COOLDOWN:
        remaining = COOLDOWN - (now - last)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        return await interaction.response.send_message(f"⏰ Already claimed! Come back in {hours}h {minutes}m", ephemeral=True)

    add(f"money_{id}", DAILY_AMOUNT)
    db[f"last_daily_{id}"] = now
    save()
    await interaction.response.send_message(f"✅ Claimed **15,000,000**! Use /balance")

@bot.tree.command(name="deposit", description="Deposit money")
@app_commands.describe(amount="Amount to deposit")
async def deposit(interaction: discord.Interaction, amount: int):
    id = str(interaction.user.id)
    if get(f"money_{id}") < amount:
        return await interaction.response.send_message("❌ No money", ephemeral=True)
    sub(f"money_{id}", amount)
    add(f"bank_{id}", amount)
    add(f"deposited_{id}", amount)
    await interaction.response.send_message(f"✅ Deposited {amount:,} -> /balance")

@bot.tree.command(name="cf", description="Coinflip")
@app_commands.describe(amount="Amount to gamble")
async def cf(interaction: discord.Interaction, amount: int):
    id = str(interaction.user.id)
    if get(f"money_{id}") < amount:
        return await interaction.response.send_message("❌ No money", ephemeral=True)
    sub(f"money_{id}", amount)
    add(f"wagered_{id}", amount)
    if random.random() > 0.5:
        add(f"money_{id}", amount*2)
        add(f"profit_{id}", amount)
        await interaction.response.send_message(f"🎉 WON {amount*2:,}")
    else:
        sub(f"profit_{id}", amount)
        await interaction.response.send_message(f"💀 LOST {amount:,}")

bot.run(os.getenv("TOKEN"))
