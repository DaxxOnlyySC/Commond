import sys, os, time, json, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import re

import win32file
import win32pipe
import pywintypes

# ============== CONFIGURATION ==============
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
PIPE_CMD_NAME  = r'\\.\pipe\luaexec_discord_cmd'
PIPE_RESP_NAME = r'\\.\pipe\luaexec_discord_resp'
OWNER_ID = 1286240448775720962

WL_PC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'whitelist.txt')

WORKER_URLS = {
    "kick": "https://kickplayer.miniworldgameapp.workers.dev/",
    "fans": "https://verifygetfans.miniworldgameapp.workers.dev/",
    "medal": "https://getverifymedal.miniworldgameapp.workers.dev/",
    "points": "https://getminipoint.miniworldgameapp.workers.dev/",
    "rename": "https://setaccountname.miniworldgameapp.workers.dev/",
    "season": "https://getseasonexperience.miniworldgameapp.workers.dev/",
    "map": "https://miniworld-api.daxtercarl1202.workers.dev/",
}

BADGE_NAMES = {
    "1001": "Demon Hunter", "1002": "Treasure Hunter", "1003": "Survival Expert",
    "1004": "Extremity God", "1005": "Mystery Gift", "1006": "Trendiest Trend",
    "1008": "Happy Partner", "1010": "Like Collector", "1011": "Green House",
    "1012": "Pest Killer", "1013": "Encyclopedia", "1014": "Harvest King",
    "1015": "Thriving Growth", "1016": "Full Assembly", "1017": "Mighty Me",
    "1018": "Fancy Transform", "1019": "Beast Tamer", "1020": "Wardrobe Master",
}

def get_whitelist_list():
    if not os.path.exists(WL_PC_PATH):
        return []
    with open(WL_PC_PATH, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def get_whitelist_set():
    s = set()
    permanent_uids = ["215394716", "1215394716", "10215394716", "210244113", "1210244113"]
    for p in permanent_uids:
        s.add(p)
    if os.path.exists(WL_PC_PATH):
        with open(WL_PC_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                clean = line.strip()
                if clean:
                    s.add(clean)
                    if len(clean) == 9 and clean.startswith('1'):
                        s.add(clean[1:])
                    elif len(clean) == 10 and clean.startswith('10'):
                        s.add(clean[2:])
    return s

def load_config():
    if not os.path.exists(CONFIG_FILE):
        default = {"bot_token": "YOUR_DISCORD_BOT_TOKEN", "prefix": "!", "channel_id": 0}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default, f, indent=4)
        print("[!] config.json created. Please fill in your bot_token!")
        sys.exit(1)
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

config = load_config()
TOKEN = config['bot_token']
PREFIX = config.get('prefix', '!')
MW_UIN = config.get('mini_uin', '320807253')
MW_PW = config.get('mini_pw', 'Daxter12345GG')

if TOKEN == 'YOUR_DISCORD_BOT_TOKEN':
    print("[!] Please fill in your bot_token inside config.json first!")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

trial_mode = False
workers_online = False
cmd_pipe = None
resp_pipe = None

# ============== PIPE FUNCTIONS ==============
def connect_pipes():
    global cmd_pipe, resp_pipe
    try:
        cmd_pipe = win32file.CreateFile(PIPE_CMD_NAME, win32file.GENERIC_READ | win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
        print("[OK] Connected to CMD pipe")
    except Exception as e:
        print(f"[ERR] CMD pipe: {e}")
        cmd_pipe = None
    try:
        resp_pipe = win32file.CreateFile(PIPE_RESP_NAME, win32file.GENERIC_READ | win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
        print("[OK] Connected to RESP pipe")
    except Exception as e:
        print(f"[ERR] RESP pipe: {e}")
        resp_pipe = None

def pipe_send(cmd):
    global cmd_pipe, resp_pipe
    if not cmd_pipe or not resp_pipe:
        return "[ERROR] Pipes not connected! Start bridge first."
    try:
        win32file.WriteFile(cmd_pipe, cmd.encode('utf-8'))
    except Exception as e:
        return f"[ERROR] Send failed: {e}"
    try:
        hr, data = win32file.ReadFile(resp_pipe, 65536)
        return data.decode('utf-8')
    except Exception as e:
        return f"[ERROR] Read failed: {e}"

# ============== WORKER CHECK ==============
async def check_workers():
    global workers_online
    try:
        async with aiohttp.ClientSession() as session:
            r = await session.get(WORKER_URLS["points"], timeout=aiohttp.ClientTimeout(total=10))
            text = await r.text()
            workers_online = "error" in text.lower() or "code" in text.lower() or "114514" in text
            print(f"[HEALTH] Workers: {'ONLINE' if workers_online else 'OFFLINE'}", flush=True)
    except Exception as e:
        workers_online = False
        print(f"[HEALTH] Workers OFFLINE: {e}", flush=True)

@tasks.loop(minutes=5)
async def health_loop():
    await check_workers()

def MW_WARNING_embed(action, description):
    embed = discord.Embed(title=f"WARNING: USE {action} BUG", description=f"**WARNING**\n\nUSING THIS FEATURE MAY TRIGGER **PERMANENT BAN**.\nWE ARE NOT RESPONSIBLE FOR ANY CONSEQUENCES.\n\nFeature: **{action}** - {description}", color=discord.Color.red())
    embed.set_footer(text="Mini World: CREATA | Use at your own risk")
    return embed

# ============== TRIAL CHECK ==============
def check_trial_or_owner():
    async def predicate(ctx):
        if trial_mode:
            return True
        if ctx.author.id == OWNER_ID:
            return True
        embed = discord.Embed(title="Access Denied", description="Trial mode OFF. Owner only.", color=0xff0000)
        await ctx.send(embed=embed, delete_after=5)
        return False
    return commands.check(predicate)

# ============== MAP API FUNCTIONS ==============
async def get_player_maps(uin, country="ID"):
    url = f"{WORKER_URLS['map']}?uin={uin}&country={country}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                if r.status != 200:
                    return {"error": f"HTTP status {r.status}"}
                return await r.json()
    except asyncio.TimeoutError:
        return {"error": "Request timeout! Worker terlalu lama merespon."}
    except Exception as e:
        return {"error": str(e)[:150]}

# ============== BOT EVENTS ==============
@bot.event
async def on_ready():
    print(f"[OK] Bot online: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}cmds | Trial: OFF"), status=discord.Status.dnd)
    await check_workers()
    if not health_loop.is_running():
        health_loop.start()

# ============== MAP COMMANDS (Slash & Prefix) ==============
@bot.tree.command(name="map", description="Check Mini World player map history by UIN")
async def map_history_slash(interaction: discord.Interaction, uin: str):
    await interaction.response.defer()
    data = await get_player_maps(uin)

    if isinstance(data, dict) and "error" in data:
        await interaction.followup.send(f"❌ Error: {data['error']}")
        return

    maps_list = []
    if isinstance(data, list):
        maps_list = data
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                maps_list = value
                break
        if not maps_list and data:
            maps_list = [data]

    if not maps_list:
        await interaction.followup.send(f"⚠️ Tidak ada data map atau UIN tidak valid: **{uin}**")
        return

    embed = discord.Embed(title=f"Map History - UIN {uin}", color=0x00ff00)
    description = ""
    for i, m in enumerate(maps_list[:10], 1):
        name = m.get("name", m.get("map_name", "Unnamed"))
        pc = m.get("play_count", m.get("plays", 0))
        cc = m.get("collect", m.get("favorites", 0))
        description += f"**{i}.** {name}\n     Plays: {pc:,} | Fav: {cc:,}\n"

    embed.description = description
    embed.set_footer(text="Mini World Map API")
    await interaction.followup.send(embed=embed)

@bot.command(name='maplookup', aliases=['map'])
async def map_prefix(ctx, uin: str = None):
    if not uin:
        await ctx.send(f"Usage: `{PREFIX}map <UIN>`")
        return
    
    msg = await ctx.send(f"🔍 Mencari data map untuk UIN **{uin}**...")
    data = await get_player_maps(uin)

    if isinstance(data, dict) and "error" in data:
        await msg.edit(content=f"❌ Error API: `{data['error']}`")
        return

    maps_list = []
    if isinstance(data, list):
        maps_list = data
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, list):
                maps_list = value
                break
        if not maps_list and data:
            maps_list = [data]

    if not maps_list:
        await msg.edit(content=f"⚠️ Tidak ada data map ditemukan untuk UIN **{uin}**.")
        return

    embed = discord.Embed(title=f"Map History - UIN {uin}", color=0x00ff00)
    description = ""
    for i, m in enumerate(maps_list[:10], 1):
        name = m.get("name", m.get("map_name", "Unnamed"))
        pc = m.get("play_count", m.get("plays", 0))
        cc = m.get("collect", m.get("favorites", 0))
        description += f"**{i}.** {name}\n     Plays: {pc:,} | Fav: {cc:,}\n"

    embed.description = description
    embed.set_footer(text="Mini World Map API", icon_url=ctx.author.display_avatar.url)
    await msg.edit(content=None, embed=embed)

# ============== LUA COMMANDS (via pipe) ==============
@bot.command(name='trial')
async def trial_cmd(ctx, status: str = None):
    global trial_mode
    if ctx.author.id != OWNER_ID:
        await ctx.send("Owner only!", delete_after=5)
        return
    if not status or status.lower() not in ['on', 'off']:
        await ctx.send(f"Usage: `{PREFIX}trial on/off` | Current: **{'ON' if trial_mode else 'OFF'}**")
        return
    trial_mode = True if status.lower() == 'on' else False
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}cmds | Trial: {'ON' if trial_mode else 'OFF'}"), status=discord.Status.dnd)
    await ctx.send(f"Trial mode: **{'ON' if trial_mode else 'OFF'}**")

@bot.command(name='ping')
@check_trial_or_owner()
async def ping_cmd(ctx):
    resp = pipe_send("ping")
    embed = discord.Embed(title="Pong!", description=str(resp), color=0x00ff00)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='inject')
@check_trial_or_owner()
async def inject_cmd(ctx):
    embed = discord.Embed(title="Injecting...", description="Injecting DLL into the game...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("inject")
    embed2 = discord.Embed(title="Inject Result", description=str(resp), color=0x00ff00)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='status')
@check_trial_or_owner()
async def status_cmd(ctx):
    resp = pipe_send("status")
    embed = discord.Embed(title="Game Status", description=str(resp), color=0x3498db)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='lua')
@check_trial_or_owner()
async def lua_cmd(ctx, *, code: str):
    embed = discord.Embed(title="Executing...", description=code[:100], color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("exec:" + code)
    if len(resp) > 1900:
        resp = resp[:1900] + "..."
    embed2 = discord.Embed(title="Lua Executed", description=str(resp), color=0x00ff00)
    embed2.add_field(name="Code", value=code[:200], inline=False)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='kick')
@check_trial_or_owner()
async def kick_lua_cmd(ctx, uid: str = None):
    if not uid:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}kick <UID>` (Lua method)", color=0xff0000)
        await ctx.send(embed=embed)
        return
    whitelisted_set = get_whitelist_set()
    real_uin = uid
    if len(uid) == 9:
        real_uin = "1" + uid
    elif len(uid) == 8:
        real_uin = "10" + uid
    if uid in whitelisted_set or real_uin in whitelisted_set:
        embed = discord.Embed(title="Kick Aborted", description=f"UID `{uid}` is in the **Whitelist**!", color=0xff0000)
        await ctx.send(embed=embed)
        return

    wl_lua_table = "{" + ", ".join([f'"{u}"' for u in whitelisted_set]) + "}"
    lua_code = f"""threadpool:work(function()
    local targetToCheck = "{real_uin}"
    threadpool:wait(0.1)
    AccountManager.cluster.buddysvr.routemore('gm.kick', targetToCheck, 0)
end)"""
    msg = await ctx.send(embed=discord.Embed(title="Kick Player (Lua)", description=f"Processing kick for UID `{uid}`...", color=0xffff00))
    pipe_send("exec:" + lua_code)
    await msg.edit(embed=discord.Embed(title="Kick Result", description=f"✅ Success Processed Kick for UID {uid}", color=0x00ff00))

@bot.command(name='kickpc')
@check_trial_or_owner()
async def kickpc_cmd(ctx):
    whitelisted_set = get_whitelist_set()
    wl_lua_table = "{" + ", ".join([f'"{u}"' for u in whitelisted_set]) + "}"
    lua_code = f"""threadpool:work(function()
    local whitelist = {wl_lua_table}
    local function isWL(u)
        local s = tostring(u)
        for _, w in ipairs(whitelist) do if w == s then return end end
    end
    while true do
        if CurWorld and CurMainPlayer and ClientCurGame and ClientCurGame:isInGame() then
            local myUin = AccountManager:getUin()
            local num = ClientCurGame:getNumPlayerBriefInfo()
            for i = 1, num do
                local briefInfo = ClientCurGame:getPlayerBriefInfo(i - 1)
                if briefInfo and briefInfo.uin and briefInfo.uin > 1000 and briefInfo.uin ~= myUin then
                    local targetUin = briefInfo.uin
                    local code, ret = BuddyManager:query_friend_info(targetUin)
                    if code == ErrorCode.OK and ret and ret.baseinfo and ret.baseinfo.extra then
                        if ret.baseinfo.extra.DeviceSystem == "windows" then
                            AccountManager.cluster.buddysvr.routemore('gm.kick', targetUin, 0)
                        end
                    end
                end
            end
        end
        threadpool:wait(1)
    end
end)"""
    msg = await ctx.send(embed=discord.Embed(title="Kick PC Players", description="Auto-kicking PC players...", color=0xffff00))
    resp = pipe_send("exec:" + lua_code)
    await msg.edit(embed=discord.Embed(title="Kick PC Started", description=str(resp), color=0xff0000))

@bot.command(name='whitelist')
async def whitelist_cmd(ctx, uid: str = None):
    if ctx.author.id != OWNER_ID:
        await ctx.send("Owner only!", delete_after=5)
        return
    if not uid:
        await ctx.send(f"Usage: `{PREFIX}whitelist <UID>`")
        return
    real_uin = "1" + uid if len(uid) == 9 else uid
    existing = get_whitelist_list()
    if real_uin in existing or uid in existing:
        new_list = [u for u in existing if u != real_uin and u != uid]
        action = "REMOVED"
    else:
        existing.append(real_uin)
        new_list = existing
        action = "ADDED"
    with open(WL_PC_PATH, 'w', encoding='utf-8') as f:
        for u in new_list:
            f.write(u + "\n")
    await ctx.send(embed=discord.Embed(title="Whitelist Updated", description=f"Action: `{action}` | UID: `{uid}`", color=0x00ff00))

@bot.command(name='listwhitelist')
@check_trial_or_owner()
async def list_wl_cmd(ctx):
    wl_list = get_whitelist_list()
    desc = "\n".join([f"`{u}`" for u in wl_list]) if wl_list else "Whitelist kosong."
    await ctx.send(embed=discord.Embed(title="Daftar UID Whitelist", description=desc, color=0x3498db))

# ============== CLOUDFLARE API COMMANDS ==============
@bot.command(name='mwstatus')
async def mwstatus_cmd(ctx):
    status = "ONLINE" if workers_online else "OFFLINE"
    embed = discord.Embed(title="Workers Status", color=discord.Color.green() if workers_online else discord.Color.red())
    for name in WORKER_URLS:
        embed.add_field(name=name.capitalize(), value=status, inline=True)
    await ctx.send(embed=embed)

@bot.command(name='fans')
@check_trial_or_owner()
async def fans_cmd(ctx):
    if not workers_online:
        await ctx.send("Workers Offline!")
        return
    await ctx.send(embed=MW_WARNING_embed("FANS", "Verify/add fans"), view=MWAuthView("FANS"))

@bot.command(name='medal')
@check_trial_or_owner()
async def medal_cmd(ctx):
    if not workers_online:
        await ctx.send("Workers Offline!")
        return
    await ctx.send(embed=MW_WARNING_embed("MEDAL", "Equip medal/badge"), view=MedalBadgeSelect())

@bot.command(name='points')
@check_trial_or_owner()
async def points_cmd(ctx):
    if not workers_online:
        await ctx.send("Workers Offline!")
        return
    await ctx.send(embed=MW_WARNING_embed("POINTS", "Add points"), view=MWAuthView("POINTS"))

@bot.command(name='rename')
@check_trial_or_owner()
async def rename_cmd(ctx, *, new_name: str = None):
    if not new_name:
        await ctx.send(f"Usage: `{PREFIX}rename <new_name>`")
        return
    if not workers_online:
        await ctx.send("Workers Offline!")
        return
    await ctx.send(embed=MW_WARNING_embed("RENAME", f"Change name to `{new_name}`"), view=MWAuthView("RENAME", {"new_name": new_name}))

@bot.command(name='season')
@check_trial_or_owner()
async def season_cmd(ctx):
    if not workers_online:
        await ctx.send("Workers Offline!")
        return
    await ctx.send(embed=MW_WARNING_embed("SEASON", "Season Pass XP"), view=MWAuthView("SEASON"))

# ============== VIEWS ==============
class MWAuthModal(discord.ui.Modal, title="Masukkan Data Akun"):
    uid_input = discord.ui.TextInput(label="UID (10 digit)", placeholder="Contoh: 320807253", required=True)
    pw_input = discord.ui.TextInput(label="Password", placeholder="Password akun Mini World", required=True)

    def __init__(self, action, extra_data=None):
        super().__init__()
        self.action = action
        self.extra_data = extra_data or {}

    async def on_submit(self, interaction: discord.Interaction):
        uid = self.uid_input.value.strip()
        pwd = self.pw_input.value.strip()
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                if self.action == "FANS":
                    url = f"https://verifygetfans.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    res_txt = f"Fans Success: `{uid}`" if data.get("code") == 114514 else f"Failed: {data}"
                    await interaction.followup.send(res_txt, ephemeral=True)
                elif self.action == "POINTS":
                    url = f"https://getminipoint.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    res_txt = f"Points Success: `{uid}`" if data.get("code") == 114514 else f"Failed: {data}"
                    await interaction.followup.send(res_txt, ephemeral=True)
                elif self.action == "RENAME":
                    new_name = self.extra_data.get("new_name", "")
                    token = hashlib.sha256((uid + pwd + new_name + "fuckmini114514").encode()).hexdigest()
                    url = f"https://setaccountname.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&newName={new_name}&token={token}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    res_txt = f"Rename Success: `{new_name}`" if data.get("code") == 114514 else f"Failed: {data}"
                    await interaction.followup.send(res_txt, ephemeral=True)
                elif self.action == "MEDAL":
                    medal_ids = self.extra_data.get("medal_ids", "1001")
                    token = hashlib.sha256((uid + pwd + medal_ids + "fuckmini114514").encode()).hexdigest()
                    url = f"https://getverifymedal.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&medalid={medal_ids}&token={token}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    res_txt = f"Medal Success: `{uid}`" if data.get("code") == 114514 else f"Failed: {data}"
                    await interaction.followup.send(res_txt, ephemeral=True)
                elif self.action == "SEASON":
                    r1 = await session.get(f"https://getseasonexperience.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&type=1", timeout=aiohttp.ClientTimeout(total=15))
                    d1 = await r1.json()
                    if d1.get("code") != 114514:
                        await interaction.followup.send(f"Season Phase 1 Failed: {d1}", ephemeral=True)
                        return
                    r2 = await session.get(f"https://getseasonexperience.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&type=2", timeout=aiohttp.ClientTimeout(total=15))
                    d2 = await r2.json()
                    res_txt = f"Season Success: `{uid}`" if d2.get("code") == 114514 else f"Phase 2 Failed: {d2}"
                    await interaction.followup.send(res_txt, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error: {str(e)[:200]}", ephemeral=True)

class MWAuthView(discord.ui.View):
    def __init__(self, action, extra_data=None):
        super().__init__(timeout=120)
        self.action = action
        self.extra_data = extra_data or {}

    @discord.ui.button(label="EXECUTE", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def execute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MWAuthModal(self.action, self.extra_data))

class MedalBadgeSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.select(placeholder="Select Badge", min_values=1, max_values=5, options=[discord.SelectOption(label=name, value=bid) for bid, name in BADGE_NAMES.items()])
    async def badge_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        ids_str = ",".join(select.values)
        names = [BADGE_NAMES.get(v, v) for v in select.values]
        embed = discord.Embed(title="Medal Bug", description=f"**Selected:**\n" + "\n".join(f"- {n}" for n in names) + f"\n\nIDs: `{ids_str}`", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=MWAuthView("MEDAL", {"medal_ids": ids_str}))

# ============== MENU ==============
@bot.command(name='menu')
async def menu_cmd(ctx):
    embed = discord.Embed(title="Mini World Bot - All Commands", color=0x9b59b6)
    embed.add_field(name="--- MAP API ---", value=f"`{PREFIX}map <uin>` or `/map <uin>`", inline=False)
    embed.add_field(name="--- LUA (via pipe) ---", value=f"`{PREFIX}kick` `{PREFIX}kickpc` `{PREFIX}lua`", inline=False)
    embed.add_field(name="--- CLOUDFLARE API ---", value=f"`{PREFIX}fans` `{PREFIX}medal` `{PREFIX}points` `{PREFIX}rename` `{PREFIX}season` `{PREFIX}mwstatus`", inline=False)
    embed.add_field(name="--- OTHER ---", value=f"`{PREFIX}inject` `{PREFIX}status` `{PREFIX}ping` `{PREFIX}whitelist` `{PREFIX}trial`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name='cmds')
async def cmds_cmd(ctx):
    embed = discord.Embed(title="All Commands", color=0x3498db)
    embed.add_field(name=f"{PREFIX}map <uin>", value="Check player map history", inline=False)
    embed.add_field(name=f"{PREFIX}kick <uid>", value="Kick player (Lua pipe)", inline=False)
    embed.add_field(name=f"{PREFIX}fans", value="Verify fans (API)", inline=False)
    embed.add_field(name=f"{PREFIX}medal", value="Equip badge (API)", inline=False)
    embed.add_field(name=f"{PREFIX}points", value="Add points (API)", inline=False)
    embed.add_field(name=f"{PREFIX}rename <name>", value="Change name (API)", inline=False)
    embed.add_field(name=f"{PREFIX}season", value="Season Pass XP (API)", inline=False)
    await ctx.send(embed=embed)

# ============== MAIN ==============
def main():
    print("=" * 50)
    print("  LuaExec Discord Bot v2.0 (Fully Fixed)")
    print("=" * 50)
    connect_pipes()
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
