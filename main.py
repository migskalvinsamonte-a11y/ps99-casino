import discord, os, json, random, time
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
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

@bot.tree.command(name="balance", description="Check balance")
async def balance(interaction: discord.Interaction):
    data,_ = get_user(interaction.user.id)
    embed = discord.Embed(title=f"💎 {interaction.user.display_name}'s Vault", color=0x9B59B6)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.description = f"**Balance**\n`{fmt(data['balance'])}` - {data['balance']:,}\n\n**Stats**\n📥 Deposited: `{data['deposited']}`\n📤 Withdrawn: `{data['withdrawn']}`\n🎲 Wagered: `{fmt(data['wagered'])}`\n📈 Profit: `{fmt(data['profit'])}`"
    embed.set_footer(text="Casino • Stay Rich")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M daily every 24h")
async def daily(interaction: discord.Interaction):
    cds = load(CD); now = time.time(); last = cds.get(str(interaction.user.id), 0)
    if now - last < 86400:
        left = int(86400 - (now-last)); h=left//3600; m=(left%3600)//60
        return await interaction.response.send_message(f"⏰ Come back in {h}h {m}m!", ephemeral=True)
    data, db = get_user(interaction.user.id)
    reward = 15_000_000
    data["balance"]+=reward; data["profit"]+=reward
    db[str(interaction.user.id)]=data; cds[str(interaction.user.id)]=now
    save(DB,db); save(CD,cds)
    e=discord.Embed(title="🎁 Daily Claimed!", description=f"+ **15M** added!\nNew Balance: **{fmt(data['balance'])}**", color=0xF1C40F)
    await interaction.response.send_message(embed=e, ephemeral=True)

# ================= MINES COOL UI =================
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
        super().__init__(style=discord.ButtonStyle.secondary, label=" ", emoji="❓", row=idx//5)
        self.idx=idx
    async def callback(self, inter: discord.Interaction):
        v: MinesView = self.view
        if inter.user.id!= v.uid: return await inter.response.send_message("Not your game!", ephemeral=True)
        if self.idx in v.revealed: return
        if self.idx in v.bomb_pos:
            d, db = get_user(inter.user.id)
            d["wagered"]+=v.bet; d["profit"]-=v.bet
            db[str(inter.user.id)]=d; save(DB,db)
            for c in v.children:
                if isinstance(c, MineBtn):
                    if c.idx in v.bomb_pos: c.emoji="💣"; c.label=""; c.style=discord.ButtonStyle.danger
                    elif c.idx in v.revealed: c.emoji="💎"; c.label=""; c.style=discord.ButtonStyle.success
                    else: c.emoji="💥"; c.label=""
                    c.disabled=True
            v.children[-1].disabled=True
            e=discord.Embed(title="💥 BOOM! BUSTED", color=0xE74C3C)
            e.add_field(name="💣 Hit a Bomb", value=f"Lost **{fmt(v.bet)}**", inline=False)
            e.add_field(name="💣 Bombs", value=f"{v.bombs} bombs", inline=True)
            e.add_field(name="💎 Found", value=f"{len(v.revealed)} gems", inline=True)
            e.set_footer(text="Better luck next time!")
            await inter.response.edit_message(embed=e, view=v)
            v.stop()
        else:
            v.revealed.add(self.idx); self.emoji="💎"; self.label=""; self.style=discord.ButtonStyle.success; self.disabled=True
            r = len(v.revealed); b = v.bombs
            v.mult = round(1 + (b * 0.036) + (r-1)*0.03 + ((r-1)**2)*0.03, 2)
            won=int(v.bet*v.mult)
            profit=won-v.bet
            e=discord.Embed(title="💎 MINES • Casino", color=0x2ECC71)
            e.add_field(name="💰 Bet", value=f"`{fmt(v.bet)}`", inline=True)
            e.add_field(name="💣 Bombs", value=f"`{v.bombs}`", inline=True)
            e.add_field(name="✨ Multiplier", value=f"`x{v.mult}`", inline=True)
            e.add_field(name="💵 Cashout", value=f"**{fmt(won)}**\n+{fmt(profit)} profit", inline=True)
            e.add_field(name="💎 Gems", value=f"`{len(v.revealed)}/20`", inline=True)
            e.add_field(name="📈 Next", value=f"x{round(v.mult + 0.03 + (r*0.06),2)}", inline=True)
            e.set_footer(text="Find gems • Avoid bombs • Cashout anytime")
            await inter.response.edit_message(embed=e, view=v)

@bot.tree.command(name="mines", description="Play mines min 1M")
@app_commands.describe(bet="Ex: 1M, 10M, 100M", bombs="1-19 bombs")
async def mines(interaction: discord.Interaction, bet: str, bombs: int=5):
    try: bval = parse_amount(bet)
    except: return await interaction.response.send_message("Use like 1M, 10M, 1B", ephemeral=True)
    if bval < 1_000_000: return await interaction.response.send_message("❌ Min 1M!", ephemeral=True)
    if bombs<1 or bombs>19: return await interaction.response.send_message("Bombs 1-19!", ephemeral=True)
    data, db = get_user(interaction.user.id)
    if data["balance"] < bval: return await interaction.response.send_message(f"❌ You have {fmt(data['balance'])}", ephemeral=True)
    data["balance"]-=bval; db[str(interaction.user.id)]=data; save(DB,db)
    view = MinesView(interaction.user.id, bval, bombs)
    cash = discord.ui.Button(label=f"Cashout x1.0", style=discord.ButtonStyle.success, row=4, emoji="💸")
    async def cash_cb(inter: discord.Interaction):
        if inter.user.id!= view.uid: return
        if len(view.revealed)==0: return await inter.response.send_message("Find at least 1 gem first! 💎", ephemeral=True)
        profit=int(view.bet*view.mult)
        d2, db2 = get_user(inter.user.id)
        d2["balance"]+=profit; d2["wagered"]+=view.bet; d2["profit"]+=profit-view.bet
        db2[str(inter.user.id)]=d2; save(DB,db2)
        for c in view.children: c.disabled=True
        e=discord.Embed(title="✅ CASHED OUT!", color=0xF1C40F)
        e.add_field(name="💰 Won", value=f"**{fmt(profit)}** x{view.mult}", inline=False)
        e.add_field(name="💎 Gems Found", value=f"{len(view.revealed)}", inline=True)
        e.add_field(name="💣 Bombs", value=f"{view.bombs}", inline=True)
        await inter.response.edit_message(embed=e, view=view)
        view.stop()
    cash.callback=cash_cb; view.add_item(cash)
    e=discord.Embed(title="💣 MINES • Casino", color=0x3498DB)
    e.add_field(name="💰 Bet", value=f"`{fmt(bval)}`", inline=True)
    e.add_field(name="💣 Bombs", value=f"`{bombs}`", inline=True)
    e.add_field(name="✨ Multiplier", value=f"`x1.0`", inline=True)
    e.description = "Click tiles to find **💎 gems** and avoid **💣 bombs**!\nCashout anytime to keep your winnings."
    e.set_footer(text="Higher bombs = Higher risk = Higher reward")
    await interaction.response.send_message(embed=e, view=view)

# ================= BLACKJACK COOL UI =================
def card_val(cards):
    v=0; aces=0
    for c in cards:
        r=c[:-1]
        if r in ["J","Q","K"]: v+=10
        elif r=="A": v+=11; aces+=1
        else: v+=int(r)
    while v>21 and aces: v-=10; aces-=1
    return v
def hand_str(cards): return " ".join([f"`{c}`" for c in cards])

class BJView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=120)
        self.uid=uid; self.bet=bet
        deck=[f"{r}{s}" for r in ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] for s in ["♠","♥","♦","♣"]]*2
        random.shuffle(deck)
        self.deck=deck
        self.p=[deck.pop(), deck.pop()]
        self.d=[deck.pop(), deck.pop()]
    def embed(self, hide=True, result=None
