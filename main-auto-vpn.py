import asyncio
from curl_cffi.requests import AsyncSession
import json
import base64
import time
import sys
import os
import subprocess
import random
import requests
import signal
from datetime import datetime, timedelta, timezone

# --- [極致霓虹配色] ---
class C:
    E, R, G, Y, B, M, C, W = '\033[0m', '\033[91m', '\033[92m', '\033[93m', '\033[94m', '\033[95m', '\033[96m', '\033[97m'
    BOLD = '\033[1m'
    SUCCESS_ICON, FAIL_ICON = f"{BOLD}{G}✔{E}", f"{BOLD}{R}✘{E}"
    SPEED_ICON, TIME_ICON, GEM_ICON = f"{BOLD}{C}⚡{E}", f"{BOLD}{Y}⏰{E}", f"{BOLD}{M}🟣{E}"

# --- [1] 設定區域 ---
BOT_ID = os.environ.get("BOT_ID", "1")
VPN_USER = os.environ.get("VPN_USER", "aFwROLMWIY5ljknZ") 
VPN_PASS = os.environ.get("VPN_PASS", "XlNXBom0tFVNFp3GNH58xDJASRoxOr8m")
DEFAULT_TOKEN = os.environ.get("DUO_TOKEN", "")
LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "") 
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

IS_WINDOWS = sys.platform == 'win32'
CONFIG_DIR = "./vpn_configs"

if IS_WINDOWS: OPENVPN_CMD = [r"C:\Program Files\OpenVPN\bin\openvpn.exe"]
else: OPENVPN_CMD = ["sudo", "openvpn"]

# ⚠️ 確認 MAGIC ID
MAGIC_ID = "SKILL_COMPLETION_BALANCED-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-1-GEMS"

# ==========================================
# ☠️ 神風特攻模式 (Kamikaze Mode)
# ==========================================
DEFAULT_THREADS = 40    # 暴力多開
DEFAULT_BATCH = 100     # 單次最大搬運
DEFAULT_DELAY = 0       # 0秒延遲
NOTIFY_INTERVAL = 300   # 5分鐘報告

class DuoGemNuclear:
    def __init__(self, token, reward_id):
        self.token = token
        self.reward_id = reward_id
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        }
        self.base_url = "https://www.duolingo.com/2017-06-30/users"
        self.sub = self._decode_jwt(token)
        self.stats = {'success': 0, 'failed': 0}
        self.is_running = True
        self.start_time = 0
        self.initial_gems = 0
        self.avg_gems_per_hit = 15.0
        self.vpn_lock = asyncio.Lock()
        self.last_notify_time = 0 
        
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        self.config_files = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.ovpn')]

    def _decode_jwt(self, token):
        try:
            payload = token.split(".")[1] + "=="
            return json.loads(base64.urlsafe_b64decode(payload))['sub']
        except: return "Unknown"

    def send_telegram(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        msg_with_id = f"🤖 [神風 #{BOT_ID}]\n{message}"
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg_with_id}
            requests.post(url, json=data, timeout=5)
        except: pass

    # 🟢 [關鍵修正] 改用 os._exit(1) 強制拔插頭
    async def suicide_restart(self):
        print(f"\n{C.R}💀 偵測到封鎖 (429)！執行戰術重啟...{C.E}")
        if IS_WINDOWS: subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else: subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        
        # 👇 這裡改了！強制結束進程，不讓 except 攔截
        os._exit(1) 

    # 🟢 每次啟動都換一個新 VPN
    async def connect_random_vpn(self):
        if not self.config_files: os._exit(1) # 沒檔也直接殺
        config_name = random.choice(self.config_files)
        print(f"{C.M}🛡️ [戰術突擊] 載入新節點: {config_name}...{C.E}")

        if IS_WINDOWS: subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else: subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        await asyncio.sleep(1)
        
        with open("vpn_auth.txt", "w") as f: f.write(f"{VPN_USER}\n{VPN_PASS}")
        cmd = OPENVPN_CMD + ["--config", f"{CONFIG_DIR}/{config_name}", "--auth-user-pass", "vpn_auth.txt"]
        if not IS_WINDOWS: cmd.append("--daemon")
        subprocess.Popen(cmd, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(f"\n{C.G}✅ VPN 部署中 (直接開火)...{C.E}")
        await asyncio.sleep(5) 

    async def fetch_user_data(self, session):
        try:
            resp = await session.get(f"{self.base_url}/{self.sub}?fields=gems", headers=self.headers, timeout=5)
            if resp.status_code == 200:
                gems = resp.json().get('gems', 0)
                if self.initial_gems == 0: self.initial_gems = gems
                return True
            else:
                await self.suicide_restart()
                return False
        except:
            await self.suicide_restart()
        return False

    async def _send_patch(self, session, url, payload):
        try:
            if self.vpn_lock.locked(): return
            resp = await session.patch(url, headers=self.headers, json=payload, timeout=5)
            if 200 <= resp.status_code < 300: self.stats['success'] += 1
            else: await self.suicide_restart() 
        except: await self.suicide_restart()

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        while self.is_running:
            tasks = [self._send_patch(session, url, payload) for _ in range(batch)]
            await asyncio.gather(*tasks)
            if delay > 0: await asyncio.sleep(delay)

    async def monitor_loop(self, session):
        self.start_time = time.time()
        self.last_notify_time = time.time()
        while self.is_running:
            elapsed = time.time() - self.start_time
            speed = self.stats['success'] / elapsed if elapsed > 0 else 0
            est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
            
            if time.time() - self.last_notify_time > NOTIFY_INTERVAL:
                msg = f"🔥 [戰況] 激戰中\n💰 掠奪: +{est_gained}\n⚡ 速度: {speed:.1f}/s"
                self.send_telegram(msg)
                self.last_notify_time = time.time()

            sys.stdout.write(f"\r{C.SPEED_ICON} {speed:.1f}/s {C.SUCCESS_ICON} {self.stats['success']} {C.Y}💰 +{est_gained}{C.E}    ")
            sys.stdout.flush()
            await asyncio.sleep(1)

    async def start(self):
        await self.connect_random_vpn()
        try:
            async with AsyncSession(impersonate="chrome120") as session:
                if await self.fetch_user_data(session):
                    payload = {"consumed": True, "fromLanguage": "en", "learningLanguage": "es"} 
                    tasks = [asyncio.create_task(self.monitor_loop(session))]
                    for i in range(DEFAULT_THREADS):
                        tasks.append(asyncio.create_task(self.attack_worker(i, session, payload, DEFAULT_BATCH, DEFAULT_DELAY)))
                    try: await asyncio.gather(*tasks)
                    except: pass
        finally:
            print(f"\n🛑 墜機")

if __name__ == "__main__":
    token = DEFAULT_TOKEN
    try: 
        bot = DuoGemNuclear(token, MAGIC_ID)
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
