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
DEFAULT_TOKEN = os.environ.get("DUO_TOKEN", "")

LINE_ACCESS_TOKEN = os.environ.get("LINE_ACCESS_TOKEN", "") 
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# 參數設定
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
        self.kill_switch_active = False # 防止多線程重複觸發
        self.start_time = 0
        self.initial_gems = 0
        self.avg_gems_per_hit = 14.0 
        self.last_notify_time = 0 

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
        """
        核心防護機制：偵測到異常直接殺掉進程
        """
        if self.kill_switch_active: return
        self.kill_switch_active = True
        self.is_running = False
        
        # 顯示與通知
        print(f"\n{C.R}⛔ {reason} -> 觸發安全機制，立即終止！{C.E}")
        
        final_msg = f"⛔ 嚴重警告：偵測到異常\n💀 原因：{reason}\n🛑 動作：程式強制終止 (Exit 1)"
        self.send_telegram(final_msg)
        self.send_line(final_msg)
        
        # 強制退出
        os._exit(1)

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
                self.trigger_kill_switch(f"初始化被拒 (Status: {resp.status_code})")
                return False
        except Exception as e:
            print(f"初始化錯誤: {e}")
            return False
        return False

    async def _send_patch(self, session, url, payload):
        if not self.is_running: return
        try:
            resp = await session.patch(url, headers=self.headers, json=payload, timeout=10)
            
            # [判定邏輯區]
            if resp.status_code == 200:
                try:
                    # 檢查是否為「假性成功」(200 OK 但沒獎勵)
                    data = resp.json()
                    reward = data.get('currencyReward')
                    
                    # 情況 A: 回傳資料中有 currencyReward 欄位且為 0 -> 軟封鎖/上限
                    if reward is not None and reward == 0:
                        self.trigger_kill_switch("200 OK 但無獎勵 (收益為 0)")
                        return
                        
                    # 情況 B: 成功
                    self.stats['success'] += 1
                except:
                    # JSON 解析失敗，通常是網路問題，暫時計入失敗但不退出，除非非常頻繁
                    self.stats['failed'] += 1

            elif resp.status_code in [403, 429]:
                # 情況 C: 明確的封鎖代碼
                self.trigger_kill_switch(f"偵測到封鎖 (Status: {resp.status_code})")
            
            else:
                self.stats['failed'] += 1
                
        except Exception as e:
            self.stats['failed'] += 1

    async def attack_worker(self, worker_id, session, payload, batch, delay):
        url = f"{self.base_url}/{self.sub}/rewards/{self.reward_id}"
        # 移除 vpn_lock 等待，全速執行直到 is_running 為 False
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
        # 只有正常結束（Ctrl+C）會走到這，異常會直接 os._exit
        est_gained = int(self.stats['success'] * self.avg_gems_per_hit)
        final_gems = self.initial_gems + est_gained
        msg = f"🛑 任務手動停止\n💰 本次獲得：+{est_gained}\n🏆 最終總額：{final_gems}"
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
        def signal_handler(sig, frame): 
            bot.is_running = False
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        asyncio.run(bot.start())
    except KeyboardInterrupt: pass
