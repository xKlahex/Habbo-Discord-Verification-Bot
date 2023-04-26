import os
import requests
import random
import string
import datetime
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json

# Move variables to the top
VERIFIED_ROLE_ID = 123456789 # INSERT_ROLE_ID_HERE
LOG_CHANNEL_ID = 123456789 # INSERT_LOG_CHANNEL_ID_HERE
VERIFICATION_CUTOFF_DATE = '2023-04-01T00:00:00.000Z' # ACCOUNT_AGE_REQUIEREMENT
REQUIRED_LEVEL = 10 # LEVEL_REQUIEREMENT

load_dotenv()
intents = discord.Intents.all()
intents.members = True
bot = commands.Bot(command_prefix="!g", intents=intents, description="Habbo Helper Bot")

token = os.getenv("DISCORD_TOKEN")

async def send_verification_embed(channel, username, ctx, userInfo, log_data):
    embed = discord.Embed(title=f"{username} has verified!", color=0x00ff00)
    embed.description = f"**Username:** {username}\n"
    embed.description += f"**Previous Discord Username:** {ctx.author.name}\n"
    embed.description += f"**Habbo ID:** {userInfo['uniqueId']}\n"
    embed.description += f"**Current Level:** {userInfo['currentLevel']}\n"
    embed.description += f"**Member Since:** {userInfo['memberSince']}\n"
    embed.description += f"**Discord User ID:** {ctx.author.id}\n"
    embed.description += f"**Verification Date:** {log_data['verification_date']}\n"
    await channel.send(embed=embed)

async def update_verified_users_file(verified_users):
    with open('verified_users.json', 'w') as f:
        json.dump(verified_users, f)

async def log_verification(userInfo, log_data):
    with open('verification_logs.json', 'a') as f:
        json.dump(log_data, f)
        f.write('\n')

@bot.event
async def on_ready():
    print('+---------------------------------------------------+')
    print("Logged in and connected as: "+str(bot.user))
    print(f"Bot Username: {bot.user.name}")
    print(f"BotID: {bot.user.id}")
    print('+---------------------------------------------------+')
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="Habbo Hotel"))

@bot.hybrid_command(brief='Verify', description='Test')
async def verify(ctx, username):
    with open('verified_users.json', 'r') as f:
        verified_users = json.load(f)

    if username in [user["name"] for user in verified_users]:
        await ctx.send(f"{username} is already verified.")
        return

    apiUrl = f"https://www.habbo.com/api/public/users?name={requests.utils.quote(username)}"
    result = requests.get(apiUrl)
    userInfo = result.json()
    verification_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    if userInfo.get('error'):
        await ctx.send(f"User '{username}' could not be found. Please change your Privacy Settings, **set Profile visibility to everyone** otherwise we can't verify you.", ephemeral=True)
        return
    elif not userInfo.get('currentLevel') or userInfo['currentLevel'] < REQUIRED_LEVEL:
        await ctx.send(f"User '{username}' does not meet the verification requirements. \nYou need at least **Account Level {REQUIRED_LEVEL}**\nPlease change your Privacy Settings, **set Profile visibility to everyone** otherwise we can't verify you.", ephemeral=True)
        return
    
    accountCreationDate = datetime.datetime.strptime(userInfo['memberSince'], '%Y-%m-%dT%H:%M:%S.%f%z')
    verificationCutoffDate = datetime.datetime.strptime(VERIFICATION_CUTOFF_DATE, '%Y-%m-%dT%H:%M:%S.%f%z')

    if accountCreationDate > verificationCutoffDate:
        await ctx.send(f"User '{username}' does not meet the verification requirements.\nYour account must have been created before **February 2023**.\nPlease change your Privacy Settings, **set Profile visibility to everyone** otherwise we can't verify you.", ephemeral=True)
        return

    await ctx.send(f"Please change your motto to `Fansite #{verification_code}` in Habbo and type **Yes** in this chat to verify.", ephemeral=True)

    try:
        message = await bot.wait_for('message', check=lambda message: message.author == ctx.author and message.content.lower() == 'yes', timeout=400)
        result = requests.get(apiUrl)
        userInfo = result.json()
        newMotto = userInfo['motto']
        if f'Fansite #{verification_code}' not in newMotto:
            await ctx.send(f"Motto doesn't match, please try again.", ephemeral=True)
            return
    except asyncio.TimeoutError:
        await ctx.send('Verification timed out. Please try again.', ephemeral=True)
        return

    await ctx.send(f"Motto successfully verified. You now have the <@&{VERIFIED_ROLE_ID}> role.", ephemeral=True)
    try:
        await ctx.author.edit(nick=username)
        role = ctx.guild.get_role(VERIFIED_ROLE_ID)
        await ctx.author.add_roles(role)
    except discord.Forbidden:
        await ctx.send("Something went wrong. I do not have permission to set the nickname or add roles for this user, you're probably staff or admin so change it yourself <3", ephemeral=True)
        return

    verified_users.append({"name": username})
    await update_verified_users_file(verified_users)

    channel = bot.get_channel(LOG_CHANNEL_ID)
    await channel.send(f"User '{username}' has been verified. Logged in verification_logs.json")

    log_data = {
        "username": userInfo["name"],
        "habbo_id": userInfo["uniqueId"],
        "current_level": userInfo["currentLevel"],
        "member_since": userInfo["memberSince"],
        "verification_date": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }

    await log_verification(userInfo, log_data)

    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await send_verification_embed(channel, username, ctx, userInfo, log_data)

@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        with open('verified_users.json', 'r') as f:
            verified_users = json.load(f)

        for user in verified_users:
            if user["name"] == before.nick:
                verified_users.remove(user)
                await update_verified_users_file(verified_users)
                break

bot.run(token)
