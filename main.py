import discord, os, json, random, asyncio
from discord.ext import commands

# RAILWAY - NO TOKEN IN CODE
TOKEN = os.getenv("TOKEN")
print(f"TOKEN check: {'FOUND' if TOKEN else 'MISSING - SET IN RAILWAY VARIABLES'}")

DATA_FILE = "data.json"
OWNER_ID = 1536946071769718784

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
data = {}

def load_data():
    global data
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE,"r") as f: data=json.load(f)
        except: data={}
    else: data={}

async def save_all():
    try:
        with open(DATA_FILE,"w") as f: json.dump(data,f)
    except: pass

def get_data(uid):
    uid=str(uid)
    if uid not in data:
        data[uid]={"balance":10000,"deposited":0,"withdrawn":0,"wagered":0,"profit":0,"affiliate_code":uid,"referred_by":None,"referrals":[],"affiliate_earnings":0,"affiliate_wagered":0}
    d=data[uid]
    for k in ["deposited","withdrawn","wagered","profit","balance","affiliate_earnings","affiliate_wagered"]:
        if k not in d: d[k]=0
    if "affiliate_code" not in d: d["affiliate_code"]=uid
    if "referred_by" not in d: d["referred_by"]=None
    if "referrals" not in d: d["referrals"]=[]
    return d

def add_affiliate_reward(wager_uid,wager_amount):
    try:
        d=get_data(wager_uid)
        ref_id=d.get("referred_by")
        if not ref_id or str(ref_id)==str(wager_uid): return
        ref_data=get_data(ref_id)
        bonus=int(wager_amount*0.05)
        if bonus<=0: return
        ref_data["wagered"]+=bonus
        ref_data["affiliate_wagered"]+=bonus
        ref_data["affiliate_earnings"]+=bonus
    except Exception as e: print(f"aff err {e}")

def parse_amount(s,bal=0):
    s=str(s).lower().replace(",","").strip()
    if s in ["all","max"]: return bal
    m=1
    if s.endswith("k"): m=1000; s=s[:-1]
    elif s.endswith("m"): m=1000000; s=s[:-1]
    elif s.endswith("b"): m=1000000000; s=s[:-1]
    return int(float(s)*m)

def fmt(n):
    try: n=float(n)
    except: return "0"
    if n>=1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n>=1_000_000: return f"{n/1_000_000:.2f}M"
    if n>=1_000: return f"{n/1_000:.1f}K"
    return str(int(n))

def fmt_full(n):
    try: return f"{int(n):,}"
    except: return "0"

def no_money_embed(current,needed):
    embed=discord.Embed(color=0xED4245,title="Not enough gems!")
    embed.description=f"Your balance {fmt(current)} ({fmt_full(current)})\nYou need {fmt(needed)} ({fmt_full(needed)})"
    return embed

@bot.event
async def on_ready():
    load_data()
    try:
        await bot.tree.sync()
        print(f"ONLINE {bot.user}")
    except Exception as e: print(f"sync err {e}")

# YOUR REQUESTED BALANCE DESIGN
class BalanceView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Button(label="Advanced Stats",style=discord.ButtonStyle.secondary,disabled=True))

@bot.tree.command(name="balance",description="Check gems")
async def bal_cmd(inter:discord.Interaction,user:discord.Member=None):
    try:
        await inter.response.defer()
        t=user or inter.user
        d=get_data(t.id)
        # YOUR REQUESTED FORMAT WITH EMOJIS AND AVATAR
        embed=discord.Embed(color=0x2B2D31,title=f"{t.display_name}'s balance")
        bal_str = fmt(d['balance'])
        bal_full = fmt_full(d['balance'])
        dep_str = fmt(d['deposited'])
        wit_str = fmt(d['withdrawn'])
        wag_str = fmt(d['wagered'])
        pro_str = fmt(d['profit'])
        description_text = f"💎 Balance {bal_str} ({bal_full})\n📥 Deposited {dep_str}\n📤 Withdrawn {wit_str}\n💎 Wagered {wag_str}\n💸 Profit {pro_str}"
        embed.description=description_text
        embed.set_thumbnail(url=t.display_avatar.url)
        await inter.followup.send(embed=embed,view=BalanceView())
    except Exception as e: print(f"bal err {e}")

@bot.tree.command(name="addgems",description="Owner only")
async def add_cmd(inter:discord.Interaction,user:discord.Member,amount:str):
    if inter.user.id!=OWNER_ID: return await inter.response.send_message("Owner only",ephemeral=True)
    await inter.response.defer()
    try:
        b=parse_amount(amount)
        d=get_data(user.id); d["balance"]+=b; d["deposited"]+=b
        await save_all()
        await inter.followup.send(f"Added {fmt(b)} to {user.mention} | Now {fmt(d['balance'])}")
    except Exception as e: await inter.followup.send(f"Error {e}",ephemeral=True)

@bot.tree.command(name="removegems",description="Owner only")
async def rem_cmd(inter:discord.Interaction,user:discord.Member,amount:str):
    if inter.user.id!=OWNER_ID: return await inter.response.send_message("Owner only",ephemeral=True)
    await inter.response.defer()
    try:
        b=parse_amount(amount)
        d=get_data(user.id); d["balance"]=max(0,d["balance"]-b)
        await save_all()
        await inter.followup.send(f"Removed {fmt(b)} from {user.mention} | Now {fmt(d['balance'])}")
    except Exception as e: await inter.followup.send(f"Error {e}",ephemeral=True)

@bot.tree.command(name="tip",description="Tip anyone")
async def tip_cmd(inter:discord.Interaction,user:discord.Member,amount:str):
    await inter.response.defer()
    try:
        if user.id==inter.user.id: return await inter.followup.send("Cant tip self",ephemeral=True)
        d=get_data(inter.user.id)
        b=parse_amount(amount,d["balance"])
        if d["balance"]<b: return await inter.followup.send(embed=no_money_embed(d["balance"],b),ephemeral=True)
        d["balance"]-=b; get_data(user.id)["balance"]+=b
        await save_all()
        await inter.followup.send(f"{inter.user.mention} tipped {fmt(b)} gems to {user.mention}")
    except Exception as e: await inter.followup.send(f"Error {e}",ephemeral=True)

@bot.tree.command(name="affiliate",description="Show your affiliate code and stats")
async def affiliate_cmd(inter:discord.Interaction):
    try:
        await inter.response.defer()
        d=get_data(inter.user.id)
        code=d["affiliate_code"]
        referrals=d.get("referrals",[])
        earnings=d.get("affiliate_wagered",0)
        count=len(referrals)
        desc = "**Your Code:** `" + code + "`\nShare: `/affiliate_claim code:" + code + "`\n\nReferrals: " + str(count) + "\nWagered from referrals: " + fmt(earnings) + " (" + fmt_full(earnings) + ")\nRate: 5% of their bet ADDED to YOUR wagered"
        embed=discord.Embed(color=0x2B2D31,title="Affiliate - 5% to Wagered")
        embed.description=desc
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.followup.send(embed=embed)
    except Exception as e: print(f"aff err {e}")

@bot.tree.command(name="affiliate_claim",description="Claim an affiliate code")
async def affiliate_claim_cmd(inter:discord.Interaction,code:str):
    try:
        await inter.response.defer()
        d=get_data(inter.user.id)
        code=code.strip()
        if d.get("referred_by"): return await inter.followup.send(f"You already used code: `{d['referred_by']}`",ephemeral=True)
        if code==str(inter.user.id): return await inter.followup.send("You can't refer yourself!",ephemeral=True)
        if code not in data:
            if not code.isdigit(): return await inter.followup.send("Invalid code!",ephemeral=True)
            get_data(code)
        ref_data=get_data(code)
        d["referred_by"]=code
        if str(inter.user.id) not in ref_data["referrals"]: ref_data["referrals"].append(str(inter.user.id))
        await save_all()
        embed=discord.Embed(color=0x57F287,title="Claimed!")
        embed.description=f"You claimed `{code}` from <@{code}>! They get 5% of your bets added to THEIR wagered."
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.followup.send(embed=embed)
    except Exception as e: print(f"claim err {e}")

@bot.tree.command(name="affiliate_list",description="See your referrals list")
async def affiliate_list_cmd(inter:discord.Interaction):
    try:
        await inter.response.defer()
        d=get_data(inter.user.id)
        referrals=d.get("referrals",[])
        earnings=d.get("affiliate_wagered",0)
        embed=discord.Embed(color=0x2B2D31,title=f"Referrals - {len(referrals)} - 5% to Wagered")
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        if not referrals:
            embed.description=f"No referrals yet! Code: `{d['affiliate_code']}` Share: `/affiliate_claim code:{d['affiliate_code']}` Wagered from refs: {fmt(earnings)}"
        else:
            desc=f"Wagered from refs: {fmt(earnings)} ({fmt_full(earnings)}) Code: {d['affiliate_code']}\n\nReferrals:\n"
            for i,rid in enumerate(referrals[:20],1):
                try:
                    rdata=get_data(rid)
                    wagered=rdata.get("wagered",0)
                    bonus=int(wagered*0.05)
                    desc+=f"{i}. <@{rid}> - Wagered {fmt(wagered)} => +{fmt(bonus)} to you\n"
                except: desc+=f"{i}. <@{rid}>\n"
            if len(referrals)>20: desc+=f"\n...and {len(referrals)-20} more"
            embed.description=desc
        await inter.followup.send(embed=embed)
    except Exception as e: print(f"aff list err {e}")

@bot.tree.command(name="affiliates",description="See your referrals (alias)")
async def affiliates_cmd(inter:discord.Interaction):
    try:
        await inter.response.defer()
        d=get_data(inter.user.id)
        referrals=d.get("referrals",[])
        earnings=d.get("affiliate_wagered",0)
        embed=discord.Embed(color=0x2B2D31,title=f"Referrals - {len(referrals)}")
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        if not referrals:
            embed.description=f"No referrals! Code: `{d['affiliate_code']}` - 5% to wagered"
        else:
            desc=f"Wagered from refs: {fmt(earnings)}\n\n"
            for i,rid in enumerate(referrals[:20],1):
                rdata=get_data(rid)
                desc+=f"{i}. <@{rid}> - Wagered {fmt(rdata.get('wagered',0))}\n"
            embed.description=desc
        await inter.followup.send(embed=embed)
    except Exception as e: print(f"alias err {e}")

class MinesView(discord.ui.View):
    def __init__(self,uid,bet,bombs=23):
        super().__init__(timeout=300)
        self.uid=uid; self.bet=bet; self.bombs=bombs
        self.mine_pos=set(random.sample(range(25),bombs))
        self.revealed=set(); self.mult=1.0
        for i in range(25):
            btn=discord.ui.Button(label="?",style=discord.ButtonStyle.secondary,custom_id=str(i),row=i//5)
            btn.callback=self.make_callback(i)
            self.add_item(btn)
    def make_callback(self,idx):
        async def callback(inter:discord.Interaction):
            try:
                if inter.user.id!=self.uid: return await inter.response.send_message("Not your game!",ephemeral=True)
                if idx in self.revealed: return await inter.response.defer()
                await inter.response.defer()
                self.revealed.add(idx)
                if idx in self.mine_pos:
                    embed=discord.Embed(color=0xED4245,title="Mines - BUSTED")
                    gems_found=len([r for r in self.revealed if r not in self.mine_pos])
                    total_gems=25-self.bombs
                    embed.description=f"Bet {fmt(self.bet)} Reached {self.mult:.1f}x Gems {gems_found}/{total_gems} Bombs {self.bombs} You hit bomb!"
                    embed.set_thumbnail(url=inter.user.display_avatar.url)
                    final_view=discord.ui.View()
                    for j in range(25):
                        row=j//5
                        if j in self.mine_pos:
                            b=discord.ui.Button(label="BOMB",style=discord.ButtonStyle.danger,row=row,disabled=True)
                            if j==idx: b.label="BOOM"
                        else: b=discord.ui.Button(label="GEM",style=discord.ButtonStyle.secondary,row=row,disabled=True)
                        final_view.add_item(b)
                    d=get_data(inter.user.id); d["profit"]-=self.bet; d["wagered"]+=self.bet
                    add_affiliate_reward(inter.user.id,self.bet)
                    await save_all()
                    await inter.edit_original_response(embed=embed,view=final_view)
                    self.stop(); return
                gems_found=len([r for r in self.revealed if r not in self.mine_pos])
                self.mult=round(1.0 + gems_found*0.25 + (gems_found**2)*0.15,2)
                if gems_found==0: self.mult=1.0
                embed=discord.Embed(color=0x2B2D31,title="Mines")
                total_gems=25-self.bombs
                win_now=int(self.bet*self.mult)
                embed.description=f"Bet {fmt(self.bet)} Reached {self.mult:.1f}x Gems {gems_found}/{total_gems} Bombs {self.bombs} Current {fmt(win_now)}"
                embed.set_thumbnail(url=inter.user.display_avatar.url)
                new_view=MinesView(self.uid,self.bet,self.bombs)
                new_view.mine_pos=self.mine_pos; new_view.revealed=self.revealed; new_view.mult=self.mult
                new_view.clear_items()
                for j in range(25):
                    row=j//5
                    if j in self.revealed: b=discord.ui.Button(label="GEM",style=discord.ButtonStyle.success,row=row,disabled=True)
                    else:
                        b=discord.ui.Button(label="?",style=discord.ButtonStyle.secondary,custom_id=str(j),row=row)
                        b.callback=new_view.make_callback(j)
                    new_view.add_item(b)
                cash_btn=discord.ui.Button(label=f"CASHOUT {self.mult}x = {fmt(win_now)}",style=discord.ButtonStyle.success,row=4)
                async def cash_callback(c_inter:discord.Interaction):
                    try:
                        if c_inter.user.id!=new_view.uid: return await c_inter.response.send_message("Not yours",ephemeral=True)
                        await c_inter.response.defer()
                        win=int(new_view.bet*new_view.mult)
                        d=get_data(c_inter.user.id); d["balance"]+=win; d["wagered"]+=new_view.bet; d["profit"]+=win-new_view.bet; d["withdrawn"]+=win
                        add_affiliate_reward(c_inter.user.id,new_view.bet)
                        await save_all()
                        e=discord.Embed(color=0x57F287,title="Mines - CASHOUT")
                        e.description=f"Bet {fmt(new_view.bet)} Reached {new_view.mult}x Won {fmt(win)}!"
                        e.set_thumbnail(url=c_inter.user.display_avatar.url)
                        await c_inter.edit_original_response(embed=e,view=discord.ui.View())
                        new_view.stop()
                    except Exception as e: print(f"cash err {e}")
                cash_btn.callback=cash_callback
                new_view.add_item(cash_btn)
                await inter.edit_original_response(embed=embed,view=new_view)
                self.stop()
            except Exception as e: print(f"mines cb err {e}")
        return callback

@bot.tree.command(name="mines",description="Play mines PS99")
async def mines_cmd(inter:discord.Interaction,bet:str,bombs:int=23):
    try:
        await inter.response.defer()
        bval=parse_amount(bet,get_data(inter.user.id)["balance"])
        d=get_data(inter.user.id)
        if d["balance"]<bval: return await inter.followup.send(embed=no_money_embed(d["balance"],bval),ephemeral=True)
        d["balance"]-=bval; await save_all()
        if bombs<1 or bombs>24: bombs=23
        view=MinesView(inter.user.id,bval,bombs)
        embed=discord.Embed(color=0x2B2D31,title="Mines")
        total_gems=25-bombs
        embed.description=f"Bet {fmt(bval)} Reached 1.0x Gems 0/{total_gems} Bombs {bombs}"
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        await inter.followup.send(embed=embed,view=view)
    except Exception as e: print(f"mines err {e}")

COLORS={"white":"White","purple":"Purple","green":"Green","red":"Red","blue":"Blue","orange":"Orange"}
PAYOUTS={0:0.0,1:2.0,2:0.48,3:3.0,4:4.0,5:4.0,6:4.0}

class ColorDiceView(discord.ui.View):
    def __init__(self,uid,bet):
        super().__init__(timeout=120)
        self.uid=uid; self.bet=bet
        options=[]
        for key in COLORS.keys(): options.append(discord.SelectOption(label=COLORS[key],value=key))
        select=discord.ui.Select(placeholder="Choose your color...",options=options)
        select.callback=self.select_callback
        self.add_item(select)
    async def select_callback(self,inter:discord.Interaction):
        try:
            if inter.user.id!=self.uid: return await inter.response.send_message("Not your game!",ephemeral=True)
            picked_key=self.children[0].values[0]
            picked_name=COLORS[picked_key]
            await inter.response.defer()
            embed_roll=discord.Embed(color=0x2B2D31,title="Color Dice")
            embed_roll.description=f"Bet {fmt(self.bet)} Rolling..."
            embed_roll.set_thumbnail(url=inter.user.display_avatar.url)
            await inter.edit_original_response(embed=embed_roll,view=self)
            await asyncio.sleep(1.5)
            dice=random.choices(list(COLORS.keys()),k=6)
            dice_str=" ".join(dice)
            matches=dice.count(picked_key)
            mult=PAYOUTS[matches]
            win=int(self.bet*mult)
            d=get_data(inter.user.id)
            if mult>0: d["balance"]+=win; d["profit"]+=win-self.bet; d["withdrawn"]+=win
            else: d["profit"]-=self.bet
            d["wagered"]+=self.bet
            add_affiliate_reward(inter.user.id,self.bet)
            await save_all()
            desc = f"Bet {fmt(self.bet)} Multiplier {mult}x ({fmt(win)})\nDice roll {dice_str}\nYour pick {picked_name}\nMatches {matches}"
            if matches==0: desc+= " - 0 col = 0x LOSE"
            elif matches==1: desc+= " - 1 col = 2x"
            elif matches==2: desc+= " - 2 col = 0.48x"
            elif matches==3: desc+= " - 3 col = 3x"
            else: desc+= f" - {matches} col = 4x"
            final=discord.Embed(color=0x57F287 if mult>0 else 0xED4245,title="Color Dice")
            final.description=desc
            final.set_thumbnail(url=inter.user.display_avatar.url)
            await inter.edit_original_response(embed=final,view=discord.ui.View())
            self.stop()
        except Exception as e: print(f"colordice err {e}")

@bot.tree.command(name="colordice",description="Color dice")
async def colordice_cmd(inter:discord.Interaction,bet:str):
    try:
        await inter.response.defer()
        bval=parse_amount(bet,get_data(inter.user.id)["balance"])
        d=get_data(inter.user.id)
        if d["balance"]<bval: return await inter.followup.send(embed=no_money_embed(d["balance"],bval),ephemeral=True)
        d["balance"]-=bval; await save_all()
        embed=discord.Embed(color=0x2B2D31,title="Color Dice")
        embed.description=f"Bet {fmt(bval)} Payout 0 col -> 0x LOSE 1 col -> 2x 2 col -> 0.48x 3 col -> 3x 4 col -> 4x"
        embed.set_thumbnail(url=inter.user.display_avatar.url)
        view=ColorDiceView(inter.user.id,bval)
        await inter.followup.send(embed=embed,view=view)
    except Exception as e: print(f"colordice cmd err {e}")

@bot.tree.command(name="blackjack",description="Play blackjack")
async def blackjack_cmd(inter:discord.Interaction,bet:str):
    try:
        await inter.response.defer()
        bval=parse_amount(bet,get_data(inter.user.id)["balance"])
        d=get_data(inter.user.id)
        if d["balance"]<bval: return await inter.followup.send(embed=no_money_embed(d["balance"],bval),ephemeral=True)
        d["balance"]-=bval; await save_all()
        deck=[2,3,4,5,6,7,8,9,10,10,10,10,11]*4; random.shuffle(deck)
        def score(h):
            s=sum(h); c=h.count(11)
            while s>21 and c: s-=10; c-=1
            return s
        ph=[deck.pop(),deck.pop()]; dh=[deck.pop(),deck.pop()]
        class BJView(discord.ui.View):
   
