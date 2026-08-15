import sys, os, time, json, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands
import aiohttp

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

TOKEN = os.environ.get('DISCORD_TOKEN', '')
PREFIX = os.environ.get('PREFIX', '!')
BRIDGE_URL = os.environ.get('BRIDGE_URL', '')
BRIDGE_TOKEN = os.environ.get('AUTH_TOKEN', 'mwbot_secret_2024')
MW_UIN = os.environ.get('MINI_UIN', '320807253')
MW_PW = os.environ.get('MINI_PW', 'Daxter12345GG')

if not TOKEN:
    print("[!] Set DISCORD_TOKEN environment variable!")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

trial_mode = False
workers_online = False

# ============== BRIDGE COMMUNICATION ==============
async def bridge_send(action, code=""):
    if not BRIDGE_URL:
        return {"success": False, "message": "Bridge URL not configured!"}
    try:
        async with aiohttp.ClientSession() as session:
            data = {"action": action, "code": code}
            headers = {"Authorization": f"Bearer {BRIDGE_TOKEN}", "Content-Type": "application/json"}
            async with session.post(BRIDGE_URL, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                return await resp.json()
    except Exception as e:
        return {"success": False, "message": f"Bridge error: {str(e)}"}

async def check_workers():
    global workers_online
    try:
        async with aiohttp.ClientSession() as session:
            r = await session.get(WORKER_URLS["points"], timeout=aiohttp.ClientTimeout(total=10))
            text = await r.text()
            workers_online = "error" in text.lower() or "code" in text.lower() or "114514" in text
    except:
        workers_online = False

from discord.ext import tasks
@tasks.loop(minutes=5)
async def health_loop():
    await check_workers()

def MW_WARNING_embed(action, description):
    embed = discord.Embed(title=f"WARNING: USE {action} BUG", description=f"**WARNING**\n\nUSING THIS FEATURE MAY TRIGGER **PERMANENT BAN**.\nWE ARE NOT RESPONSIBLE.\n\nFeature: **{action}** - {description}", color=discord.Color.red())
    embed.set_footer(text="Mini World: CREATA | Use at your own risk")
    return embed

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

@bot.event
async def on_ready():
    print(f"[OK] Bot online: {bot.user}")
    print(f"     Bridge: {BRIDGE_URL or 'LOCAL MODE'}")
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}cmds"), status=discord.Status.dnd)
    await check_workers()
    if not health_loop.is_running():
        health_loop.start()

# ============== LUA COMMANDS (via bridge) ==============
@bot.command(name='trial')
async def trial_cmd(ctx, status: str = None):
    global trial_mode
    if ctx.author.id != OWNER_ID:
        await ctx.send("Owner only!", delete_after=5)
        return
    if not status or status.lower() not in ['on', 'off']:
        await ctx.send(f"Usage: `{PREFIX}trial on/off`")
        return
    trial_mode = status.lower() == 'on'
    await bot.change_presence(activity=discord.Game(name=f"{PREFIX}cmds | Trial: {'ON' if trial_mode else 'OFF'}"), status=discord.Status.dnd)
    embed = discord.Embed(title="Trial Mode", description=f"**{'ON**' if trial_mode else 'OFF**'}", color=0x00ff00 if trial_mode else 0xff0000)
    await ctx.send(embed=embed)

@bot.command(name='ping')
@check_trial_or_owner()
async def ping_cmd(ctx):
    resp = await bridge_send("ping")
    embed = discord.Embed(title="Pong!", description=str(resp.get('message', resp)), color=0x00ff00)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='inject')
@check_trial_or_owner()
async def inject_cmd(ctx):
    embed = discord.Embed(title="Injecting...", description="Injecting DLL into the game...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("inject")
    embed2 = discord.Embed(title="Inject Result", description=str(resp.get('message', resp)), color=0x00ff00 if resp.get('success') else 0xff0000)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='status')
@check_trial_or_owner()
async def status_cmd(ctx):
    resp = await bridge_send("status")
    embed = discord.Embed(title="Game Status", description=str(resp.get('message', resp)), color=0x3498db)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='lua')
@check_trial_or_owner()
async def lua_cmd(ctx, *, code: str):
    embed = discord.Embed(title="Executing...", description=code[:100], color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("exec", code)
    msg_text = str(resp.get('message', resp))
    if len(msg_text) > 1900:
        msg_text = msg_text[:1900] + "..."
    embed2 = discord.Embed(title="Lua Executed", description=msg_text, color=0x00ff00 if resp.get('success') else 0xff0000)
    embed2.add_field(name="Code", value=code[:200], inline=False)
    embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await msg.edit(embed=embed2)

@bot.command(name='kick')
@check_trial_or_owner()
async def kick_lua_cmd(ctx, uid: str = None):
    if not uid:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}kick <UID>`", color=0xff0000)
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
        embed = discord.Embed(title="Kick Aborted", description=f"UID `{uid}` (Real: `{real_uin}`) is in **Whitelist**!", color=0xff0000)
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

    embed = discord.Embed(title="Kick Player (Lua)", description=f"Kicking UID `{uid}` (Real: `{real_uin}`)...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("exec", lua_code)
    embed2 = discord.Embed(title="Kick Result", description=f"✅ Kick sent for UID {uid} > {real_uin}", color=0x00ff00)
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
                                ShowGameTipsWithoutFilter("PC player: " .. tostring(targetUin) .. ", kicking...")
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
    embed = discord.Embed(title="Kick PC Players", description="Auto-kicking PC/Windows players...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("exec", lua_code)
    embed2 = discord.Embed(title="Kick PC Started", description=str(resp.get('message', resp)), color=0xff0000)
    embed2.add_field(name="Mode", value="Auto-kick Windows/PC + Whitelist", inline=False)
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
            ShowGameTipsWithoutFilter("#RFailed to read device info", 3)
            return
        end
        local targetDevice = ret.baseinfo.extra.DeviceID or ""
        if targetDevice == "" then
            ShowGameTipsWithoutFilter("#RNo device ID", 3)
            return
        end
        local saveResult = SaveDeviceToLocalBan(targetDevice)
        local allBanList = GetLocalBlackDeviceList()
        local tipStr
        if saveResult then
            tipStr = "Blacklisted: "..targetDevice.."\nTotal: "..#allBanList
        else
            tipStr = "Already in blacklist\nTotal: "..#allBanList
        end
        ShowGameTipsWithoutFilter(tipStr, 4)
        GetClientInfo():clickCopy(tipStr)
    end, "Select player to block")
end)"""
    embed = discord.Embed(title="Ban Player", description="Opening player list to ban device...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("exec", lua_code)
    embed2 = discord.Embed(title="Ban Player", description=str(resp.get('message', resp)), color=0xff0000)
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
            pcall(function()
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
                                            ShowGameTipsWithoutFilter("#RBlacklisted: "..kickUin.." kicked")
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
        end
        threadpool:wait(0.3)
    end
end)"""
    embed = discord.Embed(title="Auto Ban Device", description="Auto-kick blacklisted devices...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("exec", lua_code)
    embed2 = discord.Embed(title="Auto Ban Started", description=str(resp.get('message', resp)), color=0xff0000)
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
        ShowGameTipsWithoutFilter("#ffff00Cannot access file", 3)
    end
end)"""
    embed = discord.Embed(title="Unban All", description="Clearing blacklist...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    resp = await bridge_send("exec", lua_code)
    embed2 = discord.Embed(title="Unban All", description=str(resp.get('message', resp)), color=0x00ff00)
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
    embed = discord.Embed(title="Whitelist Updated", color=0x00ff00)
    embed.add_field(name="Action", value=f"`{action}`", inline=False)
    embed.add_field(name="Target", value=f"`{uid}` (Real: `{real_uin}`)", inline=False)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

@bot.command(name='listwhitelist')
@check_trial_or_owner()
async def list_wl_cmd(ctx):
    wl_list = get_whitelist_list()
    if not wl_list:
        embed = discord.Embed(title="Whitelist", description="Kosong.", color=0x3498db)
    else:
        desc = "\n".join([f"`{u}`" for u in wl_list])
        embed = discord.Embed(title="Whitelist", description=desc, color=0x3498db)
    embed.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
    await ctx.send(embed=embed)

# ============== CLOUDFLARE API COMMANDS ==============
@bot.command(name='kickapi')
@check_trial_or_owner()
async def kickapi_cmd(ctx, uid: str = None, kick_type: str = "1"):
    if not uid:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}kickapi <UID> [type]`", color=0xff0000)
        await ctx.send(embed=embed)
        return
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", color=0xff0000)
        await ctx.send(embed=embed)
        return
    embed = discord.Embed(title="Kick (API)", description=f"Kicking UID `{uid}` (type={kick_type})...", color=0xffff00)
    msg = await ctx.send(embed=embed)
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://kickplayer.miniworldgameapp.workers.dev/?uin={MW_UIN}&pwd={MW_PW}&targetUin={uid}&type={kick_type}"
            r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
            data = await r.json()
            if data.get("code") == 114514:
                embed2 = discord.Embed(title="✅ Kick API Success", color=0x00ff00)
                embed2.add_field(name="Target", value=f"`{uid}`", inline=True)
            else:
                embed2 = discord.Embed(title="❌ Kick API Failed", description=f"`{data}`", color=0xff0000)
            embed2.set_footer(text="Requested by " + str(ctx.author), icon_url=ctx.author.display_avatar.url)
            await msg.edit(embed=embed2)
    except Exception as e:
        embed2 = discord.Embed(title="❌ Error", description=str(e), color=0xff0000)
        await msg.edit(embed=embed2)

@bot.command(name='fans')
@check_trial_or_owner()
async def fans_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("FANS", "Verify/add fans"), view=MWAuthView("FANS"))

@bot.command(name='medal')
@check_trial_or_owner()
async def medal_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("MEDAL", "Equip medal/badge"), view=MedalBadgeSelect())

@bot.command(name='points')
@check_trial_or_owner()
async def points_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("POINTS", "Add points"), view=MWAuthView("POINTS"))

@bot.command(name='rename')
@check_trial_or_owner()
async def rename_cmd(ctx, *, new_name: str = None):
    if not new_name:
        embed = discord.Embed(title="Error", description=f"Usage: `{PREFIX}rename <name>`", color=0xff0000)
        await ctx.send(embed=embed)
        return
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("RENAME", f"Change name to `{new_name}`"), view=MWAuthView("RENAME", {"new_name": new_name}))

@bot.command(name='season')
@check_trial_or_owner()
async def season_cmd(ctx):
    if not workers_online:
        embed = discord.Embed(title="Workers Offline", color=0xff0000)
        await ctx.send(embed=embed)
        return
    await ctx.send(embed=MW_WARNING_embed("SEASON", "Season Pass XP"), view=MWAuthView("SEASON"))

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
    uid_input = discord.ui.TextInput(label="UID", placeholder="320807253", required=True)
    pw_input = discord.ui.TextInput(label="Password", required=True)

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
                    emoji = "✅" if data.get("code") == 114514 else "❌"
                    await interaction.followup.send(f"{emoji} Fans: {data}", ephemeral=True)
                elif self.action == "MEDAL":
                    medal_ids = self.extra_data.get("medal_ids", "1001")
                    token = hashlib.sha256((uid + pwd + medal_ids + "fuckmini114514").encode()).hexdigest()
                    url = f"https://getverifymedal.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&medalid={medal_ids}&token={token}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    emoji = "✅" if data.get("code") == 114514 else "❌"
                    await interaction.followup.send(f"{emoji} Medal: {data}", ephemeral=True)
                elif self.action == "POINTS":
                    url = f"https://getminipoint.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    emoji = "✅" if data.get("code") == 114514 else "❌"
                    await interaction.followup.send(f"{emoji} Points: {data}", ephemeral=True)
                elif self.action == "RENAME":
                    new_name = self.extra_data.get("new_name", "")
                    token = hashlib.sha256((uid + pwd + new_name + "fuckmini114514").encode()).hexdigest()
                    url = f"https://setaccountname.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&newName={new_name}&token={token}"
                    r = await session.get(url, timeout=aiohttp.ClientTimeout(total=15))
                    data = await r.json()
                    emoji = "✅" if data.get("code") == 114514 else "❌"
                    await interaction.followup.send(f"{emoji} Rename: {data}", ephemeral=True)
                elif self.action == "SEASON":
                    r1 = await session.get(f"https://getseasonexperience.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&type=1", timeout=aiohttp.ClientTimeout(total=15))
                    d1 = await r1.json()
                    if d1.get("code") != 114514:
                        await interaction.followup.send(f"❌ Season Phase 1 Failed: {d1}", ephemeral=True)
                        return
                    r2 = await session.get(f"https://getseasonexperience.miniworldgameapp.workers.dev/?uin={uid}&pwd={pwd}&type=2", timeout=aiohttp.ClientTimeout(total=15))
                    d2 = await r2.json()
                    emoji = "✅" if d2.get("code") == 114514 else "❌"
                    await interaction.followup.send(f"{emoji} Season: {d2}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)[:200]}", ephemeral=True)

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
        embed = discord.Embed(title="Medal Bug", description="\n".join(f"- {n}" for n in names) + f"\n\nIDs: `{ids_str}`", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=MWAuthView("MEDAL", {"medal_ids": ids_str}))

# ============== MENU ==============
@bot.command(name='menu')
async def menu_cmd(ctx):
    embed = discord.Embed(title="Mini World Bot", color=0x9b59b6)
    embed.add_field(name="LUA COMMANDS", value=f"`{PREFIX}kick` `{PREFIX}kickpc` `{PREFIX}banplayer` `{PREFIX}autoban` `{PREFIX}unbanall` `{PREFIX}lua`", inline=False)
    embed.add_field(name="API COMMANDS", value=f"`{PREFIX}kickapi` `{PREFIX}fans` `{PREFIX}medal` `{PREFIX}points` `{PREFIX}rename` `{PREFIX}season` `{PREFIX}mwstatus`", inline=False)
    embed.add_field(name="OTHER", value=f"`{PREFIX}inject` `{PREFIX}status` `{PREFIX}ping` `{PREFIX}whitelist` `{PREFIX}listwhitelist` `{PREFIX}trial`", inline=False)
    embed.set_footer(text=f"Use {PREFIX}cmds for details")
    await ctx.send(embed=embed)

@bot.command(name='cmds')
async def cmds_cmd(ctx):
    embed = discord.Embed(title="All Commands", color=0x3498db)
    embed.add_field(name=f"{PREFIX}kick <uid>", value="Kick via Lua pipe", inline=False)
    embed.add_field(name=f"{PREFIX}kickapi <uid>", value="Kick via Cloudflare API", inline=False)
    embed.add_field(name=f"{PREFIX}kickpc", value="Auto-kick PC players (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}banplayer", value="Ban device (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}autoban", value="Auto-kick blacklisted (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}unbanall", value="Clear blacklist (Lua)", inline=False)
    embed.add_field(name=f"{PREFIX}lua <code>", value="Execute Lua (pipe)", inline=False)
    embed.add_field(name=f"{PREFIX}fans", value="Verify fans (API)", inline=False)
    embed.add_field(name=f"{PREFIX}medal", value="Equip badge (API)", inline=False)
    embed.add_field(name=f"{PREFIX}points", value="Add points (API)", inline=False)
    embed.add_field(name=f"{PREFIX}rename <name>", value="Change name (API)", inline=False)
    embed.add_field(name=f"{PREFIX}season", value="Season Pass XP (API)", inline=False)
    embed.add_field(name=f"{PREFIX}inject", value="Inject DLL", inline=False)
    embed.add_field(name=f"{PREFIX}whitelist <uid>", value="Whitelist [Owner]", inline=False)
    embed.add_field(name=f"{PREFIX}trial on/off", value="Trial mode [Owner]", inline=False)
    embed.set_footer(text="LuaExec Discord Bot v2.0")
    await ctx.send(embed=embed)

# ============== MAIN ==============
def main():
    print("=" * 50)
    print("  LuaExec Discord Bot v2.0")
    print(f"  Bridge: {BRIDGE_URL or 'LOCAL MODE'}")
    print("=" * 50)
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
