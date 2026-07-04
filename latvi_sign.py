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
        new_csrf = get_csrf_token(resp_html)
        return new_csrf or csrf
    else:
        log("❌ 登录失败，请检查账号密码")
        return None


def claim_daily(opener, csrf_token):
    """领取每日签到奖励"""
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
            log(f"✅ 签到成功！{data.get('message', '')}")
            return True
        else:
            error = data.get("error", data.get("message", "未知错误"))
            log(f"⚠️ 签到失败: {error}")
            return False
            
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            data = json.loads(body)
            error = data.get("error", data.get("message", str(e)))
            log(f"⚠️ {error}")
        except:
            log(f"❌ HTTP {e.code}: {body[:200]}")
        return False
    except Exception as e:
        log(f"❌ 请求异常: {e}")
        return False


def check_status(opener):
    """查看今日签到状态"""
    log("检查签到状态...")
    
    try:
        html = http_get(opener, f"{BASE_URL}/daily-rewards")
        
        if "On Cooldown" in html:
            log("⏳ 今日已签到（冷却中）")
            return "claimed"
        elif "Claim Reward" in html or "claim" in html.lower():
            log("🎯 今日尚未签到，可以领取")
            return "ready"
        else:
            log("❓ 无法确定签到状态")
            return "unknown"
    except Exception as e:
        log(f"❌ 检查状态失败: {e}")
        return "unknown"


def get_credits(opener):
    """尝试获取当前余额"""
    try:
        html = http_get(opener, f"{BASE_URL}/home")
        # 从用户下拉菜单找余额
        match = re.search(r'id="userDropdown"[^>]*>([^<]*)', html)
        if match:
            val = match.group(1).strip()
            if val:
                return val
        # 备选方式
        for pattern in [r'([\d,]+\.?\d*)\s*Credits', r'>([\d,.]+)\s*<', r'credits[^d]+([\d,.]+)']:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                return m.group(1)
    except:
        pass
    return "?"


def main():
    log("=" * 40)
    log("Latvi.space 自动签到")
    log("=" * 40)
    
    opener, cj = build_opener()
    
    csrf = login(opener, cj)
    if not csrf:
        sys.exit(1)
    
    status = check_status(opener)
    
    if status == "ready":
        claim_daily(opener, csrf)
    elif status == "claimed":
        log("✅ 今天已经签到了，无需重复操作")
    else:
        # 不确定状态，直接尝试
        log("尝试直接签到...")
        claim_daily(opener, csrf)
    
    credits = get_credits(opener)
    log(f"💰 当前余额: {credits} Credits")
    log("=" * 40)
    log("完成!")


if __name__ == "__main__":
    main()
