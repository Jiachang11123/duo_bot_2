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

# --- [1] 智慧設定區域 ---
BOT_ID = os.environ.get("BOT_ID", "1")
VPN_USER = os.environ.get("VPN_USER", "aFwROLMWIY5ljknZ") 
VPN_PASS = os.environ.get("VPN_PASS", "XlNXBom0tFVNFp3GNH58xDJASRoxOr8m")
DEFAULT_TOKEN = os.environ.get("DUO_TOKEN", "")

LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "") 
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- [2] 系統路徑判斷 ---
IS_WINDOWS = sys.platform == 'win32'
CONFIG_DIR = "./vpn_configs"

if IS_WINDOWS:
    OPENVPN_CMD = [r"C:\Program Files\OpenVPN\bin\openvpn.exe"]
else:
    OPENVPN_CMD = ["sudo", "openvpn"]

# ⚠️ 請確認這是你的 SKILL ID
MAGIC_ID = "SKILL_COMPLETION_BALANCED-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-1-GEMS"

# ==========================================
# ☠️ 神風特攻模式 (Kamikaze Mode)
# ==========================================
# 說明：移除所有限制，全速轟炸。
DEFAULT_THREADS = 40    # 暴力開到 40 (再高會卡死 VM)
DEFAULT_BATCH = 100     # 單次搬 100 筆
DEFAULT_DELAY = 0       # 0 秒延遲，無間斷攻擊

NOTIFY_INTERVAL = 300   # 5分鐘報告一次 (因為可能撐不到30分鐘)

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

    def send_line(self, message):
        if not LINE_ACCESS_TOKEN or not LINE_USER_ID: return
        msg_with_id = f"🤖 [神風 #{BOT_ID}]\n{message}"
        try:
            url = 'https://api.line.me/v2/bot/message/push'
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
            data = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": msg_with_id}]}
            requests.post(url, headers=headers, json=data, timeout=5)
        except: pass

    def send_telegram(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        msg_with_id = f"🤖 [神風 #{BOT_ID}]\n{message}"
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg_with_id}
            requests.post(url, json=data, timeout=5)
        except: pass

    # 🟢 遇到任何錯誤直接自殺，不嘗試修復
    async def suicide_restart(self):
        print(f"\n{C.R}💀 陣亡 (403/429)！執行重啟...{C.E}")
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else:
            subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        sys.exit(1) # 立即退出

    # 🟢 啟動時隨機連線 VPN
    async def connect_random_vpn(self):
        if not self.config_files:
            print(f"\n{C.R}❌ 沒子彈了 (找不到 .ovpn)！{C.E}")
            sys.exit(1)

        config_name = random.choice(self.config_files)
        print(f"{C.M}🛡️ [戰術突擊] 載入節點: {config_name}...{C.E}")

        if IS_WINDOWS: subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else: subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        
        # 不等待太久，直接殺進去
        await asyncio.sleep(1)
        
        with open("vpn_auth.txt", "w") as f: f.write(f"{VPN_USER}\n{VPN_PASS}")
        
        cmd = OPENVPN_CMD + ["--config", f"{CONFIG_DIR}/{config_name}", "--auth-user-pass", "vpn_auth.txt"]
        if not IS_WINDOWS: cmd.append("--daemon")
        
        subprocess.Popen(cmd, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 縮短連線等待時間 (拚運氣，能連就能刷)
        print(f"\n{C.G}✅ VPN 部署中 (不等了，直接開衝)...{C.E}")
        await asyncio.sleep(5) 

    async def fetch_user_data(self, session):
        try:
            resp = await session.get(f"{self.base_url}/{self.sub}?fields=gems", headers=self.headers, timeout=5)
            if resp.status_code == 200:
                gems = resp.json().get('gems', 0)
                if self.initial_gems == 0: 
                    self.initial_gems = gems
                    # msg = f"🚀 神風小隊出動！\n💎 初始：{gems}"
                    # self.send_telegram(msg)
                return True
            else:
                # 任何錯誤都直接重啟，不囉嗦
                await self.suicide_restart()
                return False
        except:
            await self.suicide_restart()
        return False

    async def _send_patch(self, session, url, payload):
        try:
            if self.vpn_lock.locked(): return
            resp = await session.patch(url, headers=self.headers, json=payload, timeout=5)
            if 200 <= resp.status_code < 300: 
                self.stats['success'] += 1
            else: 
                # 只要不是 200 OK，不管是 429 還是 403 還是 500，全部自殺換 IP
                await self.suicide_restart()
        except: 
            # 連線超時也自殺
            await self.suicide_restart()

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        while self.is_running:
            tasks = [self._send_patch(session, url, payload) for _ in range(batch)]
            await asyncio.gather(*tasks)
            # 延遲是 0，這裡幾乎不等待
            if delay > 0: await asyncio.sleep(delay)

    async def monitor_loop(self, session):
        self.start_time = time.time()
        self.last_notify_time = time.time()
        
        while self.is_running:
            elapsed = time.time() - self.start_time
            speed = self.stats['success'] / elapsed if elapsed > 0 else 0
            current_total_gained = int(self.stats['success'] * self.avg_gems_per_hit)
            
            # 定期通知
            if time.time() - self.last_notify_time > NOTIFY_INTERVAL:
                hours = int(elapsed / 3600)
                msg = (
                    f"🔥 [戰況] 激戰中\n"
                    f"⏱️ 存活: {int(elapsed)}秒\n"
                    f"💰 掠奪: +{current_total_gained}\n"
                    f"⚡ 速度: {speed:.1f}/s"
                )
                self.send_telegram(msg)
                self.last_notify_time = time.time()

            sys.stdout.write(f"\r{C.SPEED_ICON} {speed:.1f}/s {C.SUCCESS_ICON} {self.stats['success']} {C.Y}💰 +{current_total_gained}{C.E}    ")
            sys.stdout.flush()
            await asyncio.sleep(1)

    async def cleanup(self):
        est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
        print(f"\n🛑 墜機 (重啟中...)\n💰 本次獲得：+{est_gained}")

    async def start(self):
        # ❌ 移除所有啟動冷卻，直接開
        # print(f"⏳ 啟動冷卻中...") 
        # await asyncio.sleep(wait_time)
        
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
            await self.cleanup()

if __name__ == "__main__":
    token = DEFAULT_TOKEN
    if "xxxx" in MAGIC_ID or "SKILL_COMPLETION" not in MAGIC_ID:
        print(f"{C.R}⚠️ 警告：請記得修改代碼中的 MAGIC_ID！{C.E}")

    try: 
        bot = DuoGemNuclear(token, MAGIC_ID)
        def signal_handler(sig, frame): bot.is_running = False
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
