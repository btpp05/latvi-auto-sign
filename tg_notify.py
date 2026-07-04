import json, urllib.request, sys, re, os

# Read sign result from temp file (ANSI codes stripped by sed)
with open('/tmp/sign_result.txt') as f:
    raw = f.read()

# Strip ANSI escape codes
clean = re.sub(r'\x1b\[[0-9;]*m', '', raw)
lines = [l.strip() for l in clean.split('\n') if l.strip()]
msg = '\n'.join(lines)

# Send to Telegram
bot_token = os.environ['BOT_TOKEN']
chat_id = '644320820'

payload = json.dumps({
    'chat_id': chat_id,
    'text': msg,
}).encode()

req = urllib.request.Request(
    f'https://api.telegram.org/bot{bot_token}/sendMessage',
    data=payload,
    headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req)
print('✅ Telegram 通知已发送')
