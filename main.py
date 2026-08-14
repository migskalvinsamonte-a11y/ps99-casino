import discord, os, json, random
from discord import app_commands
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="?", intents=intents)

DB_FILE = "balances.json"

def load_db():
    if not os.path.exists(DB_FILE): return {}
    with open(DB_FILE, "r") as f: return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f)

def format_num(n):
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if n >= 1_000: return f"{n/1_000:.2f}K"
    return str(n)

def get_user(uid):
    db = load_db()
    if str(uid) not in db:
        db[str(uid)] = {"balance": 0, "deposited": 0, "withdrawn": 0, "wagered": 0, "profit": 0}
        save_db(db)
    return db[str(uid)], db

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Logged as {bot.user}")

# --- /balance ---
@bot.tree.command(name="balance", description="Check your casino balance")
async def balance(interaction: discord.Interaction):
    user_data, db = get_user(interaction.user.id)
    
    embed = discord.Embed(title=f"{interaction.user.display_name}'s balance", color=0x2B88D8)
    bal = user_data["balance"]
    embed.add_field(name="", value=(
        f"💎 **Balance** `{format_num(bal)}  ({bal:,})`\n"
        f"📥 **Deposited** `{user_data['deposited']}`\n"
        f"📤 **Withdrawn** `{user_data['withdrawn']}`\n"
        f"💎 **Wagered** `{format_num(user_data['wagered'])}`\n"
        f"💸 **Profit** `{format_num(user_data['profit'])}`\n"
        f"━━━━━━━━━━━━━━\n**Account**\n"
        f"💎 **Linked username** `Not linked`"
    ), inline=False)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Advanced Stats", style=discord.ButtonStyle.secondary))
    
    await interaction.response.send_message(embed=embed, view=view)

# --- /daily ---
@bot.tree.command(name="daily", description="Claim daily reward")
async def daily(interaction: discord.Interaction):
    user_data, db = get_user(interaction.user.id)
    reward = 5000000
    user_data["balance"] += reward
    db[str(interaction.user.id)] = user_data
    save_db(db)
    await interaction.response.send_message(f"✅ You claimed {format_num(reward)}! New balance: {format_num(user_data['balance'])}", ephemeral=True)

bot.run(os.getenv("TOKEN"))
