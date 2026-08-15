import sys, os, time, subprocess
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

import win32file
import win32pipe
import pywintypes
import psutil

# ============== KONFIGURASI ==============
PIPE_CMD_NAME  = r'\\.\pipe\luaexec_discord_cmd'
PIPE_RESP_NAME = r'\\.\pipe\luaexec_discord_resp'
LUAEXEC_PIPE   = os.environ['LUAEXEC_PIPE']
SECRET_KEY     = os.environ['SECRET_KEY']
PROCESS_NAME   = 'MiniGameApp.exe'
INJECT_EXE     = os.environ['INJECT_EXE']
INJECT_DLL     = os.environ['INJECT_DLL']
# ==========================================

def send_to_game(code):
    handle = None
    try:
        handle = win32file.CreateFile(
            LUAEXEC_PIPE,
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0, None, win32file.OPEN_EXISTING, 0, None
        )
        full_msg = SECRET_KEY + code
        win32file.WriteFile(handle, full_msg.encode('utf-8'))
        return True, "OK"
    except Exception as e:
        return False, str(e)
    finally:
        if handle:
            try:
                win32file.CloseHandle(handle)
            except:
                pass

def inject_dll():
    found_pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == PROCESS_NAME.lower():
                found_pid = proc.info['pid']
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if found_pid is None:
        return False, "MiniGameApp.exe tidak ditemukan!"

    try:
        subprocess.run(
            [INJECT_EXE, str(found_pid), INJECT_DLL],
            capture_output=True, text=True, timeout=10
        )
        return True, f"Injected ke PID: {found_pid}"
    except Exception as e:
        return False, f"Gagal inject: {e}"

def check_status():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == PROCESS_NAME.lower():
                return True, f"Game berjalan (PID: {proc.info['pid']})"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False, "Game tidak berjalan."

def make_pipe(name):
    sa = pywintypes.SECURITY_ATTRIBUTES()
    handle = win32pipe.CreateNamedPipe(
        name,
        win32pipe.PIPE_ACCESS_DUPLEX,
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
        1, 65536, 65536, 0, sa
    )
    return handle

def main():
    print("=" * 50)
    print("  LuaExec Discord Bridge v1.0")
    print("=" * 50)

    cmd_pipe  = make_pipe(PIPE_CMD_NAME)
    resp_pipe = make_pipe(PIPE_RESP_NAME)
    print(f"[OK] Pipe CMD  : {PIPE_CMD_NAME}")
    print(f"[OK] Pipe RESP : {PIPE_RESP_NAME}")

    print("[WAIT] Menunggu Discord bot connect ke CMD pipe...")
    win32pipe.ConnectNamedPipe(cmd_pipe, None)
    print("[OK] CMD pipe connected!")

    print("[WAIT] Menunggu Discord bot connect ke RESP pipe...")
    win32pipe.ConnectNamedPipe(resp_pipe, None)
    print("[OK] RESP pipe connected!")

    print("\n[BREADY] Bridge siap! Menunggu perintah...\n")

    while True:
        try:
            hr, data = win32file.ReadFile(cmd_pipe, 65536)
            msg = data.decode('utf-8').strip()

            if msg.startswith("exec:"):
                code = msg[5:]
                print(f"[EXEC] {code[:80]}...")
                ok, result = send_to_game(code)
                resp = "✅: SUCCES Executed." if ok else f"ERROR: {result}"
                win32file.WriteFile(resp_pipe, resp.encode('utf-8'))
                print(f"[RESP] {resp}")

            elif msg == "inject":
                print("[INJECT] Running inject...")
                ok, result = inject_dll()
                win32file.WriteFile(resp_pipe, result.encode('utf-8'))
                print(f"[RESP] {result}")

            elif msg == "status":
                ok, result = check_status()
                win32file.WriteFile(resp_pipe, result.encode('utf-8'))
                print(f"[RESP] {result}")

            elif msg == "ping":
                win32file.WriteFile(resp_pipe, "Pong! Bridge aktif.".encode('utf-8'))

            else:
                win32file.WriteFile(resp_pipe, f"Unknown: {msg}".encode('utf-8'))

        except pywintypes.error as e:
            if e.args[0] == 109:
                print("[DISCONNECT] Bot disconnected, waiting reconnect...")
                try:
                    win32pipe.DisconnectNamedPipe(cmd_pipe)
                    win32pipe.DisconnectNamedPipe(resp_pipe)
                    win32pipe.ConnectNamedPipe(cmd_pipe, None)
                    win32pipe.ConnectNamedPipe(resp_pipe, None)
                    print("[OK] Reconnected!")
                except:
                    break
            else:
                print(f"[ERR] {e}")
        except Exception as e:
            print(f"[ERR] {e}")
            time.sleep(0.1)

    print("[EXIT] Bridge stopped.")

if __name__ == '__main__':
    main()
