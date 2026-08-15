import discord, os, json, random, asyncio
from discord.ext import commands

# RAILWAY DOES TOKEN - NO TOKEN IN CODE - SET IN RAILWAY VARIABLES
TOKEN = os.getenv("TOKEN")
print(f"Checking Railway TOKEN... Found: {'YES' if TOKEN else 'NO - SET IN VARIABLES!'}")

DATA_FILE = "data.json"
OWNER_ID = 1536946071769718784

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
data = {}

def load_data():
    global data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
        except:
            data = {}
    else:
        data = {}

async def save_all():
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f)
    except:
        pass

def get_data(uid):
    uid = str(uid)
    if uid not in data:
        data[uid] = {
            "balance": 10000,
            "deposited":0,
            "withdrawn":0,
            "wagered":0,
            "profit":0,
            "affiliate_code": uid,
            "referred_by": None,
            "referrals": [],
            "affiliate_earnings": 0,
            "affiliate_wagered": 0
        }
    d = data[uid]
    for k in ["deposited","withdrawn","wagered","profit","balance","affiliate_earnings","affiliate_wagered"]:
        if k not in d:
            d[k]=0
    if "affiliate_code" not in d:
        d["affiliate_code"]=uid
    if "referred_by" not in d:
        d["referred_by"]=None
    if "referrals" not in d:
        d["referrals"]=[]
    return d

def add_affiliate_reward(wager_uid, wager_amount):
    """5% added to wagered, NOT money"""
    try:
        d = get_data(wager_uid)
        ref_id = d.get("referred_by")
        if not ref_id:
            return
        if str(ref_id) == str(wager_uid):
            return
        ref_data = get_data(ref_id)
        bonus = int(wager_amount * 0.05)
        if bonus <=0:
            return
        ref_data["wagered"] += bonus
        ref_data["affiliate_wagered"] += bonus
        ref_data["affiliate_earnings"] += bonus
    except Exception as e:
        print(f"aff error {e}")

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
    try:
        n=float(n)
    except:
        return "0"
    if n>=1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if n>=1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n>=1_000:
        return f"{n/1_000:.1f}K"
    return str(int(n))

def fmt_full(n):
    try:
        return f"{int(n):,}"
    except:
        return "0"

def no_money_embed(current, needed):
    embed = discord.Embed(color=0xED4245, title="Not enough gems!")
    embed.description = f"Your balance {fmt(current)} ({fmt_full(current)})\nYou need {fmt(needed)} ({fmt_full(needed)})"
    return embed

@bot.event
async def on_ready():
    load_data()
    try:
        await bot.tree.sync()
        print(f"ONLINE {bot.user}")
    except Exception as e:
        print(f"sync error {e}")

class BalanceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label="Advanced Stats", style=discord.ButtonStyle.secondary, disabled=True))

@bot.tree.command(name="balance", description="Check balance")
async def bal_cmd(inter: discord.Interaction, user: discord.Member=None):
    try:
        await inter.response.defer()
        t=user or inter.user
        d=get_data(t.id)
        embed = discord.Embed(color=0x2B2D31, title=f"{t.display_name}'s balance")
        embed.description = f"💎 Balance {fmt(d['balance'])} ({fmt_full(d['balance'])})\n📥 Deposited {fmt(d['deposited'])}\n📤 Withdrawn {fmt(d['withdrawn'])}\n💎 Wagered {fmt(d['wagered'])}\n💸 Profit {fmt(d['profit'])}"
        embed.set_thumbnail(url=t.display_avatar.url)
        await inter.followup.send(embed=embed, view=BalanceView())
    except Exception as e:
        print(f"bal error {e}")

@bot.tree.command(name="addgems", description="Owner only")
async def add_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if inter.user.id!= OWNER_ID:
        return await inter.response.send_message("Owner only", ephemeral=True)
    await inter.response.defer()
    try:
        b=parse_amount(amount)
        d=get_data(user.id)
        d["balance"]+=b
        d["deposited"]+=b
        await save_all()
        await inter.followup.send(f"Added {fmt(b)} to {user.mention} | Now {fmt(d['balance'])}")
    except Exception as e:
        await inter.followup.send(f"Error {e}", ephemeral=True)

@bot.tree.command(name="removegems", description="Owner only")
async def rem_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    if inter.user.id!= OWNER_ID:
        return await inter.response.send_message("Owner only", ephemeral=True)
    await inter.response.defer()
    try:
        b=parse_amount(amount)
        d=get_data(user.id)
        d["balance"]=max(0,d["balance"]-b)
        await save_all()
        await inter.followup.send(f"Removed {fmt(b)} from {user.mention} | Now {fmt(d['balance'])}")
    except Exception as e:
        await inter.followup.send(f"Error {e}", ephemeral=True)

@bot.tree.command(name="tip", description="Tip anyone")
async def tip_cmd(inter: discord.Interaction, user: discord.Member, amount: str):
    await inter.response.defer()
    try:
        if user.id==inter.user.id:
            return await inter.followup.send("Cant tip self", ephemeral=True)
        d=get_data(inter.user.id)
        b=parse_amount(amount, d["balance"])
        if d["balance"]<b:
            return await inter.followup.send(embed=no_money_embed(d["balance"], b), ephemeral=True)
        d["balance"]-=b
        get_data(user.id)["balance"]+=b
        await save_all()
        await inter.followup.send(f"{inter.user.mention} tipped {fmt(b)} gems to {user.mention}")
    except Exception as e:
        await inter.followup.send(f"Error {e}", ephemeral=True)

@bot.tree.command(name="affiliate", description="Show your affiliate code and stats")
async def affiliate_cmd(inter: discord.Interaction):
    try:
        await inter.response.defer()
        d = get_data(inter.user.id)
        code = d["affiliate_code"]
        referrals = d.get("referrals", [])
        earnings = d.get("affiliate_wagered", 0)
        count = len(referrals)
        embed = discord.Embed(color=0x2B2D31, title="💸 Affiliate - 5% to Wagered")
        embed.description = (
            f"**Your Code:** `{code}`\n"
            f"Share: `/affiliate_claim code:{code}`\n\n"
            f"💎 **Stats**\n"
            f"👥 Referrals: {count}\n"
            f"📈 Wagered from referrals: {fmt(earnings)} ({fmt_full(earnings)})\n"
            f"⚡ Rate: 5% of their bet ADDED to YOUR wagered (not money)\n\n"
            f"Check `/affiliate_list` to see referrals"
        )
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.followup.send(embed=embed)
    except Exception as e:
        print(f"aff error {e}")

@bot.tree.command(name="affiliate_claim", description="Claim an affiliate code")
async def affiliate_claim_cmd(inter: discord.Interaction, code: str):
    try:
        await inter.response.defer()
        d = get_data(inter.user.id)
        code = code.strip()
        if d.get("referred_by"):
            return await inter.followup.send(f"You already used code: `{d['referred_by']}`", ephemeral=True)
        if code == str(inter.user.id):
            return await inter.followup.send("You can't refer yourself!", ephemeral=True)
        if code not in data:
            if not code.isdigit():
                return await inter.followup.send("Invalid code!", ephemeral=True)
            get_data(code)
        ref_data = get_data(code)
        d["referred_by"] = code
        if str(inter.user.id) not in ref_data["referrals"]:
            ref_data["referrals"].append(str(inter.user.id))
        await save_all()
        embed = discord.Embed(color=0x57F287, title="✅ Claimed!")
        embed.description = f"You claimed `{code}` from <@{code}>!\nThey get 5% of your bets added to THEIR wagered."
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.followup.send(embed=embed)
    except Exception as e:
        print(f"claim error {e}")

@bot.tree.command(name="affiliate_list", description="See your referrals list")
async def affiliate_list_cmd(inter: discord.Interaction):
    try:
        await inter.response.defer()
        d = get_data(inter.user.id)
        referrals = d.get("referrals", [])
        earnings = d.get("affiliate_wagered", 0)
        embed = discord.Embed(color=0x2B2D31, title=f"👥 Referrals - {len(referrals)} - 5% to Wagered")
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        if not referrals:
            embed.description = f"No referrals yet!\nCode: `{d['affiliate_code']}`\nShare: `/affiliate_claim code:{d['affiliate_code']}`\nWagered from refs: {fmt(earnings)}"
        else:
            desc = f"💰 Wagered from refs: {fmt(earnings)} ({fmt_full(earnings)})\nCode: `{d['affiliate_code']}`\n\n**Referrals:**\n"
            for i, rid in enumerate(referrals[:20], 1):
                try:
                    rdata = get_data(rid)
                    wagered = rdata.get("wagered", 0)
                    user_obj = inter.guild.get_member(int(rid)) if inter.guild else None
                    name = user_obj.display_name if user_obj else f"User {rid[:6]}..."
                    bonus = int(wagered*0.05)
                    desc += f"{i}. {name} (<@{rid}>) - Wagered {fmt(wagered)} => +{fmt(bonus)} to you\n"
                except:
                    desc += f"{i}. <@{rid}>\n"
            if len(referrals) > 20:
                desc += f"\n...and {len(referrals)-20} more"
            embed.description = desc
        await inter.followup.send(embed=embed)
    except Exception as e:
        print(f"aff list error {e}")

@bot.tree.command(name="affiliates", description="See your referrals (alias)")
async def affiliates_cmd(inter: discord.Interaction):
    try:
        await inter.response.defer()
        d = get_data(inter.user.id)
        referrals = d.get("referrals", [])
        earnings = d.get("affiliate_wagered", 0)
        embed = discord.Embed(color=0x2B2D31, title=f"👥 Referrals - {len(referrals)}")
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        if not referrals:
            embed.description = f"No referrals! Code: `{d['affiliate_code']}` - 5% to wagered"
        else:
            desc = f"Wagered from refs: {fmt(earnings)}\n\n"
            for i, rid in enumerate(referrals[:20], 1):
                rdata = get_data(rid)
                desc += f"{i}. <@{rid}> - Wagered {fmt(rdata.get('wagered',0))}\n"
            embed.description = desc
        await inter.followup.send(embed=embed)
    except Exception as e:
        print(f"alias error {e}")

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
            try:
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
                    embed.description = f"💎 Bet {fmt(self.bet)}\n✨ Reached {self.mult:.1f}x\n💎 Gems found {gems_found}/{total_gems}\n💣 Bombs {self.bombs}\n\nYou struck a bomb and lost."
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
                    add_affiliate_reward(inter.user.id, self.bet)
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
                    try:
                        if c_inter.user.id != new_view.uid:
                            return await c_inter.response.send_message("Not yours", ephemeral=True)
                        await c_inter.response.defer()
                        win = int(new_view.bet * new_view.mult)
                        d = get_data(c_inter.user.id)
                        d["balance"] += win
                        d["wagered"] += new_view.bet
                        d["profit"] += win - new_view.bet
                        d["withdrawn"] += win
                        add_affiliate_reward(c_inter.user.id, new_view.bet)
                        await save_all()
                        e = discord.Embed(color=0x57F287, title="Mines - CASHOUT")
                        e.description = f"💎 Bet {fmt(new_view.bet)}\n✨ Reached {new_view.mult}x\n\nWon {fmt(win)}!"
                        e.set_thumbnail(url=c_inter.user.display_avatar.url)
                        await c_inter.edit_original_response(embed=e, view=discord.ui.View())
                        new_view.stop()
                    except Exception as e:
                        print(f"cash error {e}")
                cash_btn.callback = cash_callback
                new_view.add_item(cash_btn)
                await inter.edit_original_response(embed=embed, view=new_view)
                self.stop()
            except Exception as e:
                print(f"mines cb error {e}")
        return callback

@bot.tree.command(name="mines", description="Play mines PS99")
async def mines_cmd(inter: discord.Interaction, bet: str, bombs: int=23):
    try:
        await inter.response.defer()
        bval=parse_amount(bet, get_data(inter.user.id)["balance"])
        d=get_data(inter.user.id)
        if d["balance"]<bval:
            return await inter.followup.send(embed=no_money_embed(d["balance"], bval), ephemeral=True)
        d["balance"]-=bval
        await save_all()
        if bombs < 1 or bombs > 24:
            bombs = 23
        view=MinesView(inter.user.id, bval, bombs)
        embed = discord.Embed(color=0x2B2D31, title="Mines")
        total_gems = 25 - bombs
        embed.description = f"💎 Bet {fmt(bval)}\n✨ Reached 1.0x\n💎 Gems found 0/{total_gems}\n💣 Bombs {bombs}"
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.followup.send(embed=embed, view=view)
    except Exception as e:
        print(f"mines error {e}")

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
        try:
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
            add_affiliate_reward(inter.user.id, self.bet)
            await save_all()
            if matches == 0:
                final = discord.Embed(color=0xED4245, title="Color Dice")
                final.description = f"?
