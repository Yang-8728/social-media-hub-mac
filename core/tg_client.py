import requests
from core.config import BOT_TOKEN, CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def esc(text: str) -> str:
    """Escape special chars for MarkdownV2"""
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text


def send(text: str, markdown=False):
    """发送纯文本或 MarkdownV2 消息"""
    payload = {"chat_id": CHAT_ID, "text": text}
    if markdown:
        payload["parse_mode"] = "MarkdownV2"
    try:
        requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"[TG] 发送失败: {e}")


def send_md(text: str):
    send(text, markdown=True)
