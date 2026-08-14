import discord
import os
import json
import random
import time
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

balances = {}
cooldowns = {}

def load_file(name):
    if not os.path.exists(name):
        return {}
    try:
        with open(name, "r") as f:
            return json.load(f)
    except:
        return {}

async def save_all():
    with open("balances.json", "w") as f:
        json.dump(balances, f)
    with open("cooldowns.json", "w") as f:
        json.dump(cooldowns, f)

def fmt(n):
    if n >= 1000000000:
        return f"{n/1000000000:.2f}B"
    if n >= 1000000:
        return f"{n/1000000:.2f}M"
    if n >= 1000:
        return f"{n/1000:.1f}K"
    return str(int(n))

def parse_amount(s):
    s = str(s).upper().replace(",", "").strip()
    mult = 1
    if s.endswith("B"):
        mult = 1000000000
        s = s[:-1]
    elif s.endswith("M"):
        mult = 1000000
        s = s[:-1]
    elif s.endswith("K"):
        mult = 1000
        s = s[:-1]
    return int(float(s) * mult)

def get_data(uid):
    uid = str(uid)
    if uid not in balances:
        balances[uid] = {"balance": 0}
    return balances[uid]

@bot.event
async def on_ready():
    global balances, cooldowns
    balances = load_file("balances.json")
    cooldowns = load_file("cooldowns.json")
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

@bot.tree.command(name="balance", description="Check balance")
async def balance_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    d = get_data(interaction.user.id)
    embed = discord.Embed(title="💎 BALANCE", color=0x9B59B6, description=f"**{fmt(d['balance'])}**\n{d['balance']:,} gems")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="daily", description="Claim 15M every 24h")
async def daily_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id)
    now = time.time()
    last = cooldowns.get(uid, 0)
    if now - last < 86400:
        left = int(86400 - (now - last))
        h = left // 3600
        m = (left % 3600) // 60
        return await interaction.followup.send(f"Wait {h}h {m}m", ephemeral=True)
    d = get_data(interaction.user.id)
    d["balance"] += 15000000
    cooldowns[uid] = now
    await save_all()
    await interaction.followup.send(f"✅ +15M! You now have {fmt(d['balance'])}", ephemeral=True)

class MineBtn(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, label="?", row=idx // 5)
        self.idx = idx
    async def callback(self, inter: discord.Interaction):
        view = self.view
        if inter.user.id!= view.uid:
            return await inter.response.send_message("Not your game", ephemeral=True)
        await inter.response.defer()
        if self.idx in view.bomb_pos:
            d = get_data(inter.user.id)
            for c in view.children:
                if isinstance(c, MineBtn):
                    c.disabled = True
                    if c.idx in view.bomb_pos:
                        c.label = "💣"
                        c.style = discord.ButtonStyle.danger
            embed = discord.Embed(title="💥 BOOM LOST", description=f"Lost {fmt(view.bet)}", color=0xE74C3C)
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view)
            await save_all()
            view.stop()
        else:
            view.revealed.add(self.idx)
            self.label = "💎"
            self.style = discord.ButtonStyle.success
            self.disabled = True
            view.multi = round(1 + len(view.revealed) * 0.25, 2)
            embed = discord.Embed(title="💣 MINES", color=0x3498DB, description=f"Bet: {fmt(view.bet)} | x{view.multi} -> {fmt(int(view.bet*view.multi))}")
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view)

class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs):
        super().__init__(timeout=180)
        self.uid = uid
        self.bet = bet
        self.bombs = bombs
        self.revealed = set()
        self.bomb_pos = set(random.sample(range(25), bombs))
        self.multi = 1.0
        for i in range(25):
            self.add_item(MineBtn(i))

@bot.tree.command(name="mines", description="Play mines")
@app_commands.describe(bet="1M, 10M", bombs="1-20 bombs")
async def mines_cmd(interaction: discord.Interaction, bet: str, bombs: int = 5):
    await interaction.response.defer()
    try:
        bval = parse_amount(bet)
    except:
        return await interaction.followup.send("Use 1M")
    d = get_data(interaction.user.id)
    if d["balance"] < bval:
        return await interaction.followup.send(f"You have {fmt(d['balance'])}")
    d["balance"] -= bval
    view = MinesView(interaction.user.id, bval, bombs)
    cash_btn = discord.ui.Button(label="Cashout", style=discord.ButtonStyle.success, row=4)
    async def cash_cb(inter: discord.Interaction):
        if inter.user.id!= view.uid:
            return await inter.response.send_message("Not yours", ephemeral=True)
        await inter.response.defer()
        if len(view.revealed) == 0:
            return await inter.followup.send("Find 1 gem first", ephemeral=True)
        win = int(view.bet * view.multi)
        d2 = get_data(inter.user.id)
        d2["balance"] += win
        for c in view.children:
            c.disabled = True
        embed = discord.Embed(title="💸 CASHOUT", description=f"Won {fmt(win)} x{view.multi}", color=0x2ECC71)
        await inter.followup.edit_message(inter.message.id, embed=embed, view=view)
        await save_all()
        view.stop()
    cash_btn.callback = cash_cb
    view.add_item(cash_btn)
    embed = discord.Embed(title="💣 MINES", description=f"Bet {fmt(bval)} | Bombs {bombs}", color=0x9B59B6)
    await interaction.followup.send(embed=embed, view=view)

def card_value(cards):
    v = 0
    a = 0
    for c in cards:
        r = c[:-1]
        if r in ["J", "Q", "K"]:
            v += 10
        elif r == "A":
            v += 11
            a += 1
        else:
            v += int(r)
    while v > 21 and a > 0:
        v -= 10
        a -= 1
    return v

class BJView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=120)
        self.uid = uid
        self.bet = bet
        deck = [f"{r}{s}" for r in ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"] for s in ["♠", "♥", "♦", "♣"]] * 2
        random.shuffle(deck)
        self.deck = deck
        self.p = [deck.pop(), deck.pop()]
        self.d = [deck.pop(), deck.pop()]

@bot.tree.command(name="blackjack", description="Play blackjack 2x win 2.5x BJ")
async def blackjack_cmd(interaction: discord.Interaction, bet: str):
    await interaction.response.defer()
    try:
        bval = parse_amount(bet)
    except:
        return await interaction.followup.send("Use 1M")
    d = get_data(interaction.user.id)
    if d["balance"] < bval:
        return await interaction.followup.send(f"You have {fmt(d['balance'])}")
    d["balance"] -= bval
    view = BJView(interaction.user.id, bval)

    def make_embed(hide=True):
        pv = card_value(view.p)
        dv = card_value([view.d[0]]) if hide else card_value(view.d)
        embed = discord.Embed(title="♠️ BLACKJACK", color=0x1ABC9C)
        embed.add_field(name=f"YOU [{pv}]", value=" ".join(view.p), inline=False)
        if hide:
            embed.add_field(name=f"DEALER [{dv}+?]", value=f"{view.d[0]} 🂠", inline=False)
        else:
            embed.add_field(name=f"DEALER [{dv}]", value=" ".join(view.d), inline=False)
        embed.set_footer(text=f"Bet {fmt(bval)} | 2x Win | 2.5x Blackjack")
        return embed

    pv = card_value(view.p)
    dv = card_value(view.d)
    if pv == 21 and dv!= 21:
        win = int(bval * 2.5)
        d["balance"] += win
        await save_all()
        embed = discord.Embed(title="🔥 BLACKJACK 2.5x!", description=f"Won {fmt(win)}", color=0xF1C40F)
        return await interaction.followup.send(embed=embed)

    hit = discord.ui.Button(label="HIT", style=discord.ButtonStyle.primary)
    stand = discord.ui.Button(label="STAND", style=discord.ButtonStyle.success)

    async def hit_cb(inter: discord.Interaction):
        if inter.user.id!= view.uid:
            return await inter.response.send_message("Not yours", ephemeral=True)
        await inter.response.defer()
        view.p.append(view.deck.pop())
        if card_value(view.p) > 21:
            embed = make_embed(False)
            embed.title = f"BUST {card_value(view.p)}"
            embed.color = 0xE74C3C
            for c in view.children:
                c.disabled = True
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view)
            await save_all()
            view.stop()
        else:
            await inter.followup.edit_message(inter.message.id, embed=make_embed(True), view=view)

    async def stand_cb(inter: discord.Interaction):
        if inter.user.id!= view.uid:
            return await inter.response.send_message("Not yours", ephemeral=True)
        await inter.response.defer()
        while card_value(view.d) < 17:
            view.d.append(view.deck.pop())
        pv = card_value(view.p)
        dv = card_value(view.d)
        d2 = get_data(inter.user.id)
        if dv > 21 or pv > dv:
            win = bval * 2
            d2["balance"] += win
            embed = make_embed(False)
            embed.title = f"WIN {pv} vs {dv}"
            embed.description = f"Won {fmt(win)}"
            embed.color = 0x2ECC71
        elif pv == dv:
            d2["balance"] += bval
            embed = make_embed(False)
            embed.title = f"PUSH {pv}"
        else:
            embed = make_embed(False)
            embed.title = f"LOSE {pv} vs {dv}"
            embed.color = 0xE74C3C
        for c in view.children:
            c.disabled = True
        await inter.followup.edit_message(inter.message.id, embed=embed, view=view)
        await save_all()
        view.stop()

    hit.callback = hit_cb
    stand.callback = stand_cb
    view.add_item(hit)
    view.add_item(stand)
    await interaction.followup.send(embed=make_embed(True), view=view)

@bot.tree.command(name="give", description="Admin give")
async def give_cmd(interaction: discord.Interaction, user: discord.Member, amount: str):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Admin only", ephemeral=True)
    await interaction.response.defer()
    bval = parse_amount(amount)
    d = get_data(user.id)
    d["balance"] += bval
    await save_all()
    await interaction.followup.send(f"Gave {fmt(bval)} to {user.mention}")

bot.run(os.getenv("TOKEN"))
