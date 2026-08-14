import discord, os, json, random, time, asyncio
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="?", intents=intents)

DB = "balances.json"
CD = "cooldowns.json"
OWNER_IDS = []

def load(f):
    if not os.path.exists(f): return {}
    try:
        with open(f, "r") as fp: return json.load(fp)
    except: return {}
def save(f, data):
    with open(f, "w") as fp: json.dump(data, fp)

def fmt(n):
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)

def parse_amount(s):
    s = str(s).upper().replace(",", "").strip()
    mult = 1
    if s.endswith("B"): mult = 1_000_000_000; s = s[:-1]
    elif s.endswith("M"): mult = 1_000_000; s = s[:-1]
    elif s.endswith("K"): mult = 1_000; s = s[:-1]
    return int(float(s) * mult)

def get_user(uid):
    db = load(DB)
    if str(uid) not in db:
        db[str(uid)] = {"balance": 0, "deposited": 0, "withdrawn": 0, "wagered": 0, "profit": 0}
        save(DB, db)
    return db[str(uid)], db

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands - ONLINE {bot.user}")
    except Exception as e:
        print(f"Sync failed: {e}")

# --- BALANCE ---
@bot.tree.command(name="balance", description="Check balance")
async def balance(interaction: discord.Interaction):
    await interaction.response.defer()
    data,_ = get_user(interaction.user.id)
    embed = discord.Embed(title=f"💎 {interaction.user.display_name}'s Vault", color=0x9B59B6)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.description = f"**Balance** `{fmt(data['balance'])}` - {data['balance']:,}\n🎲 Wagered: `{fmt(data['wagered'])}`\n📈 Profit: `{fmt(data['profit'])}`"
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M daily every 24h")
async def daily(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    cds = load(CD); now = time.time(); last = cds.get(str(interaction.user.id), 0)
    if now - last < 86400:
        left = int(86400 - (now-last)); h=left//3600; m=(left%3600)//60
        return await interaction.followup.send(f"⏰ Wait {h}h {m}m!", ephemeral=True)
    data, db = get_user(interaction.user.id)
    data["balance"]+=15_000_000; data["profit"]+=15_000_000
    db[str(interaction.user.id)]=data; cds[str(interaction.user.id)]=now
    save(DB,db); save(CD,cds)
    await interaction.followup.send(f"🎁 +15M! New: {fmt(data['balance'])}", ephemeral=True)

# --- MINES ---
class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs):
        super().__init__(timeout=180)
        self.uid=uid; self.bet=bet; self.bombs=bombs
        self.revealed=set()
        self.bomb_pos=set(random.sample(range(20), bombs))
        self.mult=1.0
        for i in range(20): self.add_item(MineBtn(i))

class MineBtn(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, emoji="❓", row=idx//5)
        self.idx=idx
    async def callback(self, inter: discord.Interaction):
        v = self.view
        if inter.user.id != v.uid:
            return await inter.response.send_message("Not yours!", ephemeral=True)
        await inter.response.defer()
        if self.idx in v.revealed:
            return
        if self.idx in v.bomb_pos:
            d, db = get_user(inter.user.id)
            d["wagered"]+=v.bet; d["profit"]-=v.bet
            db[str(inter.user.id)]=d; save(DB,db)
            for c in v.children:
                if isinstance(c, MineBtn):
                    if c.idx in v.bomb_pos: c.emoji="💣"; c.style=discord.ButtonStyle.danger
                    elif c.idx in v.revealed: c.emoji="💎"; c.style=discord.ButtonStyle.success
                    c.disabled=True
            v.children[-1].disabled=True
            e=discord.Embed(title="💥 BOOM!", description=f"Lost {fmt(v.bet)}", color=0xE74C3C)
            await inter.followup.edit_message(inter.message.id, embed=e, view=v)
            v.stop()
        else:
            v.revealed.add(self.idx); self.emoji="💎"; self.style=discord.ButtonStyle.success; self.disabled=True
            r = len(v.revealed); b = v.bombs
            v.mult = round(1 + (b * 0.036) + (r-1)*0.03 + ((r-1)**2)*0.03, 2)
            won=int(v.bet*v.mult)
            e=discord.Embed(title="💎 MINES", color=0x2ECC71, description=f"**Bet** {fmt(v.bet)} | **Bombs** {b} |
