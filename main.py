import discord, os, json, random, time, asyncio
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
        with open(DATA_FILE, "r") as f: data = json.load(f)
    else: data = {}
async def save_all():
    with open(DATA_FILE, "w") as f: json.dump(data, f)
def get_data(uid):
    uid = str(uid)
    if uid not in data: data[uid] = {"balance": 10000, "wagered":0, "profit":0}
    return data[uid]
def parse_amount(s, bal=0):
    s=str(s).lower().replace(",","").strip()
    if s in ["all","max"]: return bal
    m=1
    if s.endswith("k"): m=1000; s=s[:-1]
    elif s.endswith("m"): m=1000000; s=s[:-1]
    elif s.endswith("b"): m=1000000000; s=s[:-1]
    return int(float(s)*m)
def fmt(n):
    if n>=1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n>=1_000_000: return f"{n/1_000_000:.2f}M"
    if n>=1_000: return f"{n/1_000:.1f}K"
    return str(int(n))

def no_money_embed(current, needed):
    embed = discord.Embed(color=0xED4245, title="❌ Not enough gems!")
    embed.description = f"💎 **Your balance** `{fmt(current)} ({int(current):,})`\n💸 **You need** `{fmt(needed)} ({int(needed):,})`\n\nYou don't have enough to play! Use `/daily` or ask owner."
    return embed

@bot.event
async def on_ready():
    load_data()
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

@bot.tree.command(name="balance", description="Check gems")
async def bal_cmd(inter: discord.Interaction, user: discord.Member=None):
    t=user or inter.user
    d=get_data(t.id)
    embed = discord.Embed(color=0x2B2D31, title=f"{t.display_name}'s balance")
    embed.description = f"💎 **Balance** `{fmt(d['balance'])} ({int(d['balance']):,})`\n💎 **Wagered** `{fmt(d['wagered'])}`\n💸 **Profit** `{fmt(d['profit'])}`"
    embed.set_thumbnail(url=t.display_avatar.url)
    await inter.response.send_message(embed=embed)

@bot.tree.command(name="addgems", description="Owner only")
async def add_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if inter.user.id!= OWNER_ID: return await inter.response.send_message("❌ Owner only", ephemeral=True)
    try: b=parse_amount(amount)
    except: return await inter.response.send_message("Bad amount", ephemeral=True)
    d=get_data(user.id); d["balance"]+=b; await save_all()
    await inter.response.send_message(f"✅ Added {fmt(b)} to {user.mention} | Now {fmt(d['balance'])}")

@bot.tree.command(name="removegems", description="Owner only")
async def rem_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if inter.user.id!= OWNER_ID: return await inter.response.send_message("❌ Owner only", ephemeral=True)
    try: b=parse_amount(amount)
    except: return await inter.response.send_message("Bad amount", ephemeral=True)
    d=get_data(user.id); d["balance"]=max(0,d["balance"]-b); await save_all()
    await inter.response.send_message(f"✅ Removed {fmt(b)} from {user.mention} | Now {fmt(d['balance'])}")

@bot.tree.command(name="tip", description="Tip anyone")
async def tip_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if user.id==inter.user.id: return await inter.response.send_message("Can't tip self", ephemeral=True)
    d=get_data(inter.user.id)
    try: b=parse_amount(amount, d["balance"])
    except: return await inter.response.send_message("Bad amount", ephemeral=True)
    if d["balance"]<b:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], b), ephemeral=True)
    d["balance"]-=b; get_data(user.id)["balance"]+=b; await save_all()
    await inter.response.send_message(f"💸 {inter.user.mention} tipped **{fmt(b)} gems** to {user.mention}")

# --- MINES FIXED ---
class MinesView(discord.ui.View):
    def __init__(self, uid, bet, mines=5):
        super().__init__(timeout=300); self.uid=uid; self.bet=bet; self.mines=mines
        self.mine_pos=set(random.sample(range(25), mines))
        self.revealed=set(); self.mult=1.0
        for i in range(25):
            btn = discord.ui.Button(label="?", style=discord.ButtonStyle.secondary, custom_id=str(i))
            btn.callback = self.make_cb(i)
            self.add_item(btn)
    def make_cb(self, idx):
        async def cb(inter: discord.Interaction):
            if inter.user.id!=self.uid: return await inter.response.send_message("Not yours", ephemeral=True)
            if idx in self.revealed: return await inter.response.defer()
            await inter.response.defer()
            if idx in self.mine_pos:
                for c in self.children:
                    if int(c.custom_id) in self.mine_pos: c.label="💣"; c.style=discord.ButtonStyle.danger
                    c.disabled=True
                embed=discord.Embed(color=0xED4245, title="💣 MINES - BOOM!")
                embed.description=f"Lost {fmt(self.bet)}\nBalance: {fmt(get_data(inter.user.id)['balance'])}"
                d=get_data(inter.user.id); d["profit"]-=self.bet; d["wagered"]+=self.bet; await save_all()
                await inter.edit_original_response(embed=embed, view=self); self.stop()
            else:
                self.revealed.add(idx)
                for c in self.children:
                    if int(c.custom_id)==idx: c.label="💎"; c.style=discord.ButtonStyle.success; c.disabled=True
                self.mult = round(1 + len(self.revealed)*0.25 + (len(self.revealed)**2)*0.05,2)
                embed=discord.Embed(color=0x2B2D31, title="💣 Mines")
                embed.description=f"Bet {fmt(self.bet)} | Gems: {len(self.revealed)}/{25-self.mines} | {self.mult}x = {fmt(int(self.bet*self.mult))}"
                view2 = self
                if len([c for c in view2.children if str(c.label).startswith("CASHOUT")])==0:
                    cash=discord.ui.Button(label=f"CASHOUT {self.mult}x", style=discord.ButtonStyle.success)
                    async def cash_cb(i2: discord.Interaction):
                        if i2.user.id!=self.uid: return await i2.response.send_message("Not yours",ephemeral=True)
                        await i2.response.defer()
                        win=int(self.bet*self.mult)
                        d=get_data(i2.user.id); d["balance"]+=win; d["wagered"]+=self.bet; d["profit"]+=win-self.bet; await save_all()
                        embed2=discord.Embed(color=0x57F287, title="💰 CASHOUT"); embed2.description=f"Won {fmt(win)} at {self.mult}x\nBalance: {fmt(d['balance'])}"
                        for c in view2.children: c.disabled=True
                        await i2.edit_original_response(embed=embed2, view=view2); view2.stop()
                    cash.callback=cash_cb
                    view2.add_item(cash)
                await inter.edit_original_response(embed=embed, view=view2)
        return cb

@bot.tree.command(name="mines", description="Play mines")
async def mines_cmd(inter: discord.Interaction, bet: str, bombs: int=3):
    try: bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except: return await inter.response.send_message("Bad amount", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval; await save_all()
    view=MinesView(inter.user.id, bval, bombs)
    embed=discord.Embed(color=0x2B2D31, title="💣 Mines")
    embed.description=f"Bet {fmt(bval)} | Bombs {bombs}"
    await inter.response.send_message(embed=embed, view=view)

# --- BLACKJACK ---
@bot.tree.command(name="blackjack", description="Play blackjack")
async def blackjack_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except: return await inter.response.send_message("Bad bet", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval; await save_all()
    deck=[2,3,4,5,6,7,8,9,10,10,10,10,11]*4; random.shuffle(deck)
    def score(h):
        s=sum(h); c=h.count(11)
        while s>21 and c: s-=10; c-=1
        return s
    ph=[deck.pop(), deck.pop()]; dh=[deck.pop(), deck.pop()]
    class BJView(discord.ui.View):
        def __init__(self): super().__init__(timeout=120)
        @discord.ui.button(label="HIT", style=discord.ButtonStyle.primary)
        async def hit(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id: return await i2.response.send_message("Not yours",ephemeral=True)
            await i2.response.defer()
            ph.append(deck.pop())
            if score(ph)>21:
                e=discord.Embed(color=0xED4245, title="💥 BUST"); e.description=f"You {score(ph)} | Lost {fmt(bval)}"
                dd=get_data(i2.user.id); dd["wagered"]+=bval; dd["profit"]-=bval; await save_all()
                for c in self.children: c.disabled=True
                await i2.edit_original_response(embed=e, view=self); self.stop()
            else:
                e=discord.Embed(color=0x2B2D31, title="🃏 Blackjack"); e.description=f"You {ph} = {score(ph)}\nDealer [{dh[0]}, ?]"
                await i2.edit_original_response(embed=e, view=self)
        @discord.ui.button(label="STAND", style=discord.ButtonStyle.success)
        async def stand(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id: return await i2.response.send_message("Not yours",ephemeral=True)
            await i2.response.defer()
            while score(dh)<17: dh.append(deck.pop())
            ps=score(ph); ds=score(dh); e=discord.Embed()
            if ds>21 or ps>ds:
                win=bval*2; dd=get_data(i2.user.id); dd["balance"]+=win; dd["profit"]+=bval; dd["wagered"]+=bval; await save_all()
                e.color=0x57F287; e.title="✅ WIN"; e.description=f"You {ps} vs {ds} | Won {fmt(win)}"
            elif ps==ds:
                dd=get_data(i2.user.id); dd["balance"]+=bval; await save_all()
                e.color=0xFEE75C; e.title="🤝 PUSH"; e.description=f"You {ps} vs {ds} | Refund"
            else:
                dd=get_data(i2.user.id); dd["wagered"]+=bval; dd["profit"]-=bval; await save_all()
                e.color=0xED4245; e.title="❌ LOSE"; e.description=f"You {ps} vs {ds} | Lost {fmt(bval)}"
            for c in self.children: c.disabled=True
            await i2.edit_original_response(embed=e, view=self); self.stop()
    em=discord.Embed(color=0x2B2D31, title="🃏 Blackjack"); em.description=f"Bet {fmt(bval)} | You {ph} = {score(ph)} | Dealer [{dh[0]}, ?]"
    await inter.response.send_message(embed=em, view=BJView())

# --- ROCKET NERFED INFINITE ---
@bot.tree.command(name="rocket", description="Rocket crash - nerfed infinite max")
async def rocket_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except: return await inter.response.send_message("Bad bet", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval; await save_all()
    r = random.random()
    if r < 0.50: crash = round(random.uniform(1.0, 1.8), 2)
    elif r < 0.75: crash = round(random.uniform(1.8, 2.5), 2)
    elif r < 0.90: crash = round(random.uniform(2.5, 3.5), 2)
    elif r < 0.97: crash = round(random.uniform(3.5, 6.0), 2)
    else: crash = round(random.uniform(6.0, 100.0), 2)
    
    class RocketView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=90); self.cur=1.0; self.crashed=False
        @discord.ui.button(label="CASHOUT 1.00x", style=discord.ButtonStyle.success, emoji="💸")
        async def cash(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id: return
            if self.crashed: return
            await i2.response.defer()
            win=int(bval*self.cur); d2=get_data(i2.user.id); d2["balance"]+=win; d2["profit"]+=win-bval; d2["wagered"]+=bval; await save_all()
            embed=discord.Embed(color=0x57F287, title="🚀 CASHOUT"); embed.description=f"Cashed at {self.cur}x = **{fmt(win)}**\nCrash was {crash}x"
            for c in self.children: c.disabled=True
            await i2.edit_original_response(embed=embed, view=self); self.stop()
    embed=discord.Embed(color=0x2B2D31, title="🚀 ROCKET [NERFED ♾️]"); embed.description=f"Bet `{fmt(bval)}` | Max ♾️\nCrash ???"
    view=RocketView()
    await inter.response.send_message(embed=embed, view=view)
    for i in range(1000):
        await asyncio.sleep(0.7)
        if view.is_finished(): return
        view.cur = round(1 + i*0.05 + (i**2)*0.001,2)
        if view.cur >= crash:
            view.crashed=True
            embed2=discord.Embed(color=0xED4245, title="💥 CRASHED!"); embed2.description=f"Crashed at **{crash}x** | Lost {fmt(bval)}"
            d2=get_data(inter.user.id); d2["profit"]-=bval; d2["wagered"]+=bval; await save_all()
            for c in view.children: c.disabled=True
            try: await inter.edit_original_response(embed=embed2, view=view)
            except: pass
            view.stop(); break
        else:
            embed.description=f"Bet {fmt(bval)} | Current **{view.cur}x** = {fmt(int(bval*view.cur))} | Max ♾️"
            for c in view.children: c.label=f"CASHOUT {view.cur}x"
            try: await inter.edit_original_response(embed=embed, view=view)
            except: pass

# --- COLOR DICE PS99 ---
COLORS = {
    "white": {"emoji": "⬜", "name": "White"},
    "purple": {"emoji": "🟪", "name": "Purple"},
    "green": {"emoji": "🟩", "name": "Green"},
    "red": {"emoji": "🟥", "name": "Red"},
    "blue": {"emoji": "🟦", "name": "Blue"},
    "orange": {"emoji": "🟧", "name": "Orange"},
}
PAYOUTS = {0:0.0, 1:2.0, 2:0.48, 3:3.0, 4:4.0, 5:4.0, 6:4.0}

class ColorDiceView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=60); self.uid=uid; self.bet=bet
        options=[]
        for k,v in COLORS.items():
            options.append(discord.SelectOption(label=v["name"], emoji=v["emoji"], value=k))
        sel=discord.ui.Select(placeholder="Choose your color...", options=options)
        sel.callback=self.cb
        self.add_item(sel)
    async def cb(self, inter: discord.Interaction):
        if inter.user.id!=self.uid: return await inter.response.send_message("Not yours", ephemeral=True)
        await inter.response.defer()
        pick=self.children[0].values[0]
        info=COLORS[pick]
        em=discord.Embed(color=0x2B2D31, title="🎲 Color Dice")
        em.description=f"Bet `{fmt(self.bet)}`\n\n{' '.join([v['emoji'] for v in COLORS.values()])}\n\n⏳ Rolling..."
        await inter.edit_original_response(embed=em, view=self)
        await asyncio.sleep(1.2)
        dice=random.choices(list(COLORS.keys()), k=6)
        emojis=[COLORS[c]["emoji"] for c in dice]
        matches=dice.count(pick)
        mult=PAYOUTS[matches]
        win=int(self.bet*mult)
        d=get_data(inter.user.id)
        if mult>0: d["balance"]+=win; d["profit"]+=win-self.bet; d["withdrawn"]+=win
        else: d["profit"]-=self.bet
        d["wagered"]+=self.bet; await save_all()
        if mult==0:
            fe=discord.Embed(color=0xED4245, title="🎲 Color Dice")
            fe.description=f"Bet `{fmt(self.bet)}` | {mult}x\n\nDice {' '.join(emojis)}\nPick {info['emoji']} {info['name']} | Matches {matches}"
        elif mult<1:
            fe=discord.Embed(color=0xF1C40F, title="🎲 Color Dice")
            fe.description=f"Bet `{fmt(self.bet)}` | {mult}x ({fmt(win)})\n\nDice {' '.join(emojis)}\nPick {info['emoji']} {info['name']} | Matches {matches}"
        else:
            fe=discord.Embed(color=0x57F287, title="🎲 Color Dice")
            fe.description=f"Bet `{fmt(self.bet)}` | {mult}x = {fmt(win)}\n\nDice {' '.join(emojis)}\nPick {info['emoji']} {info['name']} | Matches {matches} | Won!"
        await inter.edit_original_response(embed=fe, view=discord.ui.View())
        self.stop()

@bot.tree.command(name="colordice", description="Color dice PS99")
async def colordice_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except: return await inter.response.send_message("Bad bet", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval; await save_all()
    em=discord.Embed(color=0x2B2D31, title="🎲 Color Dice")
    em.description=f"Bet `{fmt(bval)}`\n\nPayout: 0=0x, 1=2x, 2=0.48x, 3=3x, 4+=4x"
    await inter.response.send_message(embed=em, view=ColorDiceView(inter.user.id, bval))

# --- CHICKEN CROSS - CROSSING ROADS, ONLY MULTIPLIER ---
class ChickenView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=300); self.uid=uid; self.bet=bet; self.pos=0; self.mult=1.0
    def get_mult(self, pos): 
        return round(1.15 * (1.15 ** (pos-1)) if pos>0 else 1.0, 2)
    def get_safe(self, pos): 
        return max(0.05, 0.58 - pos * 0.06)
    def get_road_visual(self):
        # Build road crossing visual - chicken crossing roads
        roads = []
        # Start
        roads.append("🟩🟩🟩 🏁 START 🏁 🟩🟩🟩")
        
        # Show next 6 roads
        for i in range(1, 8):
            mult = self.get_mult(i)
            if i < self.pos:
                # already crossed
                roads.append(f"✅ ROAD {i} | {mult}x | 🟩🟩🟩🟩🟩 crossed")
            elif i == self.pos:
                # current position with chicken
                # random cars
                if i % 2 == 0:
                    roads.append(f"🐔 ROAD {i} | {mult}x | ⬛🚗⬛🐔⬛🚗⬛")
                else:
                    roads.append(f"🐔 ROAD {i} | {mult}x | ⬛⬛🐔🚗⬛⬛🚗")
            elif i == self.pos + 1:
                # next road
                roads.append(f"➡️ ROAD {i} | {mult}x | ⬛🚗⬛⬛🚗⬛⬛")
            else:
                roads.append(f"🛣️ ROAD {i} | {mult}x | ⬛⬛🚗⬛⬛🚗⬛")
        
        roads.append("🏆🟩🟩🟩 FINISH ♾️ 🟩🟩🟩🏆")
        return "\n".join(roads)

@bot.tree.command(name="chickencross", description="Chicken cross - crossing roads infinite")
async def chicken_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet, get_data(inter.user.id)["balance"])
    except: return await inter.response.send_message("Bad bet", ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval:
        return await inter.response.send_message(embed=no_money_embed(d["balance"], bval), ephemeral=True)
    d["balance"]-=bval; await save_all()
    view=ChickenView(inter.user.id, bval)
    embed=discord.Embed(color=0x2B2D31, title="🐔 Chicken Cross - Crossing Roads ♾️")
    embed.description=f"💎 **Bet** `{fmt(bval)}`\n\n{view.get_road_visual()}\n\nLane `{view.pos}` | `{view.mult}x` = **{fmt(int(bval*view.mult))}** | Max ♾️\n\nCross the roads! Avoid cars 🚗"
    go_btn=discord.ui.Button(label=f"🐔 CROSS - Next {view.get_mult(1)}x", style=discord.ButtonStyle.primary, emoji="🐔")
    cash_btn=discord.ui.Button(label=f"💸 CASHOUT {view.mult}x", style=discord.ButtonStyle.success, disabled=True)
    view.add_item(go_btn); view.add_item(cash_btn)
    async def go_cb(i: discord.Interaction):
        if i.user.id!=view.uid: return await i.response.send_message("Not yours",ephemeral=True)
        await i.response.defer()
        safe=view.get_safe(view.pos)
        if random.random()>safe:
            embed2=discord.Embed(color=0xED4245, title="🚗💥 HIT BY CAR! 🍗")
            embed2.description=f"💎 **Bet** `{fmt(bval)}`\n\n{view.get_road_visual()}\n\n💥 Chicken got hit at ROAD {view.pos+1}!\
