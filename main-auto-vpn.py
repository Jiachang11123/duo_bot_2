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
# 🚀 智能巡航模式 (Smart Cruise)
# ==========================================
# 速度設定：稍微快一點，因為我們有熔斷保護了
DEFAULT_THREADS = 5     # 5 線程 (效率與安全的平衡)
DEFAULT_BATCH = 50      # 單次搬運量大
DEFAULT_DELAY = 1.0     # 間隔 1 秒

# 🛡️ 熔斷保護設定 (核心關鍵)
SAFE_LIMIT = 40000      # 刷到 3.5 萬分就停 (避開 4萬分 封鎖線)
REST_TIME = 180         # 強制休息 5 分鐘 (讓伺服器冷卻)

NOTIFY_INTERVAL = 1800  # 30分鐘通知

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
        
        # 用來記錄這一輪刷了多少，用於熔斷判斷
        self.session_gained = 0
        
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
            requests.post(url, headers=headers, json=data, timeout=5)
        except: pass

    def send_telegram(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        msg_with_id = f"🤖 [機器人 #{BOT_ID}]\n{message}"
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg_with_id}
            requests.post(url, json=data, timeout=5)
        except: pass

    # 🟢 [核心邏輯] 遇到封鎖直接自殺
    async def suicide_restart(self):
        print(f"\n{C.R}💀 偵測到封鎖 (403/429)！執行自殺式重啟...{C.E}")
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else:
            subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        sys.exit(1)

    # 🟢 啟動時連線 VPN
    async def connect_random_vpn(self):
        if not self.config_files:
            print(f"\n{C.R}❌ 嚴重錯誤：找不到 .ovpn 檔案！{C.E}")
            sys.exit(1)

        config_name = random.choice(self.config_files)
        print(f"{C.M}🛡️ [啟動] 正在連線至 VPN: {config_name}...{C.E}")

        if IS_WINDOWS: subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
        else: subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
        
        await asyncio.sleep(2)
        
        with open("vpn_auth.txt", "w") as f: f.write(f"{VPN_USER}\n{VPN_PASS}")
        
        cmd = OPENVPN_CMD + ["--config", f"{CONFIG_DIR}/{config_name}", "--auth-user-pass", "vpn_auth.txt"]
        if not IS_WINDOWS: cmd.append("--daemon")
        
        subprocess.Popen(cmd, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        for i in range(15, 0, -1):
            sys.stdout.write(f"\r⏳ 等待 VPN 連線... {i}s ")
            sys.stdout.flush()
            await asyncio.sleep(1)
        print(f"\n{C.G}✅ VPN 連線完成！{C.E}")

    async def fetch_user_data(self, session):
        try:
            resp = await session.get(f"{self.base_url}/{self.sub}?fields=gems", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                gems = resp.json().get('gems', 0)
                if self.initial_gems == 0: 
                    self.initial_gems = gems
                    msg = f"🚀 機器人啟動成功 (重啟)\n💎 初始寶石：{gems}"
                    # self.send_telegram(msg)
                return True
            elif resp.status_code in [403, 429]:
                await self.suicide_restart()
                return False
        except:
            await self.suicide_restart()
        return False

    async def _send_patch(self, session, url, payload):
        try:
            # 如果正在休息 (鎖定中)，就不發送請求
            if self.vpn_lock.locked(): return
            
            resp = await session.patch(url, headers=self.headers, json=payload, timeout=10)
            if 200 <= resp.status_code < 300: self.stats['success'] += 1
            elif resp.status_code in [403, 429]: await self.suicide_restart()
            else: self.stats['failed'] += 1
        except: self.stats['failed'] += 1

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        while self.is_running:
            # 檢查是否在休息中
            if not self.vpn_lock.locked():
                tasks = [self._send_patch(session, url, payload) for _ in range(batch)]
                await asyncio.gather(*tasks)
                await asyncio.sleep(delay)
            else:
                # 休息中，暫停 5 秒再檢查
                await asyncio.sleep(5)

    async def monitor_loop(self, session):
        self.start_time = time.time()
        self.last_notify_time = time.time()
        self.session_gained = 0 # 重置當前會話收益

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
            
            # 計算當前總收益
            current_total_gained = int(self.stats['success'] * self.avg_gems_per_hit)
            
            # 👇👇👇 智能熔斷判斷 👇👇👇
            # 如果 (目前總收益 - 上次休息後的收益) >= 安全極限
            if current_total_gained - self.session_gained >= SAFE_LIMIT:
                print(f"\n{C.Y}☕ 達到安全極限 ({SAFE_LIMIT})，觸發主動休息 {REST_TIME} 秒...{C.E}")
                self.send_telegram(f"☕ 觸發熔斷保護 (已刷 {SAFE_LIMIT} 分)，休息 {int(REST_TIME/60)} 分鐘...")
                
                # 鎖住 VPN 鎖，讓所有 worker 暫停
                async with self.vpn_lock:
                    # 顯示倒數計時
                    for i in range(REST_TIME, 0, -1):
                        sys.stdout.write(f"\r💤 休息中... 剩餘 {i} 秒   ")
                        sys.stdout.flush()
                        await asyncio.sleep(1)
                
                # 休息結束，更新基準點
                self.session_gained = current_total_gained
                print(f"\n{C.G}▶️ 休息結束，繼續刷分！{C.E}")
                self.send_telegram("▶️ 體力恢復，繼續刷分")
            # 👆👆👆 判斷結束 👆👆👆

            if time.time() - self.last_notify_time > NOTIFY_INTERVAL:
                hours = int(elapsed / 3600)
                msg = (
                    f"🟢 [定期報告] 執行中\n"
                    f"⏱️ 運行: {hours}小時\n"
                    f"💰 本次: +{current_total_gained}\n"
                    f"⚡ 速度: {speed:.1f}/s"
                )
                self.send_telegram(msg)
                self.send_line(msg)
                self.last_notify_time = time.time()

            # 顯示狀態列 (如果沒在休息)
            if not self.vpn_lock.locked():
                sys.stdout.write(f"\r{C.TIME_ICON} {final_display} ({int(elapsed)}s) {C.SPEED_ICON} {speed:.1f}/s {C.SUCCESS_ICON} {self.stats['success']} {C.Y}💰 +{current_total_gained}{C.E}    ")
                sys.stdout.flush()
            
            await asyncio.sleep(1)

    async def cleanup(self):
        est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
        print(f"\n🛑 任務結束 (準備重啟...)\n💰 本次獲得：+{est_gained}")

    async def start(self):
        # 🟢 啟動前隨機冷卻 5~15 秒
        wait_time = random.randint(5, 15)
        print(f"⏳ 啟動冷卻中... ({wait_time}s)")
        await asyncio.sleep(wait_time)
        
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
