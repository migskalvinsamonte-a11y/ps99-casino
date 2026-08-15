import discord, os, json, random, asyncio
from discord.ext import commands

TOKEN = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
DATA_FILE = "data.json"
OWNER_ID = 1536946071769718784

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
data = {}

def load_data():
    global data
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    else:
        data = {}

async def save_all():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def get_data(uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {"balance": 10000, "deposited":0, "withdrawn":0, "wagered":0, "profit":0}
    for k in ["deposited","withdrawn","wagered","profit","balance"]:
        if k not in data[uid]:
            data[uid][k]=0
    return data[uid]

def parse_amount(s, bal=0):
    s=str(s).lower().replace(",","").strip()
    if s in ["all","max"]:
        return bal
    m=1
    if s.endswith("k"):
        m=1000
        s=s[:-1]
    elif s.endswith("m"):
        m=1000000
        s=s[:-1]
    elif s.endswith("b"):
        m=1000000000
        s=s[:-1]
    return int(float(s)*m)

def fmt(n):
    if n>=1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n>=1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n>=1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))

def fmt_full(n):
    return f"{int(n):,}"

def no_money_embed(current, needed):
    embed = discord.Embed(color=0xED4245, title="Not enough gems!")
    embed.description = f"Your balance {fmt(current)} ({fmt_full(current)})\nYou need {fmt(needed)} ({fmt_full(needed)})"
    return embed

@bot.event
async def on_ready():
    load_data()
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

class BalanceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label="Advanced Stats", style=discord.ButtonStyle.secondary, disabled=True))

@bot.tree.command(name="balance", description="Check balance")
async def bal_cmd(inter: discord.Interaction, user: discord.Member=None):
    t=user or inter.user
    d=get_data(t.id)
    bal_str = f"{fmt(d['balance'])} ({fmt_full(d['balance'])})"
    dep_str = f"{fmt(d['deposited'])}"
    with_str = f"{fmt(d['withdrawn'])}"
    wag_str = f"{fmt(d['wagered'])}"
    prof_str = f"{fmt(d['profit'])}"
    embed = discord.Embed(color=0x2B2D31, title=f"{t.display_name}'s balance")
    embed.description = f"💎 Balance {bal_str}\n📥 Deposited {dep_str}\n📤 Withdrawn {with_str}\n💎 Wagered {wag_str}\n💸 Profit {prof_str}"
    embed.set_thumbnail(url=t.display_avatar.url)
    await inter.response.send_message(embed=embed, view=BalanceView())

@bot.tree.command(name="addgems", description="Owner only")
async def add_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if inter.user.id!= OWNER_ID:
        return await inter.response.send_message("Owner only", ephemeral=True)
    try:
        b=parse_amount(amount)
    except:
        return await inter.response.send_message("Bad amount", ephemeral=True)
    d=get_data(user.id)
    d["balance"]+=b
    d["deposited"]+=b
    await save_all()
    await inter.response.send_message(f"Added {fmt(b)} to {user.mention} | Now {fmt(d['balance'])}")

@bot.tree.command(name="removegems", description="Owner only")
async def rem_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if inter.user.id!= OWNER_ID:
        return await inter.response.send_message("Owner only", ephemeral=True)
    try:
        b=parse_amount(amount)
    except:
        return await inter.response.send_message("Bad amount", ephemeral=True)
    d=get_data(user.id)
    d["balance"]=max(0,d["balance"]-b)
    await save_all()
    await inter.response.send_message(f"Removed {fmt(b)} from {user.mention} | Now {fmt(d['balance'])}")

@bot.tree.command(name="tip", description="Tip anyone")
async def tip_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if user.id==inter.user.id:
        return await inter.response.send_message("Cant tip self", ephemeral=True)
    d=get_data(inter.user.id)
    try:
        b=parse_amount(amount, d["balance"])
    except:
        return await inter.response.send_message("Bad amount", ephemeral=True)
    if d["balance"]<b:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], b), ephemeral=True)
    d["balance"]-=b
    get_data(user.id)["balance"]+=b
    await save_all()
    await inter.response.send_message(f"{inter.user.mention} tipped {fmt(b)} gems to {user.mention}")

# MINES FIXED - NO "APPLICATION DID NOT RESPOND"
class MinesView(discord.ui.View):
    def __init__(self, uid, bet, bombs=23):
        super().__init__(timeout=300)
        self.uid = uid
        self.bet = bet
        self.bombs = bombs
        self.mine_pos = set(random.sample(range(25), bombs))
        self.revealed = set()
        self.mult = 1.0
        for i in range(25):
            btn = discord.ui.Button(label="?", style=discord.ButtonStyle.secondary, custom_id=str(i), row=i//5)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, idx):
        async def callback(inter: discord.Interaction):
            if inter.user.id != self.uid:
                return await inter.response.send_message("Not your game!", ephemeral=True)
            if idx in self.revealed:
                return await inter.response.defer()
            await inter.response.defer()
            self.revealed.add(idx)
            if idx in self.mine_pos:
                embed = discord.Embed(color=0xED4245, title="Mines - BUSTED")
                gems_found = len([r for r in self.revealed if r not in self.mine_pos])
                total_gems = 25 - self.bombs
                embed.description = f"💎 Bet {fmt(self.bet)}\n✨ Reached {self.mult:.1f}x\n💎 Gems found {gems_found}/{total_gems}\n💣 Bombs {self.bombs}\n\nYou struck a bomb and lost your bet."
                embed.set_thumbnail(url=inter.user.display_avatar.url)
                final_view = discord.ui.View()
                for j in range(25):
                    row = j // 5
                    if j in self.mine_pos:
                        b = discord.ui.Button(label="BOMB", style=discord.ButtonStyle.danger, row=row, disabled=True)
                        if j == idx:
                            b.label = "BOOM"
                    else:
                        b = discord.ui.Button(label="GEM", style=discord.ButtonStyle.secondary, row=row, disabled=True)
                    final_view.add_item(b)
                d = get_data(inter.user.id)
                d["profit"] -= self.bet
                d["wagered"] += self.bet
                await save_all()
                await inter.edit_original_response(embed=embed, view=final_view)
                self.stop()
                return
            gems_found = len([r for r in self.revealed if r not in self.mine_pos])
            self.mult = round(1.0 + gems_found * 0.25 + (gems_found ** 2) * 0.15, 2)
            if gems_found == 0:
                self.mult = 1.0
            embed = discord.Embed(color=0x2B2D31, title="Mines")
            total_gems = 25 - self.bombs
            win_now = int(self.bet * self.mult)
            embed.description = f"💎 Bet {fmt(self.bet)}\n✨ Reached {self.mult:.1f}x\n💎 Gems found {gems_found}/{total_gems}\n💣 Bombs {self.bombs}\n\nCurrent {fmt(win_now)}"
            embed.set_thumbnail(url=inter.user.display_avatar.url)
            new_view = MinesView(self.uid, self.bet, self.bombs)
            new_view.mine_pos = self.mine_pos
            new_view.revealed = self.revealed
            new_view.mult = self.mult
            new_view.clear_items()
            for j in range(25):
                row = j // 5
                if j in self.revealed:
                    b = discord.ui.Button(label="GEM", style=discord.ButtonStyle.success, row=row, disabled=True)
                else:
                    b = discord.ui.Button(label="?", style=discord.ButtonStyle.secondary, custom_id=str(j), row=row)
                    b.callback = new_view.make_callback(j)
                new_view.add_item(b)
            cash_btn = discord.ui.Button(label=f"CASHOUT {self.mult}x = {fmt(win_now)}", style=discord.ButtonStyle.success, row=4)
            async def cash_callback(c_inter: discord.Interaction):
                if c_inter.user.id != new_view.uid:
                    return await c_inter.response.send_message("Not yours", ephemeral=True)
                await c_inter.response.defer()
                win = int(new_view.bet * new_view.mult)
                d = get_data(c_inter.user.id)
                d["balance"] += win
                d["wagered"] += new_view.bet
                d["profit"] += win - new_view.bet
                d["withdrawn"] += win
                await save_all()
                e = discord.Embed(color=0x57F287, title="Mines - CASHOUT")
                e.description = f"💎 Bet {fmt(new_view.bet)}\n✨ Reached {new_view.mult}x\n💎 Gems {gems_found}/{total_gems}\n\nWon {fmt(win)}!"
                e.set_thumbnail(url=c_inter.user.display_avatar.url)
                await c_inter.edit_original_response(embed=e, view=discord.ui.View())
                new_view.stop()
            cash_btn.callback = cash_callback
            new_view.add_item(cash_btn)
            await inter.edit_original_response(embed=embed, view=new_view)
            self.stop()
        return callback

@bot.tree.command(name="mines", description="Play mines PS99")
async def mines_cmd(inter: discord.Interaction, bet: str, bombs: int=23):
    try:
        bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except:
        return await inter.response.send_message("Bad amount", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval
    await save_all()
    if bombs < 1 or bombs > 24:
        bombs = 23
    view=MinesView(inter.user.id, bval, bombs)
    embed = discord.Embed(color=0x2B2D31, title="Mines")
    total_gems = 25 - bombs
    embed.description = f"💎 Bet {fmt(bval)}\n✨ Reached 1.0x\n💎 Gems found 0/{total_gems}\n💣 Bombs {bombs}"
    embed.set_thumbnail(url=inter.user.display_avatar.url)
    await inter.response.send_message(embed=embed, view=view)

# COLOR DICE CONSISTENT
COLORS = {
    "white": {"emoji": "⬜", "name": "White"},
    "purple": {"emoji": "🟪", "name": "Purple"},
    "green": {"emoji": "🟩", "name": "Green"},
    "red": {"emoji": "🟫", "name": "Red"},
    "blue": {"emoji": "🟦", "name": "Blue"},
    "orange": {"emoji": "🟧", "name": "Orange"},
}
PAYOUTS = {0:0.0, 1:2.0, 2:0.48, 3:3.0, 4:4.0, 5:4.0, 6:4.0}

class ColorDiceView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=120)
        self.uid = uid
        self.bet = bet
        options = []
        for key, val in COLORS.items():
            options.append(discord.SelectOption(label=val["name"], emoji=val["emoji"], value=key))
        select = discord.ui.Select(placeholder="Choose your color...", options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, inter: discord.Interaction):
        if inter.user.id != self.uid:
            return await inter.response.send_message("Not your game!", ephemeral=True)
        picked_key = self.children[0].values[0]
        picked_info = COLORS[picked_key]
        await inter.response.defer()
        embed_roll = discord.Embed(color=0x2B2D31, title="Color Dice")
        embed_roll.description = f"💎 Bet {fmt(self.bet)}\n\n⬜ 🟪 🟩 🟫 🟦 🟧\n\nRolling the dice."
        embed_roll.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.edit_original_response(embed=embed_roll, view=self)
        await asyncio.sleep(1.5)
        dice = random.choices(list(COLORS.keys()), k=6)
        dice_emojis = [COLORS[c]["emoji"] for c in dice]
        dice_str = " ".join(dice_emojis)
        matches = dice.count(picked_key)
        mult = PAYOUTS[matches]
        win = int(self.bet * mult)
        d = get_data(inter.user.id)
        if mult > 0:
            d["balance"] += win
            d["profit"] += win - self.bet
            d["withdrawn"] += win
        else:
            d["profit"] -= self.bet
        d["wagered"] += self.bet
        await save_all()
        if matches == 0:
            final = discord.Embed(color=0xED4245, title="Color Dice")
            final.description = f"💎 Bet {fmt(self.bet)}\nMultiplier {mult}x ({fmt(win)})\n\nDice roll {dice_str}\nYour pick {picked_info['emoji']} {picked_info['name']}\nMatches {matches} - 0 col = 0x LOSE"
        elif matches == 1:
            final = discord.Embed(color=0x57F287, title="Color Dice")
            final.description = f"💎 Bet {fmt(self.bet)}\nMultiplier {mult}x ({fmt(win)})\n\nDice roll {dice_str}\nYour pick {picked_info['emoji']} {picked_info['name']}\nMatches {matches} - 1 col = 2x"
        elif matches == 2:
            final = discord.Embed(color=0xF1C40F, title="Color Dice")
            final.description = f"💎 Bet {fmt(self.bet)}\nMultiplier {mult}x ({fmt(win)})\n\nDice roll {dice_str}\nYour pick {picked_info['emoji']} {picked_info['name']}\nMatches {matches} - 2 col = 0.48x"
        elif matches == 3:
            final = discord.Embed(color=0x57F287, title="Color Dice")
            final.description = f"💎 Bet {fmt(self.bet)}\nMultiplier {mult}x ({fmt(win)})\n\nDice roll {dice_str}\nYour pick {picked_info['emoji']} {picked_info['name']}\nMatches {matches} - 3 col = 3x"
        else:
            final = discord.Embed(color=0x57F287, title="Color Dice")
            final.description = f"💎 Bet {fmt(self.bet)}\nMultiplier {mult}x ({fmt(win)})\n\nDice roll {dice_str}\nYour pick {picked_info['emoji']} {picked_info['name']}\nMatches {matches} - {matches} col = 4x"
        final.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.edit_original_response(embed=final, view=discord.ui.View())
        self.stop()

@bot.tree.command(name="colordice", description="Color dice PS99")
async def colordice_cmd(inter: discord.Interaction, bet: str):
    try:
        bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except:
        return await inter.response.send_message("Bad bet", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval
    await save_all()
    embed = discord.Embed(color=0x2B2D31, title="Color Dice")
    embed.description = f"💎 Bet {fmt(bval)}\n\nPayout\n0 col -> 0x LOSE\n1 col -> 2x\n2 col -> 0.48x\n3 col -> 3x\n4 col -> 4x\n5 col -> 4x\n6 col -> 4x"
    embed.set_thumbnail(url=inter.user.display_avatar.url)
    view = ColorDiceView(inter.user.id, bval)
    await inter.response.send_message(embed=embed, view=view)

# BLACKJACK WITH AVATAR
@bot.tree.command(name="blackjack", description="Play blackjack")
async def blackjack_cmd(inter: discord.Interaction, bet: str):
    try:
        bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except:
        return await inter.response.send_message("Bad bet", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval
    await save_all()
    deck=[2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)
    def score(h):
        s=sum(h)
        c=h.count(11)
        while s>21 and c:
            s-=10
            c-=1
        return s
    ph=[deck.pop(), deck.pop()]
    dh=[deck.pop(), deck.pop()]
    class BJView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
        @discord.ui.button(label="HIT", style=discord.ButtonStyle.primary, emoji="🃏")
        async def hit(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id:
                return await i2.response.send_message("Not yours",ephemeral=True)
            await i2.response.defer()
            ph.append(deck.pop())
            if score(ph)>21:
                e=discord.Embed(color=0xED4245, title="Blackjack - BUST!")
                e.description = f"💎 Bet {fmt(bval)}\nYou {ph} = {score(ph)}\nDealer [{dh[0]}, ?]\n\nLost {fmt(bval)}"
                e.set_thumbnail(url=inter.user.display_avatar.url)
                dd=get_data(i2.user.id)
                dd["wagered"]+=bval
                dd["profit"]-=bval
                await save_all()
                for c in self.children:
                    c.disabled=True
                await i2.edit_original_response(embed=e, view=self)
                self.stop()
            else:
                e=discord.Embed(color=0x2B2D31, title="Blackjack")
                e.description = f"💎 Bet {fmt(bval)}\nYou {ph} = {score(ph)}\nDealer [{dh[0]}, ?]"
                e.set_thumbnail(url=inter.user.display_avatar.url)
                await i2.edit_original_response(embed=e, view=self)
        @discord.ui.button(label="STAND", style=discord.ButtonStyle.success, emoji="✋")
        async def stand(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id:
                return await i2.response.send_message("Not yours",ephemeral=True)
            await i2.response.defer()
            while score(dh)<17:
                dh.append(deck.pop())
            ps=score(ph)
            ds=score(dh)
            e=discord.Embed()
            e.set_thumbnail(url=inter.user.display_avatar.url)
            if ds>21 or ps>ds:
                win=bval*2
                dd=get_data(i2.user.id)
                dd["balance"]+=win
                dd["profit"]+=bval
                dd["wagered"]+=bval
                dd["withdrawn"]+=win
                await save_all()
                e.color=0x57F287
                e.title="Blackjack - WIN!"
                e.description = f"💎 Bet {fmt(bval)}\nYou {ph} = {ps}\nDealer {dh} = {ds}\n\nWon {fmt(win)}!"
            elif ps==ds:
                dd=get_data(i2.user.id)
                dd["balance"]+=bval
                await save_all()
                e.color=0xFEE75C
                e.title="Blackjack - PUSH"
                e.description = f"💎 Bet {fmt(bval)}\nYou {ps} vs {ds}\nRefund {fmt(bval)}"
            else:
                dd=get_data(i2.user.id)
                dd["wagered"]+=bval
                dd["profit"]-=bval
                await save_all()
                e.color=0xED4245
                e.title="Blackjack - LOSE"
                e.description = f"💎 Bet {fmt(bval)}\nYou {ph} = {ps}\nDealer {dh} = {ds}\nLost {fmt(bval)}"
            for c in self.children:
                c.disabled=True
            await i2.edit_original_response(embed=e, view=self)
            self.stop()
    em=discord.Embed(color=0x2B2D31, title="Blackjack")
    em.description = f"💎 Bet {fmt(bval)}\nYou {ph} = {score(ph)}\nDealer [{dh[0]}, ?]"
    em.set_thumbnail(url=inter.user.display_avatar.url)
    await inter.response.send_message(embed=em, view=BJView())

# ROCKET VISUAL NO INFINITE
def get_rocket_visual(mult):
    height = min(int(mult * 1.5), 10)
    lines = []
    for i in range(10, -1, -1):
        if i == height:
            lines.append("🚀")
        elif i == height - 1:
            lines.append("🔥")
        elif i == height - 2:
            lines.append("💨")
        elif i == 0:
            lines.append("🌎 Earth")
        elif i == 1:
            lines.append("☁️☁️☁️")
        else:
            if i % 3 == 0 and i < height:
                lines.append("✨ · ✨")
            else:
                lines.append("   ·   ")
    visual = "\n".join(lines)
    visual += f"\n{'─'*12}\nAltitude: {mult:.
