# Latvi Auto Sign

Latvi.space (dash.latvi.space) 每日自动签到脚本。

## 功能

- 每日自动领取 Daily Rewards（约 UTC 2:00 / 北京时间 10:00）
- 支持 GitHub Actions 运行（免费）
- 支持手动触发

## 使用方法

### 1. Fork 或 Clone 此仓库

### 2. 配置 Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中设置：

| Secret | 说明 |
|--------|------|
| `LATVI_EMAIL` | 登录邮箱（btpp04@gmail.com） |
| `LATVI_PASSWORD` | 登录密码 |

### 3. 手动触发

进入 Actions → 每日自动签到 → Run workflow

### 本地运行

```
python3 latvi_sign.py
```

