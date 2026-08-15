import sys, os, time, json, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import discord
from discord.ext import commands
import aiohttp
import requests
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

from discord.ext import tasks
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
def get_player_maps(uin, country="ID"):
    cur_time = int(time.time())
    url = (
        f"http://shequ.miniworldgame.com:8080/miniw/map/"
        f"?act=get_room_new_tab_oversea"
        f"&uin={uin}"
        f"&country={country}"
        f"&apiid=410"
        f"&s2t={cur_time}"
        f"&ver=1.7.15"
        f"&time={cur_time}"
        f"&section=INA"
        f"&requestid=12345"
        f"&lang=15"
        f"&refreshIndex=1"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return parse_lua_table(r.text)
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def parse_lua_table(raw):
    result = {"recent": [], "featured": []}
    blocks = re.split(r'\[\d+\]=\{', raw)

    for block in blocks[1:]:
        try:
            wid = re.search(r'\["wid"\]="?(\d+)"?', block)
            name = re.search(r'\["name"\]="([^"]*)"', block)
            play = re.search(r'\["play_count"\]=(\d+)', block)
            collect = re.search(r'\["collectc"\]=(\d+)', block)

            map_data = {}
            if wid: map_data["wid"] = wid.group(1)
            if name: map_data["name"] = name.group(1)
            if play: map_data["play_count"] = int(play.group(1))
            if collect: map_data["collect"] = int(collect.group(1))

            if map_data.get("wid"):
                result["recent"].append(map_data)
        except:
            continue

    return result

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

    data = get_player_maps(uin)

    if "error" in data:
        await interaction.followup.send(f"Error: {data['error']}")
        return

    if not data["recent"]:
        await interaction.followup.send(f"No map data found for UIN **{uin}**.")
        return

    embed = discord.Embed(
        title=f"Map History - UIN {uin}",
        color=0x00ff00
    )

    description = ""
    for i, m in enumerate(data["recent"][:10], 1):
        name = m.get("name", "Unnamed")
        pc = m.get("play_count", 0)
        cc = m.get("collect", 0)
        description += f"**{i}.** {name}\n"
        description += f"     Plays: {pc:,} | Fav: {cc:,}\n"

    embed.description = description
    embed.set_footer(text="Mini World Map API | Powered by shequ.miniworldgame.com")

    await interaction.followup.send(embed=embed)

@bot.command(name='map')
async def map_prefix(ctx, uin: str = None):
    if not uin:
        await ctx.send(f"Usage: `{PREFIX}map <UIN>`")
        return
    data = get_player_maps(uin)

    if "error" in data:
        await ctx.send(f"Error: {data['error']}")
        return

    if not data["recent"]:
        await ctx.send(f"No map data found for UIN **{uin}**.")
        return

    embed = discord.Embed(
        title=f"Map History - UIN {uin}",
        color=0x00ff00
    )

    description = ""
    for i, m in enumerate(data["recent"][:10], 1):
        name = m.get("name", "Unnamed")
        pc = m.get("play_count", 0)
        cc = m.get("collect", 0)
        description += f"**{i}.** {name}\n"
        description += f"     Plays: {pc:,} | Fav: {cc:,}\n"

    embed.description = description
    embed.set_footer(text="Mini World Map API", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)

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
    alt_uid = uid[1:] if (len(uid) == 9 and uid.startswith('1')) or (len(uid) == 10 and uid.startswith('10')) else None
    if uid in whitelisted_set or real_uin in whitelisted_set or (alt_uid and alt_uid in whitelisted_set):
        embed = discord.Embed(title="Kick Aborted", description=f"UID `{uid}` (Real: `{real_uin}`) is in the **Whitelist**! Cannot kick.", color=0xff0000)
        embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
        return

    wl_lua_table = "{" + ", ".join([f'"{u}"' for u in whitelisted_set]) + "}"
    lua_code = f"""threadpool:work(function()
    local targetToCheck = "{real_uin}"
    local whitelist = {wl_lua_table}
    local function isWL(u)
        local s = tostring(u)
        for _, w in ipairs(whitelist) do
            if w == s then return true end
        end
        return false
    end
    threadpool:wait(0.1)
    AccountManager.cluster.buddysvr.routemore('gm.kick', targetToCheck, 0)
end)"""

    embed = discord.Embed(title="Kick Player (Lua)", description=f"Processing kick for UID `{uid}` (Real UIN: `{real_uin}`)...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("exec:" + lua_code)
    embed2 = discord.Embed(title="Kick Result", description=f"✅ Success Processed Kick for UID {uid} > {real_uin}", color=0x00ff00)
    embed2.add_field(name="Input UID", value=f"`{uid}`", inline=True)
    embed2.add_field(name="Real UIN", value=f"`{real_uin}`", inline=True)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='kickpc')
@check_trial_or_owner()
async def kickpc_cmd(ctx):
    whitelisted_set = get_whitelist_set()
    wl_lua_table = "{" + ", ".join([f'"{u}"' for u in whitelisted_set]) + "}"
    lua_code = f"""threadpool:work(function()
    local whitelist = {wl_lua_table}
    local function isWL(u)
        local s = tostring(u)
        for _, w in ipairs(whitelist) do
            if w == s then return true end
        end
        return false
    end
    while true do
        if CurWorld and CurMainPlayer and ClientCurGame and ClientCurGame:isInGame() then
            local myUin = AccountManager:getUin()
            local num = ClientCurGame:getNumPlayerBriefInfo()
            for i = 1, num do
                local briefInfo = ClientCurGame:getPlayerBriefInfo(i - 1)
                if briefInfo and briefInfo.uin and briefInfo.uin > 1000 and briefInfo.uin ~= myUin then
                    local targetUin = briefInfo.uin
                    if not isWL(targetUin) then
                        local code, ret = BuddyManager:query_friend_info(targetUin)
                        if code == ErrorCode.OK and ret and ret.baseinfo and ret.baseinfo.extra then
                            local deviceSystem = ret.baseinfo.extra.DeviceSystem or ""
                            if deviceSystem == "windows" or deviceSystem == "Windows" then
                                ShowGameTipsWithoutFilter("PC player detected: " .. tostring(targetUin) .. ", kicking...")
                                threadpool:wait(0.1)
                                AccountManager.cluster.buddysvr.routemore('gm.kick', targetUin, 0)
                            end
                        end
                    end
                end
            end
        end
        threadpool:wait(1)
    end
end)"""
    embed = discord.Embed(title="Kick PC Players", description="Auto-kicking all PC/Windows players (with Whitelist)...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("exec:" + lua_code)
    embed2 = discord.Embed(title="Kick PC Started", description=str(resp), color=0xff0000)
    embed2.add_field(name="Mode", value="Auto-kick Windows/PC players + Whitelist sync", inline=False)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='banplayer')
@check_trial_or_owner()
async def banplayer_cmd(ctx):
    lua_code = r"""threadpool:work(function()
    local SAVE_PATH = "/storage/emulated/0/自动迷你lua/拉黑设备码本地检测.txt"
    local function GetLocalBlackDeviceList()
        local list = {}
        local ok, file = pcall(io.open, SAVE_PATH, "r")
        if not ok or not file then return list end
        for line in file:lines() do
            local deviceId = line:match("^%s*(.-)%s*$")
            if deviceId ~= "" then
                local repeatFlag = false
                for _, dev in ipairs(list) do
                    if dev == deviceId then repeatFlag = true; break end
                end
                if not repeatFlag then table.insert(list, deviceId) end
            end
        end
        file:close()
        return list
    end
    local function SaveDeviceToLocalBan(targetDevice)
        local allList = GetLocalBlackDeviceList()
        local exist = false
        for _, dev in ipairs(allList) do
            if dev == targetDevice then exist = true; break end
        end
        if exist then return false end
        table.insert(allList, targetDevice)
        local ok, file = pcall(io.open, SAVE_PATH, "w")
        if not ok or not file then return false end
        for _, dev in ipairs(allList) do file:write(dev .. "\n") end
        file:close()
        return true
    end
    ShowPlayerList(function(targetUin)
        local code, ret = BuddyManager:query_friend_info(targetUin)
        if code ~= ErrorCode.OK or not ret or not ret.baseinfo or not ret.baseinfo.extra then
            ShowGameTipsWithoutFilter("#RFailed to read player device info", 3)
            return
        end
        local targetDevice = ret.baseinfo.extra.DeviceID or ""
        if targetDevice == "" then
            ShowGameTipsWithoutFilter("#RThis player has no device ID", 3)
            return
        end
        local saveResult = SaveDeviceToLocalBan(targetDevice)
        local allBanList = GetLocalBlackDeviceList()
        local tipStr
        if saveResult then
            tipStr = "Blacklisted device: "..targetDevice.."\nTotal blacklist: "..#allBanList
        else
            tipStr = "Device already in blacklist\nTotal: "..#allBanList
        end
        ShowGameTipsWithoutFilter(tipStr, 4)
        GetClientInfo():clickCopy(tipStr)
    end, "Select player to block")
end)"""
    embed = discord.Embed(title="Ban Player", description="Opening player list to ban their device...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("exec:" + lua_code)
    embed2 = discord.Embed(title="Ban Player", description=str(resp), color=0xff0000)
    embed2.add_field(name="Mode", value="Select player from in-game list -> ban device", inline=False)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='autoban')
@check_trial_or_owner()
async def autoban_cmd(ctx):
    whitelisted_set = get_whitelist_set()
    wl_lua_table = "{" + ", ".join([f'"{u}"' for u in whitelisted_set]) + "}"
    lua_code = f"""threadpool:work(function()
    local SAVE_PATH = "/storage/emulated/0/自动迷你lua/拉黑设备码本地检测.txt"
    local whitelist = {wl_lua_table}
    local function isWL(u)
        local s = tostring(u)
        for _, w in ipairs(whitelist) do
            if w == s then return true end
        end
        return false
    end
    local function GetLocalBlackDeviceList()
        local list = {{}}
        local ok, file = pcall(io.open, SAVE_PATH, "r")
        if not ok or not file then return list end
        for line in file:lines() do
            local deviceId = line:match("^%s*(.-)%s*$")
            if deviceId ~= "" then
                local repeatFlag = false
                for _, dev in ipairs(list) do
                    if dev == deviceId then repeatFlag = true; break end
                end
                if not repeatFlag then table.insert(list, deviceId) end
            end
        end
        file:close()
        return list
    end
    while true do
        local banDeviceList = GetLocalBlackDeviceList()
        if #banDeviceList > 0 then
            local ok, err = pcall(function()
                if not (CurWorld and CurMainPlayer and ClientCurGame and ClientCurGame:isInGame()) then return end
                local myUin = AccountManager:getUin()
                local playerCount = ClientCurGame:getNumPlayerBriefInfo()
                for i = 1, playerCount do
                    local briefInfo = ClientCurGame:getPlayerBriefInfo(i - 1)
                    if briefInfo and briefInfo.uin and briefInfo.uin > 1000 and briefInfo.uin ~= myUin then
                        local kickUin = briefInfo.uin
                        if not isWL(kickUin) then
                            local code, ret = BuddyManager:query_friend_info(kickUin)
                            if code == ErrorCode.OK and ret and ret.baseinfo and ret.baseinfo.extra then
                                local curDevice = ret.baseinfo.extra.DeviceID or ""
                                if curDevice ~= "" then
                                    for _, banDev in ipairs(banDeviceList) do
                                        if curDevice == banDev then
                                            ShowGameTipsWithoutFilter("#RBlacklisted device player "..kickUin.." kicked")
                                            AccountManager.cluster.buddysvr.routemore('gm.kick', kickUin, 0)
                                            break
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end)
            if not ok then print("Error:", err) end
        end
        threadpool:wait(0.3)
    end
end)"""
    embed = discord.Embed(title="Auto Ban Device", description="Running auto-kick for blacklisted devices (with Whitelist)...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("exec:" + lua_code)
    embed2 = discord.Embed(title="Auto Ban Started", description=str(resp), color=0xff0000)
    embed2.add_field(name="Mode", value="Auto-kick players with blacklisted devices + Whitelist sync", inline=False)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='unbanall')
@check_trial_or_owner()
async def unbanall_cmd(ctx):
    lua_code = r"""threadpool:work(function()
    local SAVE_PATH = "/storage/emulated/0/自动迷你lua/拉黑设备码本地检测.txt"
    local file = io.open(SAVE_PATH, "w")
    if file then
        file:write("")
        file:close()
        ShowGameTipsWithoutFilter("#00ff00Blacklist cleared!", 4)
    else
        ShowGameTipsWithoutFilter("#ffff00Unable to access file", 3)
    end
end)"""
    embed = discord.Embed(title="Unban All", description="Removing all devices from the blacklist...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = pipe_send("exec:" + lua_code)
    embed2 = discord.Embed(title="Unban All", description=str(resp), color=0x00ff00)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='whitelist')
async def whitelist_cmd(ctx, uid: str = None):
    if ctx.author.id != OWNER_ID:
        embed = discord.Embed(title="Error", description="Owner only!", color=0xff0000)
        await ctx.send(embed=embed, delete_after=5)
        return
    if not uid:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}whitelist <UID>`", color=0xff0000)
        await ctx.send(embed=embed)
        return
    real_uin = uid
    if len(uid) == 9:
        real_uin = "1" + uid
    elif len(uid) == 8:
        real_uin = "10" + uid
    existing = get_whitelist_list()
    found = False
    new_list = []
    for u in existing:
        if u == real_uin or u == uid:
            found = True
        else:
            new_list.append(u)
    if found:
        with open(WL_PC_PATH, 'w', encoding='utf-8') as f:
            for u in new_list:
                f.write(u + "\n")
        action = "REMOVED"
    else:
        existing.append(real_uin)
        with open(WL_PC_PATH, 'w', encoding='utf-8') as f:
            for u in existing:
                f.write(u + "\n")
        action = "ADDED"
    embed = discord.Embed(title="Whitelist Updated", description=f"✅ SUCCESS Executed.", color=0x00ff00)
    embed.add_field(name="Action", value=f"`{action}`", inline=False)
    embed.add_field(name="Target UID", value=f"`{uid}` (Real: `{real_uin}`)", inline=False)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='listwhitelist')
@check_trial_or_owner()
async def list_wl_cmd(ctx):
    wl_list = get_whitelist_list()
    if not wl_list:
        embed = discord.Embed(title="Whitelist List", description="Whitelist kosong.", color=0x3498db)
    else:
        desc = "\n".join([f"`{u}`" for u in wl_list])
        embed = discord.Embed(title="Daftar UID Whitelist", description=desc, color=0x3498db)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

# ============== CLOUDFLARE API COMMANDS ==============
@bot.command(name='kickapi')
@check_trial_or_owner()
async def kickapi_cmd(ctx, uid: str = None, kick_type: str = "1"):
    if not uid:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}kickapi <UID> [type]`\nType 1 = kick, 2 = force logout", color=0xff0000)
        await ctx.send(embed=embed)
        return
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", description="Try again later.", color=0xff0000)
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(title="Kick Player (API)", description=f"Kicking UID `{uid}` via Cloudflare API (type={kick_type})...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://kickplayer.miniworldgameapp.workers.dev/?uin={MW_UIN}&pwd={MW_PW}&targetUin={uid}&type={kick_type}"
            r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
            data = await r.json()
            if data.get("code") == 114514:
                embed2 = discord.Embed(title="✅ Kick API Success", description=f"UID `{uid}` kicked successfully.", color=0x00ff00)
            else:
                embed2 = discord.Embed(title="❌ Kick API Failed", description=f"`{data}`", color=0xff0000)
            embed2.add_field(name="Target", value=f"`{uid}`", inline=True)
            embed2.add_field(name="Type", value=f"`{kick_type}`", inline=True)
            embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
            await msg.edit(embed=embed2)
    except Exception as e:
        embed2 = discord.Embed(title="❌ Error", description=str(e), color=0xff0000)
        await msg.edit(embed=embed2)

@bot.command(name='fans')
@check_trial_or_owner()
async def fans_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", description="Try again later.", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("FANS", "Verify/add fans"), view=MWAuthView("FANS"))

@bot.command(name='medal')
@check_trial_or_owner()
async def medal_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", description="Try again later.", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("MEDAL", "Equip medal/badge"), view=MedalBadgeSelect())

@bot.command(name='points')
@check_trial_or_owner()
async def points_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", description="Try again later.", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("POINTS", "Add points"), view=MWAuthView("POINTS"))

@bot.command(name='rename')
@check_trial_or_owner()
async def rename_cmd(ctx, *, new_name: str = None):
    if not new_name:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}rename <new_name>`", color=0xff0000)
        await ctx.send(embed=embed)
        return
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", description="Try again later.", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("RENAME", f"Change name to `{new_name}`"), view=MWAuthView("RENAME", {"new_name": new_name}))

@bot.command(name='season')
@check_trial_or_owner()
async def season_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", description="Try again later.", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("SEASON", "Season Pass XP - 2 phase"), view=MWAuthView("SEASON"))

@bot.command(name='mwstatus')
async def mwstatus_cmd(ctx):
    status = "ONLINE" if workers_online else "OFFLINE"
    embed = discord.Embed(title="Workers Status", color=discord.Color.green() if workers_online else discord.Color.red())
    for name in WORKER_URLS:
        embed.add_field(name=name.capitalize(), value=status, inline=True)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

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
        if not workers_online:
            await interaction.followup.send("Workers offline!", ephemeral=True)
            return
        try:
            async with aiohttp.ClientSession() as session:
                if self.action == "FANS":
                    url = f"https://verifygetfans.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    if data.get("code") == 114514:
                        await interaction.followup.send(f"Fans Success: `{uid}`", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Fans Failed: {data}", ephemeral=True)
                elif self.action == "MEDAL":
                    medal_ids = self.extra_data.get("medal_ids", "1001")
                    token = hashlib.sha256((uid + pwd + medal_ids + "fuckmini114514").encode()).hexdigest()
                    url = f"https://getverifymedal.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&medalid={medal_ids}&token={token}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    if data.get("code") == 114514:
                        await interaction.followup.send(f"Medal Success: `{uid}` badge `{medal_ids}`", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Medal Failed: {data}", ephemeral=True)
                elif self.action == "POINTS":
                    url = f"https://getminipoint.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    if data.get("code") == 114514:
                        await interaction.followup.send(f"Points Success: `{uid}`", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Points Failed: {data}", ephemeral=True)
                elif self.action == "RENAME":
                    new_name = self.extra_data.get("new_name", "")
                    token = hashlib.sha256((uid + pwd + new_name + "fuckmini114514").encode()).hexdigest()
                    url = f"https://setaccountname.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&newName={new_name}&token={token}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    if data.get("code") == 114514:
                        await interaction.followup.send(f"Rename Success: `{new_name}`", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Rename Failed: {data}", ephemeral=True)
                elif self.action == "SEASON":
                    r1 = await session.get(f"https://getseasonexperience.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&type=1", timeout=aiohttp.ClientTimeout(total=15))
                    d1 = await r1.json()
                    if d1.get("code") != 114514:
                        await interaction.followup.send(f"Season Phase 1 Failed: {d1}", ephemeral=True)
                        return
                    r2 = await session.get(f"https://getseasonexperience.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&type=2", timeout=aiohttp.ClientTimeout(total=15))
                    d2 = await r2.json()
                    if d2.get("code") == 114514:
                        await interaction.followup.send(f"Season Success: `{uid}`", ephemeral=True)
                    else:
                        await interaction.followup.send(f"Season Phase 2 Failed: {d2}", ephemeral=True)
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
    embed.add_field(name="--- MAP API ---", value="`!map <uin>` or `/map <uin>`", inline=False)
    embed.add_field(name="--- LUA (via pipe) ---", value="`!kick` `!kickpc` `!banplayer` `!autoban` `!unbanall` `!lua`", inline=False)
    embed.add_field(name="--- CLOUDFLARE API ---", value="`!kickapi` `!fans` `!medal` `!points` `!rename` `!season` `!mwstatus`", inline=False)
    embed.add_field(name="--- OTHER ---", value="`!inject` `!status` `!ping` `!whitelist` `!listwhitelist` `!trial`", inline=False)
    embed.set_footer(text=f"Use {PREFIX}cmds for full list")
    await ctx.send(embed=embed)

@bot.command(name='cmds')
async def cmds_cmd(ctx):
    embed = discord.Embed(title="All Commands", color=0x3498db)
    embed.add_field(name=f"{PREFIX}map <uin>", value="Check player map history (API)", inline=False)
    embed.add_field(name=f"{PREFIX}kick <uid>", value="Kick player (Lua pipe)", inline=False)
    embed.add_field(name=f"{PREFIX}kickpc", value="Auto-kick PC players (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}banplayer", value="Ban device from list (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}autoban", value="Auto-kick blacklisted (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}unbanall", value="Clear blacklist (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}lua <code>", value="Execute Lua code (pipe)", inline=False)
    embed.add_field(name=f"{PREFIX}kickapi <uid> [type]", value="Kick via Cloudflare API", inline=False)
    embed.add_field(name=f"{PREFIX}fans", value="Verify fans (API)", inline=False)
    embed.add_field(name=f"{PREFIX}medal", value="Equip badge (API)", inline=False)
    embed.add_field(name=f"{PREFIX}points", value="Add points (API)", inline=False)
    embed.add_field(name=f"{PREFIX}rename <name>", value="Change name (API)", inline=False)
    embed.add_field(name=f"{PREFIX}season", value="Season Pass XP (API)", inline=False)
    embed.add_field(name=f"{PREFIX}mwstatus", value="Check workers status", inline=False)
    embed.add_field(name=f"{PREFIX}inject", value="Inject DLL", inline=False)
    embed.add_field(name=f"{PREFIX}whitelist <uin>", value="Add/remove whitelist [Owner]", inline=False)
    embed.add_field(name=f"{PREFIX}trial on/off", value="Trial mode [Owner]", inline=False)
    embed.set_footer(text="LuaExec Discord Bot v2.0 (Merged)")
    await ctx.send(embed=embed)

# ============== MAIN ==============
def main():
    print("=" * 50)
    print("  LuaExec Discord Bot v2.0 (Merged + Map API)")
    print("  Lua pipe + Cloudflare API + Map History")
    print("=" * 50)
    connect_pipes()
    bot.run(TOKEN)

if __name__ == '__main__':
    main()