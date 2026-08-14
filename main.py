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
        balances[uid] = {"balance":0, "bank":0, "wagered":0, "deposited":0, "withdrawn":0, "profit":0}
    # ensure old users have new keys
    for k in ["bank","wagered","deposited","withdrawn","profit"]:
        if k not in balances[uid]: balances[uid][k]=0
    return balances[uid]

@bot.event
async def on_ready():
    global balances, cooldowns
    balances = load_file("balances.json")
    cooldowns = load_file("cooldowns.json")
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

# BALANCE WITH GEMS / BANK / WAGERED / DEPOSITS
@bot.tree.command(name="balance", description="Check vault")
async def balance_cmd(interaction: discord.Interaction):
    await interaction.response.defer()
    d = get_data(interaction.user.id)
    embed = discord.Embed(title="💎 VAULT", color=0xA020F0)
    embed.set_author(name=f"{interaction.user.display_name}'s Vault", icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="💰 Gems", value=f"**{fmt(d['balance'])}**\n{d['balance']:,}", inline=True)
    embed.add_field(name="🏦 Bank", value=f"**{fmt(d['bank'])}**\nWithdrawable", inline=True)
    embed.add_field(name="📊 Stats", value=f"Wagered: {fmt(d['wagered'])}\nDeposited: {fmt(d['deposited'])}\nWithdrawn: {fmt(d['withdrawn'])}\nProfit: {fmt(d['profit'])}", inline=False)
    await interaction.followup.send(embed=embed)

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
    d["profit"] += 15000000
    cooldowns[uid] = now
    await save_all()
    await interaction.followup.send(f"✅ +15M! Balance: {fmt(d['balance'])}", ephemeral=True)

# MINES FIXED - NO LOADING
class MineBtn(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, label="?", row=idx//5)
        self.idx = idx
    async def callback(self, inter: discord.Interaction):
        view = self.view
        if inter.user.id!= view.uid:
            return await inter.response.send_message("Not your game!", ephemeral=True)
        if self.idx in view.revealed:
            return await inter.response.defer()
        await inter.response.defer()
        if self.idx in view.bomb_pos:
            d = get_data(inter.user.id)
            d["wagered"] += view.bet
            d["profit"] -= view.bet
            for c in view.children:
                if isinstance(c, MineBtn):
                    c.disabled = True
                    if c.idx in view.bomb_pos:
                        c.label = "💣"; c.style = discord.ButtonStyle.danger
            embed = discord.Embed(title="💥 BOOM!", description=f"{inter.user.mention} hit a bomb! Lost {fmt(view.bet)}", color=0xE74C3C)
            embed.set_author(name=f"{inter.user.display_name}'s Mines Game", icon_url=inter.user.display_avatar.url)
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view)
            await save_all()
            view.stop()
        else:
            view.revealed.add(self.idx)
            self.label = "💎"; self.style = discord.ButtonStyle.success; self.disabled = True
            gems = len(view.revealed)
            view.multi = round(1 + (gems * 0.3), 2)
            win = int(view.bet * view.multi)
            embed = discord.Embed(title="💣 MINES", color=0x3498DB, description=f"Bet **{fmt(view.bet)}** | Gems {gems}/25\n**x{view.multi}** -> **{fmt(win)}**\nBombs: {view.bombs}")
            embed.set_author(name=f"{inter.user.display_name}'s Game", icon_url=inter.user.display_avatar.url)
            embed.set_thumbnail(url=inter.user.display_avatar.url)
            await inter.followup.edit_message(inter.message.id, embed=embed, view=view)

class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs):
        super().__init__(timeout=180)
        self.uid = uid; self.bet = bet; self.bombs = bombs
        self.revealed = set()
        self.bomb_pos = set(random.sample(range(25), bombs))
        self.multi = 1.0
        for i in range(25): self.add_item(MineBtn(i))

@bot.tree.command(name="mines", description="Play mines")
async def mines_cmd(interaction: discord.Interaction, bet: str, bombs: int = 5):
    await interaction.response.defer()
    try: bval = parse_amount(bet)
    except: return await interaction.followup.send("Use like 1M")
    if bval < 100000: return await interaction.followup.send("Min 100K")
    d = get_data(interaction.user.id)
    if d["balance"] < bval: return await interaction.followup.send(f"Need {fmt(bval)} have {fmt(d['balance'])}")
    d["balance"] -= bval
    view = MinesView(interaction.user.id, bval, bombs)

    cash = discord.ui.Button(label=f"Cashout x1.0", style=discord.ButtonStyle.success, row=4, emoji="💸")
    async def cash_cb(inter: discord.Interaction):
        if inter.user.id!= view.uid: return await inter.response.send_message("Not yours", ephemeral=True)
        await inter.response.defer()
        if len(view.revealed) == 0: return await inter.followup.send("Find 1 gem!", ephemeral=True)
        win = int(view.bet * view.multi)
        d2 = get_data(inter.user.id)
        d2["balance"] += win
        d2["wagered"] += view.bet
        d2["profit"] += win - view.bet
        for c in view.children: c.disabled = True
        embed = discord.Embed(title="✅ CASHOUT", description=f"Won **{fmt(win)}** x{view.multi}", color=0xF1C40F)
        embed.set_author(name=f"{inter.user.display_name}", icon_url=inter.user.display_avatar.url)
        await inter.followup.edit_message(inter.message.id, embed=embed, view=view)
        await save_all()
        view.stop()
    cash.callback = cash_cb
    view.add_item(cash)

    embed = discord.Embed(title="💣 MINES", description=f"Bet {fmt(bval)} | {bombs} Bombs\nFind 💎 avoid 💣", color=0x9B59B6)
    embed.set_author(name=f"{interaction.user.display_name}'s Mines Game", icon_url=interaction.user.display_avatar.url)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction
