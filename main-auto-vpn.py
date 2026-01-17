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

# --- [極致霓虹配色 UI] ---
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

IS_WINDOWS = sys.platform == 'win32'
CONFIG_DIR = "./vpn_configs"

if IS_WINDOWS: OPENVPN_CMD = [r"C:\Program Files\OpenVPN\bin\openvpn.exe"]
else: OPENVPN_CMD = ["sudo", "openvpn"]

# ⚠️ 請確認這是你的 SKILL ID
MAGIC_ID = "CAPSTONE_COMPLETION-f526ff3b_5d8f_3958_a14c_0bcba416022b-1-GEMS"

# ==========================================
# ☠️ 神風特攻模式 (Kamikaze Mode)
# ==========================================
DEFAULT_THREADS = 40    # 暴力多開
DEFAULT_BATCH = 100     # 單次最大搬運
DEFAULT_DELAY = 0       # 0秒延遲，全速轟炸
NOTIFY_INTERVAL = 300   # 5分鐘報告一次

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

    # 🟢 [神風核心] 遇到封鎖直接拔插頭 (os._exit)
    async def suicide_restart(self):
        print(f"\n{C.R}💀 偵測到封鎖 (429/空包彈)！執行戰術重啟...{C.E}")
        if IS_WINDOWS: subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else: subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        
        # 強制瞬殺，不讓 except 攔截
        os._exit(1) 

    # 🟢 啟動時隨機連線 VPN
    async def connect_random_vpn(self):
        if not self.config_files: os._exit(1)
        config_name = random.choice(self.config_files)
        print(f"{C.M}🛡️ [戰術突擊] 載入節點: {config_name}...{C.E}")

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
                if self.initial_gems == 0: 
                    self.initial_gems = gems
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
            
            # 👇👇👇 核心修改：檢查是不是「空包彈」 👇👇👇
            if 200 <= resp.status_code < 300:
                try:
                    data = resp.json()
                    # 如果回傳是空的 {} 或者 currencyReward 是 0，代表被軟鎖了
                    # 有些練習會給 xpReward 但不給 currencyReward，所以兩個都要檢查
                    reward = data.get('currencyReward', 0) + data.get('xpReward', 0)
                    
                    if reward > 0:
                        self.stats['success'] += 1
                    else:
                        # 雖然是 200 OK，但沒獎勵 -> 視為封鎖 -> 自殺換 IP
                        await self.suicide_restart()
                except:
                    # 解析 JSON 失敗 -> 自殺
                    await self.suicide_restart()
            else: 
                # 429/403/500 -> 自殺
                await self.suicide_restart()
        except: 
            # 連線錯誤 -> 自殺
            await self.suicide_restart()

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        while self.is_running:
            tasks = [self._send_patch(session, url, payload) for _ in range(batch)]
            await asyncio.gather(*tasks)
            if delay > 0: await asyncio.sleep(delay)

    async def monitor_loop(self, session):
        self.start_time = time.time()
        self.last_notify_time = time.time()
        week_days = ["(一)", "(二)", "(三)", "(四)", "(五)", "(六)", "(日)"]
        
        while self.is_running:
            tw_time = datetime.now(timezone.utc) + timedelta(hours=8)
            date_str = tw_time.strftime("%Y年%m月%d日")
            week_str = week_days[tw_time.weekday()]
            period = "早上" if tw_time.hour < 12 else "下午"
            time_str = tw_time.strftime("%I:%M分%S秒")
            final_display = f"{date_str}{week_str}{period}{time_str}"
            
            elapsed = time.time() - self.start_time
            speed = self.stats['success'] / elapsed if elapsed > 0 else 0
            est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
            current_gems = self.initial_gems + est_gained
            
            if time.time() - self.last_notify_time > NOTIFY_INTERVAL:
                hours, rem = divmod(elapsed, 3600)
                minutes, seconds = divmod(rem, 60)
                run_time_str = "{:0>2}時{:0>2}分{:0>2}秒".format(int(hours),int(minutes),int(seconds))
                
                msg = (
                    f"🔥 [神風報告] 激戰中\n"
                    f"⏰ {run_time_str}\n"
                    f"💰 本次: +{est_gained}\n"
                    f"🏆 總額: {current_gems}\n"
                    f"⚡ 速度: {speed:.1f}/s"
                )
                self.send_telegram(msg)
                self.send_line(msg)
                self.last_notify_time = time.time()

            sys.stdout.write(f"\r{C.TIME_ICON} {final_display} ({int(elapsed)}s) {C.SPEED_ICON} {speed:.1f}/s {C.SUCCESS_ICON} {self.stats['success']} {C.GEM_ICON} +{est_gained}{C.E}    ")
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
    if "xxxx" in MAGIC_ID or "SKILL_COMPLETION" not in MAGIC_ID:
        print(f"{C.R}⚠️ 警告：請記得修改代碼中的 MAGIC_ID！{C.E}")

    try: 
        bot = DuoGemNuclear(token, MAGIC_ID)
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
