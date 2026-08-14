import discord, os, json, random, time
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="?", intents=intents)

DB = "balances.json"
COOLDOWN_FILE = "cooldowns.json"

def load(f):
    if not os.path.exists(f): return {}
    with open(f, "r") as fp: return json.load(fp)
def save(f, data):
    with open(f, "w") as fp: json.dump(fp, data) if False else json.dump(data, fp)

def fmt(n):
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)

def get_user(uid):
    db = load(DB)
    if str(uid) not in db:
        db[str(uid)] = {"balance": 0, "deposited": 0, "withdrawn": 0, "wagered": 0, "profit": 0}
        save(DB, db)
    return db[str(uid)], db

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Online {bot.user}")

# --- BALANCE (clean) ---
@bot.tree.command(name="balance", description="Check balance")
async def balance(interaction: discord.Interaction):
    data, db = get_user(interaction.user.id)
    embed = discord.Embed(title=f"{interaction.user.display_name}'s balance", color=0x2B88D8)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.description = (
        f"💎 **Balance** `{fmt(data['balance'])} ({data['balance']:,})`\n"
        f"📥 **Deposited** `{data['deposited']}`\n"
        f"📤 **Withdrawn** `{data['withdrawn']}`\n"
        f"💎 **Wagered** `{fmt(data['wagered'])}`\n"
        f"💸 **Profit** `{fmt(data['profit'])}`"
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Advanced Stats", style=discord.ButtonStyle.secondary, disabled=True))
    await interaction.response.send_message(embed=embed, view=view)

# --- DAILY 24H ---
@bot.tree.command(name="daily", description="Claim daily reward every 24h")
async def daily(interaction: discord.Interaction):
    cds = load(COOLDOWN_FILE)
    now = time.time()
    last = cds.get(str(interaction.user.id), 0)
    if now - last < 86400:
        left = int(86400 - (now - last))
        h = left // 3600
        m = (left % 3600)//60
        return await interaction.response.send_message(f"⏰ Come back in {h}h {m}m! Daily is every 24h.", ephemeral=True)
    
    data, db = get_user(interaction.user.id)
    reward = 5000000
    data["balance"] += reward
    data["profit"] += reward
    db[str(interaction.user.id)] = data
    cds[str(interaction.user.id)] = now
    save(DB, db)
    save(COOLDOWN_FILE, cds)
    await interaction.response.send_message(f"✅ You claimed **{fmt(reward)}**! Balance: {fmt(data['balance'])}", ephemeral=True)

# --- MINES GAME ---
class MinesView(discord.ui.View):
    def __init__(self, user_id, bet, bombs=3):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bet = bet
        self.bombs = bombs
        self.revealed = set()
        self.bomb_positions = set(random.sample(range(25), bombs))
        self.multiplier = 1.0
        for i in range(25):
            self.add_item(MineButton(i))

    def get_embed(self):
        won = int(self.bet * self.multiplier) if len(self.revealed) > 0 else 0
        embed = discord.Embed(title="💣 Mines", color=0x2B88D8)
        embed.description = f"**Bet:** {fmt(self.bet)} | **Bombs:** {self.bombs}\n**Next Profit:** {fmt(won)} (x{self.multiplier:.2f})\nClick a tile, cashout before boom!"
        return embed

class MineButton(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(style=discord.ButtonStyle.secondary, label="❓", row=idx//5)
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        view: MinesView = self.view
        if interaction.user.id != view.user_id:
            return await interaction.response.send_message("Not your game!", ephemeral=True)
        
        if self.idx in view.revealed or self.idx in view.bomb_positions and view.revealed:
            return

        if self.idx in view.bomb_positions:
            # BOOM - lose
            data, db = get_user(interaction.user.id)
            data["wagered"] += view.bet
            data["profit"] -= view.bet
            db[str(interaction.user.id)] = data
            save(DB, db)
            
            for child in view.children:
                if isinstance(child, MineButton):
                    if child.idx in view.bomb_positions:
                        child.label = "💣"
                        child.style = discord.ButtonStyle.danger
                    elif child.idx in view.revealed:
                        child.label = "💎"
                        child.style = discord.ButtonStyle.success
                    child.disabled = True
            embed = discord.Embed(title="💥 BOOM! You hit a mine!", description=f"Lost {fmt(view.bet)}", color=0xFF0000)
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()
        else:
            view.revealed.add(self.idx)
            self.label = "💎"
            self.style = discord.ButtonStyle.success
            self.disabled = True
            view.multiplier = round(1 + len(view.revealed) * 0.24 + (view.bombs * 0.15), 2)
            await interaction.response.edit_message(embed=view.get_embed(), view=view)

@bot.tree.command(name="mines", description="Play mines min 1M bet")
@app_commands.describe(bet="Amount to bet (min 1M)", bombs="Number of bombs 1-10")
async def mines(interaction: discord.Interaction, bet: int, bombs: int = 3):
    if bet < 1000000:
        return await interaction.response.send_message("❌ Minimum bet is **1M**!", ephemeral=True)
    if bombs < 1 or bombs > 10:
        return await interaction.response.send_message("Bombs must be 1-10", ephemeral=True)

    data, db = get_user(interaction.user.id)
    if data["balance"] < bet:
        return await interaction.response.send_message(f"❌ No balance! You have {fmt(data['balance'])}", ephemeral=True)
    
    data["balance"] -= bet
    db[str(interaction.user.id)] = data
    save(DB, db)

    view = MinesView(interaction.user.id, bet, bombs)
    
    # Add cashout button
    cashout = discord.ui.Button(label="Cashout", style=discord.ButtonStyle.primary, row=4, emoji="💸")
    async def cashout_cb(inter: discord.Interaction):
        if inter.user.id != view.user_id:
            return
        if len(view.revealed) == 0:
            return await inter.response.send_message("Reveal at least 1 tile!", ephemeral=True)
        profit = int(view.bet * view.multiplier)
        data2, db2 = get_user(inter.user.id)
        data2["balance"] += profit
        data2["wagered"] += view.bet
        data2["profit"] += profit - view.bet
        db2[str(inter.user.id)] = data2
        save(DB, db2)
        for c in view.children: c.disabled = True
        embed = discord.Embed(title="✅ Cashed Out!", description=f"Won **{fmt(profit)}** x{view.multiplier}", color=0x00FF00)
        await inter.response.edit_message(embed=embed, view=view)
        view.stop()
    cashout.callback = cashout_cb
    view.add_item(cashout)

    await interaction.response.send_message(embed=view.get_embed(), view=view)

bot.run(os.getenv("TOKEN"))
