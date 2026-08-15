import sys, os, time, subprocess, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

import win32file
import win32pipe
import pywintypes
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============== KONFIGURASI ==============
LUAEXEC_PIPE   = os.environ['LUAEXEC_PIPE']
SECRET_KEY     = os.environ['SECRET_KEY']
PROCESS_NAME   = 'MiniGameApp.exe'
INJECT_EXE     = os.environ['INJECT_EXE']
INJECT_DLL     = os.environ['INJECT_DLL']
HTTP_PORT      = 18234
AUTH_TOKEN     = os.environ['AUTH_TOKEN']
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
        return False, "MiniGameApp.exe not found!"
    try:
        subprocess.run([INJECT_EXE, str(found_pid), INJECT_DLL], capture_output=True, text=True, timeout=10)
        return True, f"Injected to PID: {found_pid}"
    except Exception as e:
        return False, f"Inject failed: {e}"

def check_status():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() == PROCESS_NAME.lower():
                return True, f"Game running (PID: {proc.info['pid']})"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False, "Game not running."

class BridgeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")

    def do_POST(self):
        auth = self.headers.get('Authorization', '')
        if auth != f'Bearer {AUTH_TOKEN}':
            self.send_response(401)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
            return

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON"}).encode())
            return

        action = data.get('action', '')
        result = {}

        if action == 'exec':
            code = data.get('code', '')
            print(f"[EXEC] {code[:80]}...")
            ok, res = send_to_game(code)
            result = {"success": ok, "message": "✅ Executed" if ok else f"ERROR: {res}"}

        elif action == 'inject':
            print("[INJECT] Running...")
            ok, res = inject_dll()
            result = {"success": ok, "message": res}

        elif action == 'status':
            ok, res = check_status()
            result = {"success": ok, "message": res}

        elif action == 'ping':
            result = {"success": True, "message": "Pong! Bridge active."}

        else:
            result = {"success": False, "message": f"Unknown action: {action}"}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)
            self.end_headers()

def main():
    print("=" * 50)
    print("  LuaExec Bridge Server v1.0")
    print(f"  HTTP Port: {HTTP_PORT}")
    print("=" * 50)

    server = HTTPServer(('0.0.0.0', HTTP_PORT), BridgeHandler)
    print(f"[OK] Server running on port {HTTP_PORT}")
    print(f"[OK] Auth token: {AUTH_TOKEN}")
    print("[WAIT] Waiting for commands from Railway bot...\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[EXIT] Server stopped.")
        server.server_close()

if __name__ == '__main__':
    main()
