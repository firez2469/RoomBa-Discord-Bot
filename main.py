import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from discord import app_commands, SelectMenu, SelectOption,ui
from discord.ext import commands
from discord.ext.commands import has_permissions, MissingPermissions
from typing import Optional
import json
import asyncio


load_dotenv()

# Loads the token from the .env file
TOKEN = os.getenv('DISCORD_TOKEN')

# Enables all discord intents.
intents = discord.Intents.all()

# Creates a bot object with the specified command prefix and intents.
bot = commands.Bot(command_prefix="!", intents=intents)


# Creates a group of commands for the bot.
admin_commands = app_commands.Group(name="admin",description="Admin commands")
room_commands = app_commands.Group(name="room",description="Room Commands")

data = {"rooms":{}}

server_id = os.getenv('GUILD_ID')

# testing
server_id = os.getenv('TESTING_GUILD_ID')


def new_room_template(name:str,owner:discord.User):
    return {
        "name":name,
        "owner":owner.id,
        "allowed": [owner.id]
    }

def save():
    global data
    print("Saved!")
    json.dump(data,open("data.json","w"))

# Create a accept/deny menu
class AcceptSelect(ui.Select):
    def __init__(self, user,channel_id:int,guild_id:int):
        self.channel_id = channel_id
        self.server_id = guild_id
        options = [discord.SelectOption(label="Accept", value=user.id),discord.SelectOption(label="Decline", value="Decline")]
        # Initialize the select menu with these options and a placeholder
        super().__init__(placeholder=f"Accept or deny {user}", options=options, custom_id="candidate_select_menu")
    
    # This method is called when the user selects an option
    async def callback(self, interaction: discord.Interaction):
        # given the name find the user by name using discord.py
        output = str(self.values[0])
        if output == "Decline":
            await interaction.response.send_message("You declined the request!")
            return
        
        # search user by id
        guild = discord.utils.get(bot.guilds,id=server_id)
        user = discord.utils.get(guild.members,id=int(output))
        channel = discord.utils.get(guild.channels,id=self.channel_id)

        data["rooms"][self.channel_id]["allowed"].append(user.id)
        await channel.set_permissions(user,read_messages=True,send_messages=True)
        await interaction.response.send_message(f"{user.mention} was added to the room!")
        save()

# Create a view for the election
class AcceptView(ui.View):
    def __init__(self, user,channel_id:int,guild_id:int):
        super().__init__()
        self.user = user
        self.add_item(AcceptSelect(user, channel_id=channel_id,guild_id=guild_id))


# Create a new Room.
@admin_commands.command(name="create",description="Create a new room with the",extras={"date":"The date of the election"})
@app_commands.describe(channel="Text channel being used",name="Name of the room",owner="Owner of the room")
async def create(ctx,channel:discord.TextChannel,name:str,owner:discord.User):
    room = new_room_template(name,owner)
    data["rooms"][int(channel.id)] = room
    # set channel permissions to allow ctx.user to see it and no-one else
    await channel.set_permissions(ctx.user,read_messages=True,send_messages=True)
    await ctx.response.send_message(f"Room {name} created in {channel.mention}")
    save()

# Delete a new election command.
@admin_commands.command(name="delete",description="Delete a room")
@app_commands.describe(channel="The channel attached to this room")
async def delete(ctx,channel:discord.TextChannel):
    if channel.id in data["rooms"]:
        del data["rooms"][channel.id]
        await ctx.response.send_message(f"Room in {channel.mention} deleted")
    else:
        await ctx.response.send_message(f"Room in {channel.mention} not found")
    save()

@admin_commands.command(name="reset",description="Reset all rooms (aka delete them all)")
@app_commands.describe()
async def reset(ctx):
    data["rooms"] = {"rooms":{}}
    await ctx.response.send_message("All rooms reset")
    save()    


@admin_commands.command(name="change_owner",description="Change the owner of a room")
@app_commands.describe(channel="Text channel being used",owner="Owner of the room")
async def change_owner(ctx,channel:discord.TextChannel,owner:discord.User):
    if channel.id in data["rooms"]:
        if owner.id not in data["rooms"][channel.id]["allowed"]:
            owner = data["rooms"][channel.id]["owner"]
            owner = discord.utils.get(ctx.guild.members,id=owner)
            await channel.set_permissions(owner,read_messages=False,send_messages=False)
        data["rooms"][channel.id]["owner"] = owner.id
        await channel.set_permissions(owner,read_messages=True,send_messages=True)
        await ctx.response.send_message(f"Owner of room in {channel.mention} changed to {owner.mention}")
    else:
        await ctx.response.send_message(f"Room in {channel.mention} not found")
    save()

@room_commands.command(name="join",description="Request to join a room")
@app_commands.describe()
async def join(ctx,name:str):
    for room in data["rooms"]:
        if data["rooms"][room]["name"] == name:
            if ctx.user.id in data["rooms"][room]["allowed"]:
                await ctx.response.send_message(f"You are already in {name}")
            else:
                # send a embed dm to the owner with a button to accept or deny them entry.
                embed = discord.Embed(title="Join Request",description=f"{ctx.user.mention} wants to join {name}")
                
                # create the view and send to dms/server.
                view = AcceptView(ctx.user,room,str(ctx.guild.id))
                owner = data["rooms"][room]["owner"]
                owner = discord.utils.get(ctx.guild.members,id=owner)
                await owner.send(embed=embed, view=view)
                await ctx.response.send_message(f"Request sent to {owner.name}")
            save()
            return
        
    await ctx.response.send_message(f"Room `{name}` not found")
    save()

@room_commands.command(name="leave",description="Leave a room")
@app_commands.describe()
async def leave(ctx,name:str):
    for room in data["rooms"]:
        if data["rooms"][room]["name"] == name:
            if ctx.user.id in data["rooms"][room]["allowed"]:
                data["rooms"][room]["allowed"].remove(ctx.user.id)
                # remove permissions to read channel
                channel = discord.utils.get(ctx.guild.channels,id=room)
                await channel.set_permissions(ctx.user,read_messages=False,send_messages=False)
                await channel.send(f"{ctx.user.mention} has left the room")
                await ctx.response.send_message(f"You have left {name}")
            else:
                await ctx.response.send_message(f"You are not in {name}")
            save()
            return
    await ctx.response.send_message(f"Room `{name}` not found")


@room_commands.command(name="list",description="List all rooms")
@app_commands.describe()
async def list(ctx):
    
    text = ""
    for room in data["rooms"]:
        r1 = data["rooms"][room]['name']
        owner = discord.utils.get(ctx.guild.members,id=data["rooms"][room]['owner'])
        r2 = owner.mention
        print("Getting channel ",room)
        r3 = discord.utils.get(ctx.guild.channels,id=int(room)).mention
        text += f"{r1} - {r2} ({r3})\n"
        
    embed = discord.Embed(title="Rooms",description=text)
    await ctx.response.send_message(embed=embed)

@room_commands.command(name="kick",description="Kick a user from a room")
@app_commands.describe()
async def kick(ctx,room_name:str,user:discord.User):
    name = room_name
    for room in data["rooms"]:
        if data["rooms"][room]["name"] == name:
            if ctx.user.id == data["rooms"][room]["owner"]:
                if user.id in data["rooms"][room]["allowed"]:
                    data["rooms"][room]["allowed"].remove(user.id)

                    channel = discord.utils.get(ctx.guild.channels,id=room)
                    await channel.set_permissions(user,read_messages=False,send_messages=False)
                    await channel.send(f"{user.mention} was kicked from the room")
                    await ctx.response.send_message(f"{user.mention} was kicked from {name}")
                else:
                    await ctx.response.send_message(f"{user.mention} is not in {name}")
            else:
                await ctx.response.send_message(f"You are not the owner of {name}")
            save()
            return
    await ctx.response.send_message(f"Room `{name}` not found")


@room_commands.command(name="slide", description="Slide a user from one room to another")
@app_commands.describe()
async def slide(ctx):
    rooms_slide = json.loads(os.getenv('SLIDE'))
    initial_room= rooms_slide[0]
    if ctx.channel.id != initial_room:
        await ctx.response.send_message("You cannot slide from this room")
        return

    for room in rooms_slide:
        channel = discord.utils.get(ctx.guild.channels,id=room)
        # give user permission to read
        await channel.set_permissions(ctx.user,read_messages=True,send_messages=True)
        msg = await channel.send(f"{ctx.user.mention} has been slid into this room")
        await asyncio.sleep(1)
        await msg.delete()
        msg = await channel.send(f"{ctx.user.mention} has been slid out of this room")
        await asyncio.sleep(1)
        await msg.delete()
        await channel.set_permissions(ctx.user,read_messages=False,send_messages=False)



# Add the command structure to the bot.
bot.tree.add_command(admin_commands)
bot.tree.add_command(room_commands)

# on ready event.
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    global data
    if os.path.exists("data.json"):
        print("Loading data..")
        data = json.load(open("data.json","r"))
    print("Saving data ",data)
    json.dump(data,open("data.json","w"))

    for guild in bot.guilds:
        print(f'{bot.user} is connected to the following guild:\n{guild.name} (id: {guild.id})')
        synced = await bot.tree.sync()
        print(f"Synced! {len(synced)} commands(s)")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="to secret conversations"))

# Run the bot!
bot.run(TOKEN)
