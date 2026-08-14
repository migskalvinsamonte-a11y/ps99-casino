import discord, os, json, random, time, asyncio
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="?", intents=intents)

DB = "balances.json"
CD = "cooldowns.json"

# --- NO-WAIT CACHE ---
def load(f):
    if not os.path.exists(f): return {}
    try:
        with open(f, "r") as fp: return json.load(fp)
    except: return {}

def save(f, data):
    with open(f, "w") as fp: json.dump(data, fp)

balances = load(DB) # Loaded ONCE at startup
cooldowns = load(CD)
save_lock = asyncio.Lock()

async def save_bg():
    # Saves in background so no one waits
    async with save_lock:
        save(DB, balances)
        save(CD, cooldowns)

def get_user(uid):
    uid = str(uid)
    if uid not in balances:
        balances[uid] = {"balance": 0, "deposited": 0, "wagered": 0, "profit": 0}
    return balances[uid]

def fmt(n):
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)

def parse_amount(s):
    s = str(s).upper().replace(",", "").strip()
    m=1
    if s.endswith("B"): m=1_000_000_000; s=s[:-1]
    elif s.endswith("M"): m=1_000_000; s=s[:-1]
    elif s.endswith("K"): m=1000; s=s[:-1]
    return int(float(s)*m)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ ONLINE {bot.user} - NO-WAIT MODE")

# --- BALANCE ---
@bot.tree.command(name="balance", description="Check balance")
async def balance_cmd(interaction: discord.Interaction):
    data = get_user(interaction.user.id)
    embed = discord.Embed(title=f"💎 {interaction.user.display_name}'s Vault", color=0x9B59B6)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="💰 Balance", value=f"**{fmt(data['balance'])}**\n`{data['balance']:,}`", inline=False)
    embed.add_field(name="📊 Stats", value=f"🎲 Wagered: {fmt(data['wagered'])}\n📈 Profit: {fmt(data['profit'])}", inline=False)
    embed.set_footer(text="Casino • Instant Play")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M daily every 24h")
async def daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    now = time.time()
    last = cooldowns.get(uid, 0)
    if now - last < 86400:
        left = int(86400 - (now-last)); h=left//3600; m=(left%3600)//60
        return await interaction.response.send_message(f"⏰ Come back in {h}h {m}m!", ephemeral=True)
    data = get_user(interaction.user.id)
    data["balance"]+=15_000_000
    data["profit"]+=15_000_000
    cooldowns[uid]=now
    asyncio.create_task(save_bg()) # save in background, no wait
    e=discord.Embed(title="🎁 Daily Claimed!", description=f"+**15,000,000**\nNew Balance: **{fmt(data['balance'])}**", color=0xF1C40F)
    await interaction.response.send_message(embed=e, ephemeral=True)

# --- MINES COOL UI ---
class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs):
        super().__init__(timeout=180
