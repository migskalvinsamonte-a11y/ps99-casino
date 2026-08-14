import discord, os, json, random, time
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

balances = {}
cooldowns = {}

def load_file(name):
    if not os.path.exists(name): return {}
    try:
        with open(name, "r") as f: return json.load(f)
    except: return {}

async def save_all():
    with open("balances.json", "w") as f: json.dump(balances, f)
    with open("cooldowns.json", "w") as f: json.dump(cooldowns, f)

def fmt(n):
    if n >= 1000000000: return f"{n/1000000000:.2f}B"
    if n >= 1000000: return f"{n/1000000:.2f}M"
    if n >= 1000: return f"{n/1000:.1f}K"
    return str(int(n))

def parse_amount(s):
    s = str(s).upper().replace(",", "").strip()
    m = 1
    if s.endswith("B"): m = 1000000000; s = s[:-1]
    elif s.endswith("M"): m = 1000000; s = s[:-1]
    elif s.endswith("K"): m = 1000; s = s[:-1]
    return int(float(s) * m)

def get_data(uid):
    uid = str(uid)
    if uid not in balances:
        balances[uid] = {"balance":0, "bank":0, "wagered":0, "deposited":0, "withdrawn":0, "profit":0, "tipped":0}
    for k in ["bank","wagered","deposited","withdrawn","profit","tipped"]:
        if k not in balances[uid]: balances[uid][k]=0
    return balances[uid]

@bot.event
async def on_ready():
    global balances, cooldowns
    balances = load_file("balances.json")
    cooldowns = load_file("cooldowns.json")
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

@bot.tree.command(name="balance", description="Check vault")
async def balance_cmd(interaction: discord.Interaction):
    d = get_data(interaction.user.id)
    embed = discord.Embed(title="💎 VAULT", color=0xA020F0)
    embed.set_author(name=f"{interaction.user.display_name}'s Vault", icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="💰 Gems", value=f"**{fmt(d['balance'])}**\n{d['balance']:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"**{fmt(d['bank'])}**\nWithdrawable", inline=True)
    embed.add_field(name="📊 Stats", value=f"Wagered: {fmt(d['wagered'])}\nDeposited: {fmt(d['deposited'])}\nWithdrawn: {fmt(d['withdrawn'])}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M every 24h")
async def daily_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    now = time.time()
    last = cooldowns.get(uid, 0)
    if now - last < 86400:
        left = int(86400 - (now - last))
        return await interaction.followup.send(f"Come back in {left//3600}h {(left%3600)//60}m", ephemeral=True)
    d = get_data(interaction.user.id)
    d["balance"] += 15000000
    d["deposited"] += 15000000
    cooldowns[uid] = now
    await save_all()
    await interaction.followup.send(f"✅ +15M! Balance: {fmt(d['balance'])}", ephemeral=True)

@bot.tree.command(name="tip", description="Tip gems to a member")
@app_commands.describe(user="Who to tip", amount="Amount like 1M")
async def tip_cmd(interaction: discord.Interaction, user: discord.Member, amount: str):
    await interaction.response.defer()
    if user.id == interaction.user.id: return await interaction.followup.send("Can't tip yourself!")
    if user.bot: return await interaction.followup.send("Can't tip bots!")
    try: bval = parse_amount(amount)
    except: return await interaction.followup.send("Use 1M")
    d = get_data(interaction.user.id)
    if d["balance"] < bval: return await interaction.followup.send(f"You have {fmt(d['balance'])} only!")
    d["balance"] -= bval
    d2 = get_data(user.id)
    d2["balance"] += bval
    await save_all()
    embed = discord.Embed(title="💸 TIP", color=0x2ECC71, description=f"{interaction.user.mention} -> {user.mention} **{fmt(bval)}**")
    embed.set_author(name=f"{interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.followup.send(embed=embed)

def card_value(cards):
    v=0;a=0
    for c in cards:
        r=c[:-1]
        if r in ["J","Q","K"]: v+=10
        elif r=="A": v+=11;a+=1
        else: v+=int(r)
    while v>21 and a>0: v-=10;a-=1
    return v

class BJView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=120)
        self.uid=uid; self.bet=bet
        deck=[]
        for _ in range(4):
            for r in ["2","3","4","5","6","7","8","9","10","J","Q","K","A"]:
                for s in ["♠","♥","♦","♣"]:
                    if r == "A" and random.randint(1,100) <= 70: continue
                    deck.append(f"{r}{s}")
        random.shuffle(deck)
        self.deck=deck
        self.p=[deck.pop(), deck.pop()]
        self.d=[deck.pop(), deck.pop()]
        if card_value(self.p)==21 and random.randint(1,100) <= 65:
            self.p[1]=random.choice(["2♠","3♥","4♦","5♣","6♠","7♦"])

@bot.tree.command(name="blackjack", description="Play blackjack")
async def bj_cmd(interaction: discord.Interaction, bet: str):
    await interaction.response.defer()
    try: bval=parse_amount(bet)
    except: return await interaction.followup.send("Use 1M")
    d=get_data(interaction.user.id)
    if d["balance"]<bval: return await interaction.followup.send(f"Have {fmt(d['balance'])}")
    d["balance"]-=bval
    view=BJView(interaction.user.id,bval)
    def make_embed(hide=True):
        pv=card_value(view.p); dv=card_value([view.d[0]]) if hide else card_value(view.d)
        emb=discord.Embed(title="♠️ BLACKJACK", color=0x1ABC9C)
        emb.set_author(name=f"{interaction.user.display_name}'s Blackjack", icon_url=interaction.user.display_avatar.url)
        emb.set_thumbnail(url=interaction.user.display_avatar.url)
        emb.add_field(name=f"YOU [{pv}]", value=" ".join(view.p), inline=False)
        emb.add_field(name=f"DEALER [{dv}{'+?' if hide else ''}]", value=f"{view.d[0]} 🂠" if hide else " ".join(view.d), inline=False)
        emb.set_footer(text=f"Bet {fmt(bval)} • 2x Win • 2.5x Blackjack")
        return emb
    if card_value(view.p)==21:
        win=int(bval*2.5); d["balance"]+=win; await save_all()
        emb=discord.Embed(title="🔥 BLACKJACK!", description=f"Won {fmt(win)}", color=0xF1C40F)
        emb.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        return await interaction.followup.send(embed=emb)
    hit=discord.ui.Button(label="HIT", style=discord.ButtonStyle.primary)
    stand=discord.ui.Button(label="STAND", style=discord.ButtonStyle.success)
    async def hit_cb(inter: discord.Interaction):
        if inter.user.id!=view.uid: return await inter.response.send_message("Not your game", ephemeral=True)
        await inter.response.defer()
        view.p.append(view.deck.pop())
        if card_value(view.p)>21:
            emb=make_embed(False); emb.title=f"BUST {card_value(view.p)}"; emb.color=0xE74C3C
            for c in view.children: c.disabled=True
            await inter.followup.edit_message(inter.message.id, embed=emb, view=view); await save_all(); view.stop()
        else: await inter.followup.edit_message(inter.message.id, embed=make_embed(True), view=view)
    async def stand_cb(inter: discord.Interaction):
        if inter.user.id!=view.uid: return await inter.response.send_message("Not your game", ephemeral=True)
        await inter.response.defer()
        while card_value(view.d)<17: view.d.append(view.deck.pop())
        pv=card_value(view.p); dv=card_value(view.d); d2=get_data(inter.user.id)
        if dv>21 or pv>dv:
            win=bval*2; d2["balance"]+=win; d2["wagered"]+=bval; d2["profit"]+=win-bval
            emb=make_embed(False); emb.title=f"WIN {pv} vs {dv}"; emb.description=f"Won {fmt(win)}"; emb.color=0x2ECC71
        elif pv==dv:
            d2["balance"]+=bval; emb=make_embed(False); emb.title=f"PUSH {pv}"
        else:
            d2["wagered"]+=bval; d2["profit"]-=bval; emb=make_embed(False); emb.title=f"LOSE {pv} vs {dv}"; emb.color=0xE74C3C
        for c in view.children: c.disabled=True
        await inter.followup.edit_message(inter.message.id, embed=emb, view=view); await save_all(); view.stop()
    hit.callback=hit_cb; stand.callback=stand_cb; view.add_item(hit); view.add_item(stand)
    await interaction.followup.send(embed=make_embed(True), view=view)

class MineBtn(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, label="?", row=idx//5)
        self.idx = idx
    async def callback(self, inter: discord.Interaction):
        view = self.view
        if inter.user.id!= view.uid: return await inter.response.send_message("Not your game!", ephemeral=True)
        await inter.response.defer()
        if self.idx in view.revealed: return
        if self.idx in view.bomb_pos:
            d = get_data(inter.user.id); d["wagered"] += view.bet; d["profit"] -= view.bet
            for c in view.children:
                if isinstance(c, MineBtn):
                    c.disabled = True
                    if c.idx in view.bomb_pos: c.label = "💣"; c.style = discord.ButtonStyle.danger
            embed = discord.Embed(title="BOOM!", description=f"Lost {fmt(view.bet)}", color=0xE74C3C)
            embed.set_author(name=f"{inter.user.display_name}", icon_url=inter.user.display_avatar.url)
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view); await save_all(); view.stop()
        else:
            view.revealed.add(self.idx); self.label = "💎"; self.style = discord.ButtonStyle.success; self.disabled = True
            view.multi = round(1 + len(view.revealed) * 0.3, 2); win = int(view.bet * view.multi)
            embed = discord.Embed(title="MINES", color=0x3498DB, description=f"Bet **{fmt(view.bet)}** | {len(view.revealed)}/25\n**x{view.multi}** -> **{fmt(win)}**")
            embed.set_author(name=f"{inter.user.display_name}", icon_url=inter.user.display_avatar.url)
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view)

class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs):
        super().__init__(timeout=180)
        self.uid=uid; self.bet=bet; self.bombs=bombs; self.revealed=set()
        self.bomb_pos=set(random.sample(range(25), bombs)); self.multi=1.0
        for i in range(25): self.add_item(MineBtn(i))

@bot.tree.command(name="mines", description="Play mines")
async def mines_cmd(interaction: discord.Interaction, bet: str, bombs: int = 5):
    await interaction.response.defer()
    try: bval=parse_amount(bet)
    except: return await interaction.followup.send("Use 1M")
    d=get_data(interaction.user.id)
    if d["balance"]<bval: return await interaction.followup.send(f"Need {fmt(bval)}")
    d["balance"]-=bval; view=MinesView(interaction.user.id,bval,bombs)
    cash=discord.ui.Button(label="Cashout", style=discord.ButtonStyle.success, row=4, emoji="💸")
    async def cash_cb(inter: discord.Interaction):
        if inter.user.id!=view.uid: return await inter.response.send_message("Not yours", ephemeral=True)
        await inter.response.defer()
        if len(view.revealed)==0: return await inter.followup.send("Find 1 gem!", ephemeral=True)
        win=int(view.bet*view.multi); d2=get_data(inter.user.id); d2["balance"]+=win; d2["wagered"]+=view.bet; d2["profit"]+=win-view.bet
        for c in view.children: c.disabled=True
        embed=discord.Embed(title="CASHOUT", description=f"Won {fmt(win)} x{view.multi}", color=0xF1C40F)
        await inter.followup.edit_message(inter.message.id, embed=embed, view=view); await save_all(); view.stop()
    cash.callback=cash_cb; view.add_item(cash)
    embed=discord.Embed(title="MINES", description=f"Bet {fmt(bval)} | {bombs} Bombs", color=0x9B59B6)
    embed.set_author(name=f"{interaction.user.display_name}'s Mines", icon_url=interaction.user.display_avatar.url)
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name="give", description="Give gems")
async def give_cmd(interaction: discord.Interaction, user: discord.Member, amount: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("Admin only", ephemeral=True)
    await interaction.response.defer()
    bval=parse_amount(amount); d=get_data(user.id); d["balance"]+=bval; d["deposited"]+=bval; await save_all()
    await interaction.followup.send(f"Gave {fmt(bval)} to {user.mention}")

bot.run(os.getenv("TOKEN"))
