import discord, os, json, random, time
from discord import app_commands
from discord.ext import commands

OWNER_ID = 1536946071769718784 # Elix - Owner only can give/remove

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
        balances[uid] = {"balance":0, "deposited":0, "withdrawn":0, "wagered":0, "profit":0}
    for k in ["deposited","withdrawn","wagered","profit"]:
        if k not in balances[uid]: balances[uid][k]=0
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
    d = get_data(interaction.user.id)
    desc = f"💎 **Balance** `{fmt(d['balance'])} ({d['balance']:,})`\n"
    desc += f"📥 **Deposited** `{fmt(d['deposited'])}`\n"
    desc += f"📤 **Withdrawn** `{fmt(d['withdrawn'])}`\n"
    desc += f"💎 **Wagered** `{fmt(d['wagered'])}`\n"
    desc += f"💸 **Profit** `{fmt(d['profit'])}`"
    embed = discord.Embed(title=f"{interaction.user.display_name}'s balance", description=desc, color=0x2B2D31)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

class MineBtn(discord.ui.Button):
    def __init__(self, idx, is_bomb=False, revealed=False):
        style = discord.ButtonStyle.secondary
        label = "?"
        if revealed:
            style = discord.ButtonStyle.danger if is_bomb else discord.ButtonStyle.secondary
            label = "💣" if is_bomb else "💎"
        super().__init__(style=style, label=label, row=idx//5, disabled=revealed)
        self.idx = idx
    async def callback(self, inter: discord.Interaction):
        view: MinesView = self.view
        if inter.user.id!= view.uid:
            return await inter.response.send_message("Not your game!", ephemeral=True)
        view.revealed.add(self.idx)
        if self.idx in view.bomb_pos:
            embed = discord.Embed(color=0xED4245)
            embed.title = "💣 Mines - BUSTED"
            gems_found = len([r for r in view.revealed if r not in view.bomb_pos])
            total_gems = 25 - view.bombs
            reached = round(1.0 + gems_found * 0.24, 2)
            embed.description = f"💎 **Bet** `{fmt(view.bet)}`\n✨ **Reached** `{reached}x`\n💎 **Gems found** `{gems_found}/{total_gems}`\n💣 **Bombs** `{view.bombs}`\n\nYou struck a bomb and lost your bet. 💣 shows every mine."
            new_view = discord.ui.View()
            for i in range(25):
                is_bomb = i in view.bomb_pos
                new_view.add_item(MineBtn(i, is_bomb=is_bomb, revealed=True))
            d = get_data(inter.user.id); d["wagered"] += view.bet; d["profit"] -= view.bet
            await save_all()
            await inter.response.edit_message(embed=embed, view=new_view)
        else:
            gems_found = len([r for r in view.revealed if r not in view.bomb_pos])
            total_gems = 25 - view.bombs
            reached = round(1.0 + gems_found * 0.26, 2)
            current_win = int(view.bet * reached)
            embed = discord.Embed(color=0x57F287)
            embed.title = "💣 Mines"
            embed.description = f"💎 **Bet** `{fmt(view.bet)}`\n✨ **Reached** `{reached}x`\n💎 **Gems found** `{gems_found}/{total_gems}`\n💣 **Bombs** `{view.bombs}`\n\nCurrent win: **{fmt(current_win)}**"
            new_view = MinesView(view.uid, view.bet, view.bombs)
            new_view.revealed = view.revealed; new_view.bomb_pos = view.bomb_pos
            new_view.clear_items()
            for i in range(25):
                is_bomb = i in view.bomb_pos; is_rev = i in view.revealed
                btn = MineBtn(i, is_bomb=is_bomb, revealed=is_rev)
                if is_rev and not is_bomb: btn.style = discord.ButtonStyle.success
                new_view.add_item(btn)
            cash = discord.ui.Button(label=f"Cashout {fmt(current_win)}", style=discord.ButtonStyle.success, row=4, emoji="💸")
            async def cash_cb(c_inter: discord.Interaction):
                if c_inter.user.id!= new_view.uid: return await c_inter.response.send_message("Not yours", ephemeral=True)
                win = int(new_view.bet * reached)
                d2 = get_data(c_inter.user.id); d2["balance"] += win; d2["wagered"] += new_view.bet; d2["profit"] += win - new_view.bet; d2["withdrawn"] += win
                await save_all()
                e = discord.Embed(color=0xFEE75C); e.title = "💰 Mines - CASHOUT"
                e.description = f"💎 **Bet** `{fmt(new_view.bet)}`\n✨ **Reached** `{reached}x`\n💎 **Gems found** `{gems_found}/{total_gems}`\n\nYou cashed out **{fmt(win)}**!"
                await c_inter.response.edit_message(embed=e, view=discord.ui.View())
            cash.callback = cash_cb; new_view.add_item(cash)
            await inter.response.edit_message(embed=embed, view=new_view)

class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs):
        super().__init__(timeout=180)
        self.uid = uid; self.bet = bet; self.bombs = bombs; self.revealed = set()
        self.bomb_pos = set(random.sample(range(25), bombs))
        for i in range(25): self.add_item(MineBtn(i))

@bot.tree.command(name="mines", description="Play mines")
async def mines_cmd(interaction: discord.Interaction, bet: str, bombs: int = 3):
    try: bval = parse_amount(bet)
    except: return await interaction.response.send_message("Use like 1M", ephemeral=True)
    if bval < 100000: return await interaction.response.send_message("Min 100K", ephemeral=True)
    d = get_data(interaction.user.id)
    if d["balance"] < bval: return await interaction.response.send_message(f"You need {fmt(bval)} have {fmt(d['balance'])}", ephemeral=True)
    d["balance"] -= bval; await save_all()
    view = MinesView(interaction.user.id, bval, bombs)
    embed = discord.Embed(color=0x5865F2); embed.title = "💣 Mines"
    embed.description = f"💎 **Bet** `{fmt(bval)}`\n✨ **Reached** `1.0x`\n💎 **Gems found** `0/{25-bombs}`\n💣 **Bombs** `{bombs}`\n\nFind 💎 avoid 💣"
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="daily", description="Claim 15M every 24h")
async def daily_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    uid = str(interaction.user.id); now = time.time(); last = cooldowns.get(uid, 0)
    if now - last < 86400:
        left = int(86400 - (now - last))
        return await interaction.followup.send(f"Come back in {left//3600}h {(left%3600)//60}m", ephemeral=True)
    d = get_data(interaction.user.id); d["balance"] += 15000000; d["deposited"] += 15000000
    cooldowns[uid] = now; await save_all()
    await interaction.followup.send(f"✅ +15M! Balance: {fmt(d['balance'])}", ephemeral=True)

@bot.tree.command(name="give", description="Give gems [OWNER ONLY]")
async def give_cmd(interaction: discord.Interaction, user: discord.Member, amount: str):
    if interaction.user.id!= OWNER_ID: return await interaction.response.send_message("❌ Only owner can use!", ephemeral=True)
    try: bval = parse_amount(amount)
    except: return await interaction.response.send_message("Use 1M", ephemeral=True)
    d = get_data(user.id); d["balance"] += bval; d["deposited"] += bval; await save_all()
    await interaction.response.send_message(f"✅ Gave {fmt(bval)} to {user.mention}")

@bot.tree.command(name="removegems", description="Remove gems [OWNER ONLY]")
async def remove_cmd(interaction: discord.Interaction, user: discord.Member, amount: str):
    if interaction.user.id!= OWNER_ID: return await interaction.response.send_message("❌ Only owner can use!", ephemeral=True)
    try: bval = parse_amount(amount)
    except: return await interaction.response.send_message("Use 1M", ephemeral=True)
    d = get_data(user.id); d["balance"] = max(0, d["balance"] - bval); await save_all()
    await interaction.response.send_message(f"✅ Removed {fmt(bval)} from {user.mention} | New: {fmt(d['balance'])}")

@bot.tree.command(name="tip", description="Tip gems to a member")
async def tip_cmd(interaction: discord.Interaction, user: discord.Member, amount: str):
    await interaction.response.defer()
    if user.id == interaction.user.id: return await interaction.followup.send("Can't tip yourself!")
    try: bval = parse_amount(amount)
    except: return await interaction.followup.send("Use 1M")
    d = get_data(interaction.user.id)
    if d["balance"] < bval: return await interaction.followup.send(f"You have {fmt(d['balance'])} only!")
    d["balance"] -= bval; d2 = get_data(user.id); d2["balance"] += bval; await save_all()
    await interaction.followup.send(f"💸 {interaction.user.mention} tipped **{fmt(bval)}** to {user.mention}")

bot.run(os.getenv("TOKEN"))
