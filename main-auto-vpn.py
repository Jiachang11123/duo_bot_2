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
BOT_ID = os.environ.get("BOT_ID", "1") # 讀取編號
VPN_USER = os.environ.get("VPN_USER", "aFwROLMWIY5ljknZ") 
VPN_PASS = os.environ.get("VPN_PASS", "XlNXBom0tFVNFp3GNH58xDJASRoxOr8m")
DEFAULT_TOKEN = os.environ.get("DUO_TOKEN", "")

LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "") 
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ... (中間路徑判斷與攻擊設定維持原樣) ...
IS_WINDOWS = sys.platform == 'win32'
CONFIG_DIR = "./vpn_configs"

if IS_WINDOWS:
    OPENVPN_CMD = [r"C:\Program Files\OpenVPN\bin\openvpn.exe"]
else:
    OPENVPN_CMD = ["sudo", "openvpn"]

MAGIC_ID = "SKILL_COMPLETION_BALANCED-…-2-GEMS"
DEFAULT_THREADS = 25
DEFAULT_BATCH = 60
DEFAULT_DELAY = 0.6
NOTIFY_INTERVAL = 60

class DuoGemNuclear:
    def __init__(self, token, reward_id):
        # ... (初始化內容維持原樣) ...
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
        self.avg_gems_per_hit = 14.0 
        self.vpn_lock = asyncio.Lock()
        self.last_notify_time = 0 
        
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR, exist_ok=True)
        self.config_files = [f for f in os.listdir(CONFIG_DIR) if f.endswith('.ovpn')]
        self.config_index = 0

    def _decode_jwt(self, token):
        try:
            payload = token.split(".")[1] + "=="
            return json.loads(base64.urlsafe_b64decode(payload))['sub']
        except: return "Unknown"

    def send_line(self, message):
        if not LINE_ACCESS_TOKEN or not LINE_USER_ID: return
        # 加入編號
        msg_with_id = f"🤖 [機器人 #{BOT_ID}]\n{message}"
        try:
            url = 'https://api.line.me/v2/bot/message/push'
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_ACCESS_TOKEN}'}
            data = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": msg_with_id}]}
            requests.post(url, headers=headers, json=data)
        except: pass

    def send_telegram(self, message):
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
        # 加入編號
        msg_with_id = f"🤖 [機器人 #{BOT_ID}]\n{message}"
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg_with_id}
            requests.post(url, json=data)
        except: pass

    # ... (其餘 rotate_vpn, attack_worker, monitor_loop 等函式維持原樣不動) ...
    async def rotate_vpn(self):
        if self.vpn_lock.locked(): return
        async with self.vpn_lock:
            tw_now = datetime.now(timezone.utc) + timedelta(hours=8)
            time_tag = tw_now.strftime("%H:%M:%S")
            print(f"\n[{time_tag}] {C.M}🛡️ 正在切換 IP...{C.E}")
            self.send_telegram(f"🛡️ 偵測到連線受阻\n⏰ 時間：{time_tag}\n⚙️ 正在切換 IP...")
            try:
                if IS_WINDOWS:
                    subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], capture_output=True)
                else:
                    subprocess.run(["sudo", "killall", "openvpn"], capture_output=True)
                await asyncio.sleep(2)
                if not self.config_files:
                    print("❌ 無設定檔")
                    self.send_telegram("❌ 錯誤：找不到 VPN 設定檔！")
                    return
                config_name = self.config_files[self.config_index]
                self.config_index = (self.config_index + 1) % len(self.config_files)
                with open("vpn_auth.txt", "w") as f: f.write(f"{VPN_USER}\n{VPN_PASS}")
                cmd = OPENVPN_CMD + ["--config", f"{CONFIG_DIR}/{config_name}", "--auth-user-pass", "vpn_auth.txt"]
                if not IS_WINDOWS:
                    cmd.append("--daemon")
                subprocess.Popen(cmd, cwd=os.getcwd(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"{C.C}🌐 連線目標：{config_name}{C.E}")
                await asyncio.sleep(15)
                print(f"{C.G}✅ 網路重連完成{C.E}")
                self.send_telegram(f"✅ IP 切換成功！\n🌐 新節點：{config_name}\n🚀 繼續刷分中...")
            except Exception as e:
                print(f"{C.R}❌ VPN 錯誤：{e}{C.E}")
                self.send_telegram(f"❌ VPN 切換失敗：{e}")

    async def fetch_user_data(self, session):
        try:
            resp = await session.get(f"{self.base_url}/{self.sub}?fields=gems", headers=self.headers, timeout=10)
            if resp.status_code == 200:
                gems = resp.json().get('gems', 0)
                if self.initial_gems == 0: 
                    self.initial_gems = gems
                    msg = f"🚀 機器人啟動成功！\n💎 初始寶石：{gems}"
                    self.send_telegram(msg)
                    self.send_line(msg)
                return True
            elif resp.status_code in [403, 429]:
                await self.rotate_vpn()
                return False
        except:
            await self.rotate_vpn()
        return False

    async def _send_patch(self, session, url, payload):
        try:
            if self.vpn_lock.locked(): return
            resp = await session.patch(url, headers=self.headers, json=payload, timeout=10)
            if 200 <= resp.status_code < 300: self.stats['success'] += 1
            elif resp.status_code in [403, 429]: await self.rotate_vpn()
            else: self.stats['failed'] += 1
        except: self.stats['failed'] += 1

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        while self.is_running:
            if not self.vpn_lock.locked():
                tasks = [self._send_patch(session, url, payload) for _ in range(batch)]
                await asyncio.gather(*tasks)
                await asyncio.sleep(delay)
            else: await asyncio.sleep(5)

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
                    f"🟢 [分鐘報告] 執行中\n"
                    f"⏰ {run_time_str}\n"
                    f"💎 初始：{self.initial_gems}\n"
                    f"💰 本次：+{est_gained}\n"
                    f"🏆 總額：{current_gems}\n"
                    f"⚡ 速度：{speed:.1f}/s"
                )
                self.send_telegram(msg)
                self.last_notify_time = time.time()
            sys.stdout.write(f"\r{C.TIME_ICON} {final_display} ({int(elapsed)}s) {C.SPEED_ICON} {speed:.1f}/s {C.SUCCESS_ICON} {self.stats['success']} {C.Y}💰 +{est_gained}{C.E}    ")
            sys.stdout.flush()
            await asyncio.sleep(1)

    async def cleanup(self):
        est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
        final_gems = self.initial_gems + est_gained
        msg = f"🛑 任務結束 (或中斷)\n💰 本次獲得：+{est_gained}\n🏆 最終總額：{final_gems}"
        self.send_telegram(msg)
        self.send_line(msg)

    async def start(self):
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
    try: 
        bot = DuoGemNuclear(token, MAGIC_ID)
        def signal_handler(sig, frame): bot.is_running = False
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
