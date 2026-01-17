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

# --- [設定區域] ---
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
# 確保指向正確的 OpenVPN 路徑
if IS_WINDOWS:
    OPENVPN_CMD = [r"C:\Program Files\OpenVPN\bin\openvpn.exe"]
else:
    OPENVPN_CMD = ["sudo", "openvpn"]

MAGIC_ID = "SKILL_COMPLETION_BALANCED-…-2-GEMS"
DEFAULT_THREADS = 100
DEFAULT_BATCH = 300
DEFAULT_DELAY = 0.01
NOTIFY_INTERVAL = 60

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
        self.kill_switch_active = False 
        self.start_time = 0
        self.initial_gems = 0
        self.avg_gems_per_hit = 14.0 
        self.last_notify_time = 0 
        
        # 讀取 VPN 設定檔
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
        msg_with_id = f"🤖 [機器人 #{BOT_ID}]\n{message}"
        try:
            url = 'https://api.line.me/v2/bot/message/push'
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
            data = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": msg_with_id}]}
            requests.post(url, headers=headers, json=data)
        except: pass

    def send_telegram(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        msg_with_id = f"🤖 [機器人 #{BOT_ID}]\n{message}"
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg_with_id}
            requests.post(url, json=data)
        except: pass

    def trigger_kill_switch(self, reason):
        if self.kill_switch_active: return
        self.kill_switch_active = True
        self.is_running = False
        print(f"\n{C.R}⛔ {reason} -> 觸發重啟機制{C.E}")
        # 這裡不發通知了，避免洗版，直接自殺讓 YAML 重啟
        os._exit(1)

    def connect_random_vpn(self):
        """啟動時隨機連線一個 VPN"""
        if not self.config_files:
            print(f"{C.R}❌ 錯誤：找不到 VPN 設定檔 (.ovpn){C.E}")
            return # 無檔案則裸奔（不建議）

        # 1. 先殺掉舊的 OpenVPN 進程
        print(f"{C.Y}🧹 清理舊連線...{C.E}")
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else:
            subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        time.sleep(1)

        # 2. 隨機選一個設定檔
        config_name = random.choice(self.config_files)
        print(f"{C.M}🛡️ 正在連線 VPN: {config_name}{C.E}")

        # 3. 建立密碼檔
        with open("vpn_auth.txt", "w") as f: 
            f.write(f"{VPN_USER}\n{VPN_PASS}")
        
        # 4. 啟動
        cmd = OPENVPN_CMD + ["--config", f"{CONFIG_DIR}/{config_name}", "--auth-user-pass", "vpn_auth.txt"]
        if not IS_WINDOWS:
            cmd.append("--daemon") # Linux 下背景執行
        
        subprocess.Popen(cmd, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 5. 等待連線生效 (10秒)
        print(f"{C.C}⏳ 等待 IP 切換 (10s)...{C.E}")
        time.sleep(10)
        print(f"{C.G}✅ VPN 啟動完成，開始攻擊{C.E}")

    async def fetch_user_data(self, session):
        try:
            resp = await session.get(f"{self.base_url}/{self.sub}?fields=gems", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                gems = resp.json().get('gems', 0)
                if self.initial_gems == 0: 
                    self.initial_gems = gems
                    # 第一輪才通知，避免每90秒通知一次
                    print(f"💎 初始寶石：{gems}")
                return True
            elif resp.status_code in [403, 429]:
                self.trigger_kill_switch(f"開局被擋 (Status: {resp.status_code})")
                return False
        except Exception as e:
            print(f"初始化連線錯誤: {e}")
            self.trigger_kill_switch("網路連線失敗")
            return False
        return False

    async def _send_patch(self, session, url, payload):
        if not self.is_running: return
        try:
            resp = await session.patch(url, headers=self.headers, json=payload, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    reward = data.get('currencyReward')
                    if reward is not None and reward == 0:
                        self.trigger_kill_switch("收益為 0 (軟封鎖)")
                        return
                    self.stats['success'] += 1
                except: self.stats['failed'] += 1
            elif resp.status_code in [403, 429]:
                self.trigger_kill_switch(f"封鎖 (Status: {resp.status_code})")
            else: self.stats['failed'] += 1
        except: self.stats['failed'] += 1

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        while self.is_running:
            tasks = [self._send_patch(session, url, payload) for _ in range(batch)]
            await asyncio.gather(*tasks)
            await asyncio.sleep(delay)

    async def monitor_loop(self, session):
        self.start_time = time.time()
        self.last_notify_time = time.time()
        week_days = ["(一)", "(二)", "(三)", "(四)", "(五)", "(六)", "(日)"]
        
        while self.is_running:
            tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
            time_str = tw_time.strftime("%I:%M分%S秒")
            
            elapsed = time.time() - self.start_time
            speed = self.stats['success'] / elapsed if elapsed > 0 else 0
            est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
            current_gems = self.initial_gems + est_gained
            
            # 每 50 秒通知一次 (配合 90 秒生命週期)
            if time.time() - self.last_notify_time > 50:
                msg = f"🟢 [機器人 #{BOT_ID}] 存活中\n💎 累積：+{est_gained}\n⚡ 速度：{speed:.1f}/s"
                # self.send_telegram(msg) # 選擇性開啟，避免太吵
                self.last_notify_time = time.time()
                
            sys.stdout.write(f"\r{C.TIME_ICON} {time_str} ({int(elapsed)}s) {C.SPEED_ICON} {speed:.1f}/s {C.SUCCESS_ICON} {self.stats['success']} {C.Y}💰 +{est_gained}{C.E}    ")
            sys.stdout.flush()
            await asyncio.sleep(1)

    async def start(self):
        # 🟢 在開始任何連線前，先連上隨機 VPN
        self.connect_random_vpn()
        
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
            print("\n👋 本輪結束")

if __name__ == "__main__":
    token = DEFAULT_TOKEN
    try: 
        bot = DuoGemNuclear(token, MAGIC_ID)
        def signal_handler(sig, frame): 
            bot.is_running = False
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
