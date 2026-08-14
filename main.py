import discord, os, json, time
from discord.ext import commands
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

DB="db.json"
db=json.load(open(DB)) if os.path.exists(DB) else {}
def save(): json.dump(db, open(DB,"w"))
def get(k): return db.get(k,0)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"READY {bot.user}")

@bot.tree.command(name="daily", description="Claim 15M every 24h")
async def daily(interaction: discord.Interaction):
    uid=str(interaction.user.id)
    now=time.time()
    last=db.get(f"last_{uid}",0)
    if now-last < 86400:
        r=int(86400-(now-last))
        return await interaction.response.send_message(f"⏰ Come back in {r//3600}h {(r%3600)//60}m", ephemeral=True)
    db[f"money_{uid}"]=get(f"money_{uid}")+15000000
    db[f"last_{uid}"]=now
    save()
    await interaction.response.send_message("✅ **15,000,000** claimed!")

@bot.tree.command(name="balance", description="Check balance")
async def balance(interaction: discord.Interaction):
    uid=str(interaction.user.id)
    await interaction.response.send_message(f"💰 {get(f'money_{uid}'):,}")

@bot.tree.command(name="deposit", description="Deposit to bank")
async def deposit(interaction: discord.Interaction, amount: int):
    uid=str(interaction.user.id)
    if get(f"money_{uid}") < amount:
        return await interaction.response.send_message("❌ Broke", ephemeral=True)
    db[f"money_{uid}"]-=amount
    db[f"bank_{uid}"]=get(f"bank_{uid}")+amount
    save()
    await interaction.response.send_message(f"✅ Deposited {amount:,}")

bot.run(os.getenv("TOKEN"))
