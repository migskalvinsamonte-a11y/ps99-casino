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
    embed = discord.Embed(title=f"{interaction.user.display_name}'s balance", color=0x2B88D8)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.description = f"💎 **Balance** `{fmt(data['balance'])} ({data['balance']:,})`\n📥 **Deposited** `{data['deposited']}`\n📤 **Withdrawn** `{data['withdrawn']}`\n💎 **Wagered** `{fmt(data['wagered'])}`\n💸 **Profit** `{fmt(data['profit'])}`"
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M daily every 24h")
async def daily(interaction: discord.Interaction):
    cds = load(CD); now = time.time(); last = cds.get(str(interaction.user.id), 0)
    if now - last < 86400:
        left = int(86400 - (now-last)); h=left//3600; m=(left%3600)//60
        return await interaction.response.send_message(f"⏰ Wait {h}h {m}m!", ephemeral=True)
    data, db = get_user(interaction.user.id)
    reward = 15_000_000
    data["balance"]+=reward; data["profit"]+=reward
    db[str(interaction.user.id)]=data; cds[str(interaction.user.id)]=now
    save(DB,db); save(CD,cds)
    await interaction.response.send_message(f"✅ Claimed **15M**! Balance: {fmt(data['balance'])}", ephemeral=True)

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
        super().__init__(style=discord.ButtonStyle.secondary, label="❓", row=idx//5)
        self.idx=idx
    async def callback(self, inter: discord.Interaction):
        v: MinesView = self.view
        if inter.user.id!= v.uid: return await inter.response.send_message("Not yours!", ephemeral=True)
        if self.idx in v.revealed: return
        if self.idx in v.bomb_pos:
            d, db = get_user(inter.user.id)
            d["wagered"]+=v.bet; d["profit"]-=v.bet
            db[str(inter.user.id)]=d; save(DB,db)
            for c in v.children:
                if isinstance(c, MineBtn):
                    if c.idx in v.bomb_pos: c.label="💣"; c.style=discord.ButtonStyle.danger
                    elif c.idx in v.revealed: c.label="💎"
                    c.disabled=True
            v.children[-1].disabled=True
            await inter.response.edit_message(embed=discord.Embed(title="💥 BOOM!", description=f"Lost {fmt(v.bet)}", color=0xFF0000), view=v)
            v.stop()
        else:
            v.revealed.add(self.idx); self.label="💎"; self.style=discord.ButtonStyle.success; self.disabled=True
            r = len(v.revealed); b = v.bombs
            v.mult = round(1 + (b * 0.036) + (r-1)*0.03 + ((r-1)**2)*0.03, 2)
            won=int(v.bet*v.mult)
            e=discord.Embed(title="💣 Mines", color=0x2B88D8, description=f"**Bet:** {fmt(v.bet)} | **Bombs:** {v.bombs}\n**Cashout:** {fmt(won)} x{v.mult}\nRevealed: {len(v.revealed)}")
            await inter.response.edit_message(embed=e, view=v)

@bot.tree.command(name="mines", description="Play mines min 1M - bombs up to 19")
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
    cash = discord.ui.Button(label="Cashout", style=discord.ButtonStyle.green, row=4, emoji="💸")
    async def cash_cb(inter: discord.Interaction):
        if inter.user.id!= view.uid: return
        if len(view.revealed)==0: return await inter.response.send_message("Reveal 1 tile first!", ephemeral=True)
        profit=int(view.bet*view.mult)
        d2, db2 = get_user(inter.user.id)
        d2["balance"]+=profit; d2["wagered"]+=view.bet; d2["profit"]+=profit-view.bet
        db2[str(inter.user.id)]=d2; save(DB,db2)
        for c in view.children: c.disabled=True
        await inter.response.edit_message(embed=discord.Embed(title="✅ Cashed Out!", description=f"Won **{fmt(profit)}** x{view.mult}", color=0x00FF00), view=view)
        view.stop()
    cash.callback=cash_cb; view.add_item(cash)
    e=discord.Embed(title="💣 Mines", color=0x2B88D8, description=f"**Bet:** {fmt(bval)} | **Bombs:** {bombs}\n**Cashout:** {fmt(bval)} x1.0")
    await interaction.response.send_message(embed=e, view=view)

def card_val(cards):
    v=0; aces=0
    for c in cards:
        r=c[:-1]
        if r in ["J","Q","K"]: v+=10
        elif r=="A": v+=11; aces+=1
        else: v+=int(r)
    while v>21 and aces: v-=10; aces-=1
    return v

def hand_str(cards): return " ".join(cards)

class BJView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=120)
        self.uid=uid; self.bet=bet
        deck=[f"{r}{s}" for r in ["A","2","3","4","5","6","7","8","9","10","J","Q","K"] for s in ["♠","♥","♦","♣"]]*2
        random.shuffle(deck)
        self.deck=deck
        self.p=[deck.pop(), deck.pop()]
        self.d=[deck.pop(), deck.pop()]
    def embed(self, hide=True):
        pv=card_val(self.p); dv=card_val([self.d[0]]) if hide else card_val(self.d)
        e=discord.Embed(title="♠️ Blackjack", color=0x2B88D8)
        e.add_field(name=f"Your Hand ({pv})", value=hand_str(self.p), inline=False)
        if hide: e.add_field(name=f"Dealer ({dv}+?)", value=f"{self.d[0]} 🂠", inline=False)
        else: e.add_field(name=f"Dealer ({dv})", value=hand_str(self.d), inline=False)
        e.set_footer(text=f"Bet: {fmt(self.bet)} | Win 2x | Blackjack 2.5x")
        return e

@bot.tree.command(name="blackjack", description="Play blackjack min 1M - Win 2x, Blackjack 2.5x")
@app_commands.describe(bet="Ex: 1M, 10M")
async def blackjack(interaction: discord.Interaction, bet: str):
    try: bval=parse_amount(bet)
    except: return await interaction.response.send_message("Use 1M, 10M, 1B", ephemeral=True)
    if bval<1_000_000: return await interaction.response.send_message("❌ Min 1M!", ephemeral=True)
    data,db=get_user(interaction.user.id)
    if data["balance"]<bval: return await interaction.response.send_message(f"❌ You have {fmt(data['balance'])}", ephemeral=True)
    data["balance"]-=bval; db[str(interaction.user.id)]=data; save(DB,db)
    view=BJView(interaction.user.id, bval)
    pv=card_val(view.p); dv_full=card_val(view.d)
    if pv==21:
        if dv_full==21:
            d,_=get_user(interaction.user.id); d["balance"]+=bval; save(DB,db)
            return await interaction.response.send_message(embed=discord.Embed(title="Push! Both Blackjack", color=0xFFFF00, description=f"Returned {fmt(bval)}"))
        else:
            win=int(bval*2.5) # 2.5x for blackjack
            d,db=get_user(interaction.user.id); d["balance"]+=win; d["wagered"]+=bval; d["profit"]+=win-bval; db[str(interaction.user.id)]=d; save(DB,db)
            return await interaction.response.send_message(embed=discord.Embed(title="BLACKJACK! 2.5x", color=0x00FF00, description=f"Won {fmt(win)} (2.5x)"))
    hit=discord.ui.Button(label="Hit", style=discord.ButtonStyle.primary, emoji="🃏")
    stand=discord.ui.Button(label="Stand", style=discord.ButtonStyle.success, emoji="✋")
    async def hit_cb(inter: discord.Interaction):
        if inter.user.id!=view.uid: return
        view.p.append(view.deck.pop())
        pv=card_val(view.p)
        if pv>21:
            d,db=get_user(interaction.user.id); d["wagered"]+=view.bet; d["profit"]-=view.bet; db[str(interaction.user.id)]=d; save(DB,db)
            e=view.embed(hide=False); e.title="💥 BUST! You lost"; e.color=0xFF0000
            for c in view.children: c.disabled=True
            await inter.response.edit_message(embed=e, view=view); view.stop()
        else:
            await inter.response.edit_message(embed=view.embed(), view=view)
    async def stand_cb(inter: discord.Interaction):
        if inter.user.id!=view.uid: return
        while card_val(view.d)<17:
            view.d.append(view.deck.pop())
        pv=card_val(view.p); dv=card_val(view.d)
        e=view.embed(hide=False)
        d,db=get_user(interaction.user.id)
        if dv>21 or pv>dv:
            win=bval*2 # 2x for normal win
            d["balance"]+=win; d["wagered"]+=bval; d["profit"]+=win-bval
            e.title=f"✅ You Win! {pv} vs {dv} - 2x"; e.color=0x00FF00; e.description=f"Won **{fmt(win)}** (2x)"
        elif pv==dv:
            d["balance"]+=bval
            e.title=f"Push {pv} vs {dv}"; e.color=0xFFFF00; e.description=f"Returned {fmt(bval)}"
        else:
            d["wagered"]+=bval; d["profit"]-=bval
            e.title=f"❌ Dealer Wins {dv} vs {pv}"; e.color=0xFF0000; e.description=f"Lost {fmt(bval)}"
        db[str(interaction.user.id)]=d; save(DB,db)
        for c in view.children: c.disabled=True
        await inter.response.edit_message(embed=e, view=view); view.stop()
    hit.callback=hit_cb; stand.callback=stand_cb
    view.add_item(hit); view.add_item(stand)
    await interaction.response.send_message(embed=view.embed(), view=view)

@bot.tree.command(name="give", description="Give gems ADMIN ONLY")
@app_commands.describe(user="User", amount="1M, 100M, 1B")
async def give(interaction: discord.Interaction, user: discord.Member, amount: str):
    if not interaction.user.guild_permissions.administrator and interaction.user.id not in OWNER_IDS:
        return await interaction.response.send_message("❌ Admin only!", ephemeral=True)
    try: val=parse_amount(amount)
    except: return await interaction.response.send_message("Use 1M, 10M, 1B", ephemeral=True)
    d, db = get_user(user.id)
    d["balance"]+=val; d["deposited"]+=val; d["profit"]+=val
    db[str(user.id)]=d; save(DB,db)
    await interaction.response.send_message(embed=discord.Embed(title="💎 Given!", description=f"Gave **{fmt(val)}** to {user.mention}\nNew bal: {fmt(d['balance'])}", color=0x00FF00))

bot.run(os.getenv("TOKEN"))
