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

# --- [設定區] ---
# ⚠️ 請填入你現在用的那個 ID
MAGIC_ID = "SKILL_COMPLETION_BALANCED-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx-1-GEMS"

BOT_ID = os.environ.get("BOT_ID", "1")
VPN_USER = os.environ.get("VPN_USER", "aFwROLMWIY5ljknZ") 
VPN_PASS = os.environ.get("VPN_PASS", "XlNXBom0tFVNFp3GNH58xDJASRoxOr8m")
DEFAULT_TOKEN = os.environ.get("DUO_TOKEN", "")

class C:
    E, R, G, Y = '\033[0m', '\033[91m', '\033[92m', '\033[93m'

# 只跑一次測試
async def test_run():
    token = DEFAULT_TOKEN
    print(f"{C.Y}🔍 開始進行 ID 健康檢查...{C.E}")
    
    # 1. 解碼 Token 確認帳號
    try:
        payload = token.split(".")[1] + "=="
        sub = json.loads(base64.urlsafe_b64decode(payload))['sub']
        print(f"👤 用戶 ID: {sub}")
    except:
        print(f"{C.R}❌ Token 解碼失敗，請檢查 DUO_TOKEN{C.E}")
        return

    # 2. 發送單次請求看回應
    url = f"https://www.duolingo.com/2017-06-30/users/{sub}/rewards/{MAGIC_ID}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }
    payload_data = {"consumed": True, "fromLanguage": "en", "learningLanguage": "es"}

    print(f"🚀 發送測試請求...")
    async with AsyncSession(impersonate="chrome120") as session:
        try:
            resp = await session.patch(url, headers=headers, json=payload_data)
            
            print(f"\n📊 --- 伺服器回應報告 ---")
            print(f"狀態碼 (Status): {resp.status_code}")
            
            try:
                data = resp.json()
                print(f"回應內容 (Body): {json.dumps(data, indent=2)}")
                
                # 分析結果
                gems = data.get('currencyReward', 0) # 或者是 xpReward
                if resp.status_code == 200:
                    if gems > 0:
                        print(f"\n{C.G}✅ 測試通過！這個 ID 是有效的，每次可獲得 {gems} 獎勵。{C.E}")
                        print("👉 如果你還是沒看到寶石增加，請重啟手機 App (顯示延遲)。")
                    else:
                        print(f"\n{C.R}❌ 測試失敗！伺服器回傳成功，但獎勵是 0。{C.E}")
                        print(f"{C.Y}原因：這個 ID 可能是「寶箱」或「一次性任務」，已經被領過了。{C.E}")
                        print("👉 解法：請重新抓一個「練習 (Practice)」的 ID。")
                elif resp.status_code == 403 or resp.status_code == 400:
                     print(f"\n{C.R}❌ ID 無效或過期！{C.E}")
                     print("👉 解法：這個 ID 已經爛掉了，請去抓新的。")
                elif resp.status_code == 429:
                     print(f"\n{C.R}⛔ 帳號被鎖 (429 Too Many Requests){C.E}")
                     print("👉 解法：你的帳號正在坐牢，請休息 24 小時。")
            except:
                print(f"無法解析 JSON: {resp.text}")

        except Exception as e:
            print(f"❌ 連線錯誤: {e}")

if __name__ == "__main__":
    asyncio.run(test_run())
