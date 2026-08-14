import discord, json, os, random, asyncio
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

@bot.event
async def on_ready():
    load_data()
    await bot.tree.sync()
    print(f"ONLINE {bot.user}")

# --- BALANCE / ADMIN / TIP ---
@bot.tree.command(name="balance", description="Check gems")
async def bal_cmd(inter: discord.Interaction, user: discord.Member=None):
    t=user or inter.user
    d=get_data(t.id)
    await inter.response.send_message(f"💎 {t.mention} - **{fmt(d['balance'])} gems**")

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
    if d["balance"]<b: return await inter.response.send_message(f"You have {fmt(d['balance'])}", ephemeral=True)
    d["balance"]-=b; get_data(user.id)["balance"]+=b; await save_all()
    await inter.response.send_message(f"💸 {inter.user.mention} tipped **{fmt(b)} gems** to {user.mention}")

# --- 1. MINES ---
class MinesView(discord.ui.View):
    def __init__(self, uid, bet, mines=5):
        super().__init__(timeout=300); self.uid=uid; self.bet=bet; self.mines=mines
        self.mine_pos=set(random.sample(range(25), mines))
        self.revealed=set(); self.mult=1.0
        for i in range(25):
            btn = discord.ui.Button(label="❓", style=discord.ButtonStyle.gray, custom_id=str(i))
            btn.callback = self.make_cb(i)
            self.add_item(btn)
    def make_cb(self, idx):
        async def cb(inter: discord.Interaction):
            if inter.user.id!=self.uid: return await inter.response.send_message("Not yours", ephemeral=True)
            if idx in self.revealed: return
            if idx in self.mine_pos:
                for c in self.children:
                    if int(c.custom_id) in self.mine_pos: c.label="💣"; c.style=discord.ButtonStyle.red
                    c.disabled=True
                embed=discord.Embed(color=0xED4245, title="💣 MINES - BOOM!")
                embed.description=f"Lost {fmt(self.bet)}"
                d=get_data(inter.user.id); d["profit"]-=self.bet; d["wagered"]+=self.bet; await save_all()
                await inter.response.edit_message(embed=embed, view=self); self.stop()
            else:
                self.revealed.add(idx)
                for c in self.children:
                    if int(c.custom_id)==idx: c.label="💎"; c.style=discord.ButtonStyle.green; c.disabled=True
                # mult formula: (25 / (25 - mines - revealed)) cumulative
                self.mult = round(0.97 * (25 / (25 - len(self.revealed) - self.mines + 1)) if len(self.revealed)==1 else self.mult * (25 - len(self.revealed) - self.mines +1 +1)/(25 - len(self.revealed) - self.mines +1) ,2)
                # simple growing mult
                self.mult = round(1 + len(self.revealed)*0.25 + (len(self.revealed)**2)*0.05,2)
                embed=discord.Embed(color=0x2ECC71, title="💎 MINES")
                embed.description=f"Bet {fmt(self.bet)} | Gems: {len(self.revealed)}/ {25-self.mines} | {self.mult}x = {fmt(int(self.bet*self.mult))}\nClick to continue or cashout"
                view2 = self
                # add cashout button if not exists
                if len([c for c in view2.children if c.label.startswith("CASHOUT")])==0:
                    cash=discord.ui.Button(label=f"CASHOUT {self.mult}x", style=discord.ButtonStyle.success)
                    async def cash_cb(i2: discord.Interaction):
                        if i2.user.id!=self.uid: return await i2.response.send_message("Not yours",ephemeral=True)
                        win=int(self.bet*self.mult)
                        d=get_data(i2.user.id); d["balance"]+=win; d["wagered"]+=self.bet; d["profit"]+=win-self.bet; await save_all()
                        embed2=discord.Embed(color=0xFEE75C, title="💰 CASHOUT"); embed2.description=f"Won {fmt(win)} at {self.mult}x"
                        for c in view2.children: c.disabled=True
                        await i2.response.edit_message(embed=embed2, view=view2); view2.stop()
                    cash.callback=cash_cb
                    view2.add_item(cash)
                else:
                    for c in view2.children:
                        if c.label.startswith("CASHOUT"): c.label=f"CASHOUT {self.mult}x = {fmt(int(self.bet*self.mult))}"
                await inter.response.edit_message(embed=embed, view=view2)
        return cb

@bot.tree.command(name="mines", description="Mines game")
async def mines_cmd(inter: discord.Interaction, bet: str, mines: int=3):
    try: bval=parse_amount(bet)
    except: return await inter.response.send_message("Bad bet",ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval: return await inter.response.send_message("Broke",ephemeral=True)
    d["balance"]-=bval; await save_all()
    view=MinesView(inter.user.id, bval, max(1,min(20,mines)))
    embed=discord.Embed(color=0x2ECC71, title="💎 MINES"); embed.description=f"Bet {fmt(bval)} | {mines} mines | Find gems!"
    await inter.response.send_message(embed=embed, view=view)

# --- 2. BLACKJACK ---
@bot.tree.command(name="blackjack", description="Blackjack")
async def bj_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet)
    except: return await inter.response.send_message("Bad bet",ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval: return await inter.response.send_message("Broke",ephemeral=True)
    d["balance"]-=bval; await save_all()
    deck=[2,3,4,5,6,7,8,9,10,10,10,10,11]*4
    random.shuffle(deck)
    def score(h): 
        s=sum(h); ac=h.count(11)
        while s>21 and ac: s-=10; ac-=1
        return s
    ph=[deck.pop(), deck.pop()]; dh=[deck.pop(), deck.pop()]
    class BJView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
        @discord.ui.button(label="HIT", style=discord.ButtonStyle.primary)
        async def hit(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id: return
            ph.append(deck.pop())
            if score(ph)>21:
                embed=discord.Embed(color=0xED4245, title="BUST"); embed.description=f"You {score(ph)} vs Dealer {score(dh)} | Lost {fmt(bval)}"
                d2=get_data(i2.user.id); d2["profit"]-=bval; d2["wagered"]+=bval; await save_all()
                for c in self.children: c.disabled=True
                await i2.response.edit_message(embed=embed, view=self); self.stop()
            else:
                embed=discord.Embed(color=0x2ECC71, title="Blackjack"); embed.description=f"You: {ph} = {score(ph)}\nDealer: [{dh[0]}, ?]\nHit or Stand?"
                await i2.response.edit_message(embed=embed, view=self)
        @discord.ui.button(label="STAND", style=discord.ButtonStyle.success)
        async def stand(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id: return
            while score(dh)<17: dh.append(deck.pop())
            ps=score(ph); ds=score(dh)
            embed=discord.Embed(color=0x2ECC71)
            if ds>21 or ps>ds:
                win=int(bval*2); d2=get_data(i2.user.id); d2["balance"]+=win; d2["profit"]+=bval; d2["wagered"]+=bval; await save_all()
                embed.title="WIN"; embed.description=f"You {ps} vs Dealer {ds} | Won {fmt(win)}"
            elif ps==ds:
                d2=get_data(i2.user.id); d2["balance"]+=bval; await save_all()
                embed.title="PUSH"; embed.description=f"You {ps} vs Dealer {ds} | Refund"
            else:
                embed.title="LOSE"; embed.description=f"You {ps} vs Dealer {ds} | Lost {fmt(bval)}"
                d2=get_data(i2.user.id); d2["profit"]-=bval; d2["wagered"]+=bval; await save_all()
            for c in self.children: c.disabled=True
            await i2.response.edit_message(embed=embed, view=self); self.stop()
    embed=discord.Embed(color=0x2ECC71, title="Blackjack"); embed.description=f"You: {ph} = {score(ph)}\nDealer: [{dh[0]}, ?]"
    await inter.response.send_message(embed=embed, view=BJView())

# --- 3. ROCKET / CRASH ---
@bot.tree.command(name="rocket", description="Rocket crash")
async def rocket_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet)
    except: return await inter.response.send_message("Bad bet",ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval: return await inter.response.send_message("Broke",ephemeral=True)
    d["balance"]-=bval; await save_all()
    crash = round(random.uniform(1.05, 15.0) if random.random()>0.1 else random.uniform(1.0,1.1),2)
    class RocketView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60); self.cur=1.0; self.crashed=False
        @discord.ui.button(label="CASHOUT 1.00x", style=discord.ButtonStyle.success)
        async def cash(self, i2: discord.Interaction, btn):
            if i2.user.id!=inter.user.id: return
            if self.crashed: return
            win=int(bval*self.cur); d2=get_data(i2.user.id); d2["balance"]+=win; d2["profit"]+=win-bval; d2["wagered"]+=bval; await save_all()
            embed=discord.Embed(color=0xFEE75C, title="🚀 CASHOUT"); embed.description=f"Cashed at {self.cur}x = {fmt(win)}\nCrash was {crash}x"
            for c in self.children: c.disabled=True
            await i2.response.edit_message(embed=embed, view=self); self.stop()
    embed=discord.Embed(color=0x3498DB, title="🚀 ROCKET"); embed.description=f"Bet {fmt(bval)} | Crash at ???\nRocket flying..."
    view=RocketView()
    await inter.response.send_message(embed=embed, view=view)
    for i in range(100):
        await asyncio.sleep(0.6)
        if view.is_finished(): return
        view.cur = round(1 + i*0.12 + (i**2)*0.005,2)
        if view.cur >= crash:
            view.crashed=True
            embed2=discord.Embed(color=0xED4245, title="💥 CRASHED!"); embed2.description=f"Crashed at {crash}x\nLost {fmt(bval)}"
            d2=get_data(inter.user.id); d2["profit"]-=bval; d2["wagered"]+=bval; await save_all()
            for c in view.children: c.disabled=True
            try: await inter.edit_original_response(embed=embed2, view=view)
            except: pass
            view.stop(); break
        else:
            embed.description=f"Bet {fmt(bval)} | Current **{view.cur}x** = {fmt(int(bval*view.cur))}\nCrash at ???"
            for c in view.children: c.label=f"CASHOUT {view.cur}x = {fmt(int(bval*view.cur))}"
            try: await inter.edit_original_response(embed=embed, view=view)
            except: pass

# --- 4. COLOR DICE ---
@bot.tree.command(name="colordice", description="Color dice - bet on color")
async def colordice_cmd(inter: discord.Interaction, bet: str, color: str):
    try: bval=parse_amount(bet)
    except: return await inter.response.send_message("Bad bet",ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval: return await inter.response.send_message("Broke",ephemeral=True)
    colors=["red","blue","green","yellow","purple","gold"]
    if color.lower() not in colors: return await inter.response.send_message(f"Pick {', '.join(colors)}", ephemeral=True)
    d["balance"]-=bval; await save_all()
    roll = random.choice(colors)
    # gold 6x, others 4.5x
    mult = 6.0 if color.lower()=="gold" else 4.5
    if roll==color.lower():
        win=int(bval*mult); d["balance"]+=win; d["profit"]+=win-bval; d["wagered"]+=bval; await save_all()
        await inter.response.send_message(f"🎲 Rolled **{roll}** | ✅ WIN {fmt(win)} ({mult}x)")
    else:
        d["profit"]-=bval; d["wagered"]+=bval; await save_all()
        await inter.response.send_message(f"🎲 Rolled **{roll}** vs your **{color}** | ❌ Lost {fmt(bval)}")

# --- 5. CHICKEN CROSS INFINITE - YOUR SPECS 58% LANE1, 1.15x growing ---
class ChickenView(discord.ui.View):
    def __init__(self, uid, bet):
        super().__init__(timeout=300); self.uid=uid; self.bet=bet; self.pos=0; self.mult=1.0
    def get_mult(self, pos): 
        return round(1.15 * (1.15 ** (pos-1)) if pos>0 else 1.0, 2)
    def get_safe(self, pos): 
        return max(0.05, 0.58 - pos * 0.06) # 58% lane1
    def get_board(self):
        board=""
        for i in range(max(0, self.pos-2), self.pos+3):
            if i < self.pos: board+="✅ "
            elif i==self.pos: board+="🐔 "
            else: board+="🟩 "
        return board

@bot.tree.command(name="chickencross", description="Chicken cross infinite")
async def chicken_cmd(inter: discord.Interaction, bet: str):
    try: bval=parse_amount(bet)
    except: return await inter.response.send_message("Bad bet",ephemeral=True)
    d=get_data(inter.user.id)
    if d["balance"]<bval: return await inter.response.send_message(f"Need {fmt(bval)}",ephemeral=True)
    d["balance"]-=bval; await save_all()
    view=ChickenView(inter.user.id, bval)
    embed=discord.Embed(color=0xF1C40F, title="🐔 Chicken Cross - INFINITE")
    embed.description=f"💎 Bet `{fmt(bval)}`\n\n{view.get_board()}\n\nLane `0` | Next `1.15x` (58% safe)"
    go_btn=discord.ui.Button(label="🐔 GO to 1.15x (58% safe)", style=discord.ButtonStyle.primary)
    cash_btn=discord.ui.Button(label="💸 CASHOUT", style=discord.ButtonStyle.success, disabled=True)
    view.add_item(go_btn); view.add_item(cash_btn)
    async def go_cb(i: discord.Interaction):
        if i.user.id!=view.uid: return await i.response.send_message("Not yours",ephemeral=True)
        safe=view.get_safe(view.pos)
        if random.random()>safe:
            embed2=discord.Embed(color=0xED4245, title="🍗 FRIED!")
            embed2.description=f"💎 Bet `{fmt(bval)}`\n\n{view.get_board().replace('🐔','🔥')}\n\n💥 Fried at lane {view.pos+1} | {int(safe*100)}% was safe"
            d2=get_data(i.user.id); d2["wagered"]+=bval; d2["profit"]-=bval; await save_all()
            for c in view.children: c.disabled=True
            await i.response.edit_message(embed=embed2, view=view); view.stop()
        else:
            view.pos+=1; view.mult=view.get_mult(view.pos)
            next_mult=view.get_mult(view.pos+1); next_safe=int(view.get_safe(view.pos)*100)
            cash_btn.disabled=False; cash_btn.label=f"💸 CASHOUT {view.mult}x = {fmt(int(bval*view.mult))}"
            go_btn.label=f"🐔 GO to {next_mult}x ({next_safe}% safe)"
            embed2=discord.Embed(color=0xF1C40F, title="🐔 Chicken Cross - INFINITE")
            embed2.description=f"💎 Bet `{fmt(bval)}`\n\n{view.get_board()}\n\nLane `{view.pos}` | Current `{view.mult}x` = {fmt(int(bval*view.mult))}\nNext `{next_mult}x` - {next_safe}% safe"
            await i.response.edit_message(embed=embed2, view=view)
    async def cash_cb(i: discord.Interaction):
        if i.user.id!=view.uid: return await i.response.send_message("Not yours",ephemeral=True)
        win=int(bval*view.mult); d2=get_data(i.user.id); d2["balance"]+=win; d2["wagered"]+=bval; d2["profit"]+=win-bval; await save_all()
        embed2=discord.Embed(color=0xFEE75C, title="💰 CASHOUT"); embed2.description=f"Lane {view.pos} | {view.mult}x = {fmt(win)}"
        for c in view.children: c.disabled=True
        await i.response.edit_message(embed=embed2, view=view); view.stop()
    go_btn.callback=go_cb; cash_btn.callback=cash_cb
    await inter.response.send_message(embed=embed, view=view)

if not TOKEN:
    print("ERROR: No TOKEN env var! Set TOKEN in Railway Variables")
    print("Railway -> Your Project -> Variables -> Add TOKEN")
else:
    bot.run(TOKEN)
