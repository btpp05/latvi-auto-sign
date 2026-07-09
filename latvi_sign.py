#!/usr/bin/env python3
"""
Latvi.space 自动签到脚本
用途：每日自动领取 Daily Rewards
支持：直接运行 / GitHub Actions

使用方法：
  python3 latvi_sign.py

环境变量（或直接修改下方默认值）：
  LATVI_EMAIL     - 登录邮箱
  LATVI_PASSWORD  - 登录密码
"""

import os
import sys
import json
import re
import http.cookiejar
import urllib.request
import urllib.parse
import ssl
from datetime import datetime

# ========== 配置 ==========
EMAIL = os.environ.get("LATVI_EMAIL", "btpp04@gmail.com")
PASSWORD = os.environ.get("LATVI_PASSWORD", "Hlm@0649")
BASE_URL = "https://dash.latvi.space"

# ========== HTTPS 配置 ==========
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")


def build_opener():
    """创建带 cookie 支持的 opener"""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPSHandler(context=ctx),
    )
    opener.addheaders = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
    ]
    return opener, cj


def http_get(opener, url, extra_headers=None):
    """GET 请求"""
    req = urllib.request.Request(url)
    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)
    return opener.open(req, timeout=20).read().decode("utf-8")


def http_post(opener, url, data, extra_headers=None, json_body=False):
    """POST 请求"""
    if json_body:
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", "application/json")
    else:
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

    if extra_headers:
        for k, v in extra_headers.items():
            req.add_header(k, v)

    return opener.open(req, timeout=20).read().decode("utf-8")


def get_csrf_token(html):
    """从 HTML 提取 CSRF token"""
    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', html)
    if match:
        return match.group(1)
    return None


def login(opener, cj):
    """登录并获取 session / CSRF token"""
    log(f"正在登录: {EMAIL}")

    # 1. 获取登录页，拿 CSRF token
    try:
        html = http_get(opener, f"{BASE_URL}/login")
    except Exception as e:
        log(f"❌ 无法访问登录页: {e}")
        return None

    csrf = get_csrf_token(html)
    if not csrf:
        log("❌ 无法获取 CSRF token")
        return None

    log(f"  CSRF token: {csrf[:20]}...")

    # 2. 提交登录
    try:
        resp_html = http_post(opener, f"{BASE_URL}/login", {
            "_token": csrf,
            "email": EMAIL,
            "password": PASSWORD,
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        if "These credentials" in body or "credentials" in body:
            log("❌ 登录失败：凭证不匹配")
        else:
            log(f"❌ 登录失败: {e}")
        return None
    except Exception as e:
        log(f"❌ 登录异常: {e}")
        return None

    # 检查是否登录成功
    if "logout" in resp_html.lower() or "btpp04" in resp_html or "Daily Rewards" in resp_html:
        log("✅ 登录成功")
        # 用登录后页面（如 /home）返回的 CSRF 才对 claim 有效
        new_csrf = get_csrf_token(resp_html)
        return new_csrf or csrf
    else:
        log("❌ 登录失败，请检查账号密码")
        return None


def claim_daily(opener, csrf_token):
    """领取每日签到奖励。返回 (ok: bool, already_claimed: bool, info: dict)"""
    log("正在领取每日奖励...")

    try:
        body = json.dumps({}).encode("utf-8")
        req = urllib.request.Request(f"{BASE_URL}/daily-rewards/claim", data=body)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        req.add_header("X-CSRF-TOKEN", csrf_token)
        req.add_header("X-Requested-With", "XMLHttpRequest")

        resp = opener.open(req, timeout=20)
        data = json.loads(resp.read().decode("utf-8"))

        if data.get("success"):
            # 余额以 API 返回的 new_balance 为准（最可靠）
            reward = data.get("reward", 0)
            try:
                # API 返回 reward 单位为千分之一 Credit（如 5000 -> 5.00）
                reward_credits = reward / 1000 if reward > 100 else reward
                reward_str = f"{reward_credits:.2f}"
            except Exception:
                reward_str = str(reward)
            new_balance = data.get("new_balance", "?")
            streak = data.get("new_streak", "?")
            log(f"✅ 签到成功！+{reward_str} Credits（连续签到 {streak} 天）")
            log(f"💰 领取后余额: {new_balance} Credits")
            return True, False, data
        else:
            error = data.get("error", data.get("message", "未知错误"))
            log(f"⚠️ 签到失败: {error}")
            return False, False, data

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            data = json.loads(body)
        except Exception:
            data = {}
        if e.code == 429:
            # 今日已领取过 -> 明确提示，不要假装成功
            msg = data.get("error", data.get("message", "今日已领取"))
            next_t = data.get("next_claim_time", "")
            log(f"ℹ️ 今日已签到（奖励已于更早时领取，无需重复）")
            if next_t:
                log(f"   下次可领: {next_t}")
            return False, True, data
        error = data.get("error", data.get("message", str(e)))
        log(f"⚠️ {error}")
        return False, False, data
    except Exception as e:
        log(f"❌ 请求异常: {e}")
        return False, False, {}


def get_credits(opener):
    """获取当前余额（精确匹配 Credits 卡片里的数字，避免误取服务器数）"""
    try:
        html = http_get(opener, f"{BASE_URL}/home")
        # 首页余额卡片结构:
        #   <span class="info-box-text">Credits</span>
        #   <span class="info-box-number">15.00</span>
        m = re.search(r'info-box-text">Credits</span>\s*<span class="info-box-number">([\d,.]+)',
                      html, re.IGNORECASE)
        if m:
            return m.group(1)
        # 备用：<small>...</small>15.00
        m = re.search(r'fa-coins[^>]*></i></small>\s*([\d,.]+)', html)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "?"


def list_servers(opener):
    """列出正在运行且会消耗积分的服务器（仅提醒付费实例）"""
    try:
        html = http_get(opener, f"{BASE_URL}/servers")
    except Exception:
        return
    # 只警告真正在扣积分的实例：卡片里同时出现 "per Day" 且价格 > 0
    cards = re.findall(r'class="[^"]*server[^"]*"[^>]*>.*?</div>', html, re.S | re.I)
    warned = False
    for c in cards:
        if "per Day" in c and "No credits" not in c and "Free" not in c:
            price = re.search(r'([\d.]+)\s*per Day', c, re.I)
            if price and float(price.group(1)) > 0:
                if not warned:
                    log("⚠️ 发现按天扣分的实例，可能抵消签到奖励：")
                    warned = True
                name = re.search(r'([A-Za-z0-9_\- ]+?)\s*\(', c)
                log(f"   🖥️ {name.group(1).strip() if name else '实例'} — {price.group(1)}/天")
    if not warned:
        log("✅ 无按天扣分的实例（免费服务器不消耗积分）")


def main():
    log("=" * 40)
    log("Latvi.space 自动签到")
    log("=" * 40)

    opener, cj = build_opener()

    csrf = login(opener, cj)
    if not csrf:
        sys.exit(1)

    # 直接尝试领取：成功就加积分；429 表示今天已领过（不算失败）
    ok, already, info = claim_daily(opener, csrf)

    if not ok and not already:
        # 真正失败（网络/凭证/服务器错误），非“已领取”
        credits = get_credits(opener)
        log(f"💰 当前余额: {credits} Credits")
        sys.exit(1)

    # 余额优先用 API 返回，否则抓取页面
    if ok and info.get("new_balance"):
        balance = info.get("new_balance")
    else:
        balance = get_credits(opener)
    log(f"💰 当前余额: {balance} Credits")

    list_servers(opener)
    log("=" * 40)
    log("完成!")
    log("🔗 https://github.com/btpp05/latvi-auto-sign")


if __name__ == "__main__":
    main()
