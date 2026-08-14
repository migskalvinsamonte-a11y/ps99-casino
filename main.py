import discord, os, json, random, time, asyncio
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="?", intents=intents)

DB = "balances.json"
CD = "cooldowns.json"
lock = asyncio.Lock() # FIXES CRASH WHEN 2 PEOPLE PLAY AT SAME TIME
cd_lock = asyncio.Lock()

def load(f):
    if not os.path.exists(f): return {}
    try:
        with open(f, "r") as fp: return json.load(fp)
    except: return {}
def save(f, data):
    with open(f, "w") as fp: json.dump(data, fp, indent=2)

def fmt(n):
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(int(n))

def parse_amount(s):
    s = str(s).upper().replace(",", "").strip()
    mult=1
    if s.endswith("B"): mult=1_000_000_000; s=s[:-1]
    elif s.endswith("M"): mult=1_000_000; s=s[:-1]
    elif s.endswith("K"): mult=1_000; s=s[:-1]
    return int(float(s)*mult)

async def get_user(uid):
    async with lock:
        db=load(DB)
        if str(uid) not in db:
            db[str(uid)]={"balance":0,"deposited":0,"withdrawn":0,"wagered":0,"profit":0}
            save(DB,db)
        return db[str(uid)], db

async def save_user(uid, data, db):
    async with lock:
        db[str(uid)]=data
        save(DB,db)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ ONLINE {bot.user} | Lock enabled | 2x win 2.5x BJ")

# ================= BALANCE - COOL VAULT =================
@bot.tree.command(name="balance", description="Check your vault")
async def balance(interaction: discord.Interaction):
    await interaction.response.defer()
    data,_ = await get_user(interaction.user.id)
    e=discord.Embed(title=f"💎 {interaction.user.display_name}'s Vault", color=0x9B59B6)
    e.set_thumbnail(url=interaction.user.display_avatar.url)
    e.add_field(name="💰 Balance", value=f"**{fmt(data['balance'])}**\n`{data['balance']:,}`", inline=False)
    e.add_field(name="📊 Stats", value=f"🎲 Wagered: {fmt(data['wagered'])}\n📈 Profit: {fmt(data['profit'])}", inline=True)
    e.add_field(name="📦 Other", value=f"📥 Depo: {fmt(data['deposited'])}\n📤 With: {fmt(data['withdrawn'])}", inline=True)
    e.set_footer(text="Casino • Richest wins")
    await interaction.followup.send(embed=e)

# ================= DAILY 15M 24H =================
@bot.tree.command(name="daily", description="Claim 15M daily every 24h")
async def daily(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    async with cd_lock:
        cds=load(CD)
        now=time.time()
        last=cds.get(str(interaction.user.id),0)
        if now-last < 86400:
            left=int(86400-(now-last)); h=left//3600; m=(left%3600)//60; s=left%60
            e=discord.Embed(title="⏰ Daily on Cooldown", description=f"Come back in **{h}h {m}m {s}s**", color=0xE74C3C)
            return await interaction.followup.send(embed=e, ephemeral=True)
        data,db = await get_user(interaction.user.id)
        data["balance"]+=15_000_000; data["profit"]+=15_000_000
        await save_user(interaction.user.id, data, db)
        cds[str(interaction.user.id)]=now; save(CD,cds)
    e=discord.Embed(title="🎁 Daily Claimed!", description=f"+ **15,
