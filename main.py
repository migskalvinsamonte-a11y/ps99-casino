import discord, json, os, random
from discord.ext import commands
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)
DB_FILE = "db.json"
db = {}
if os.path.exists(DB_FILE):
    try: db = json.load(open(DB_FILE))
    except: db = {}
def save(): json.dump(db, open(DB_FILE, "w"))
def get(k): return db.get(k, 0)
def add(k,v): db[k]=get(k)+v; save()
def sub(k,v): db[k]=get(k)-v; save()
@bot.event
async def on_ready(): print(f"Bot online as {bot.user}")
@bot.command()
async def balance(ctx):
    id = str(ctx.author.id)
    embed = discord.Embed(color=0xFFC800)
    embed.set_author(name=f"{ctx.author.name}'s balance")
    embed.description = f"💎 Balance `{get(f'money_{id}'):,}`\n📥 Deposited `{get(f'deposited_{id}'):,}`\n📤 Withdrawn `{get(f'withdrawn_{id}'):,}`\n💎 Wagered `{get(f'wagered_{id}'):,}`\n💸 Profit `{get(f'profit_{id}'):,}`"
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)
@bot.command()
async def daily(ctx): add(f"money_{ctx.author.id}", 1000000); await ctx.send("Claimed 1M!")
@bot.command()
async def deposit(ctx, amount: int = None):
    id = str(ctx.author.id)
    if not amount: return await ctx.send("?deposit 1000000")
    sub(f"money_{id}", amount); add(f"bank_{id}", amount); add(f"deposited_{id}", amount)
    await ctx.send(f"Deposited {amount:,} -?balance")
@bot.command()
async def cf(ctx, amount: int = None):
    id = str(ctx.author.id)
    if not amount or get(f"money_{id}") < amount: return await ctx.send("No money")
    sub(f"money_{id}", amount); add(f"wagered_{id}", amount)
    if random.random() > 0.5: add(f"money_{id}", amount*2); add(f"profit_{id}", amount); await ctx.send(f"WON {amount*2:,}")
    else: sub(f"profit_{id}", amount); await ctx.send(f"LOST {amount:,}")
bot.run(os.getenv("TOKEN"))
