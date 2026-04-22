import requests

BOT_TOKEN = "8783329976:AAHtpcx-FXEARHNHAE859MeNhE7f97SoTPY"
CHAT_ID   = "6930861685"
BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"


def esc(text: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        text = text.replace(ch, f'\\{ch}')
    return text


def link(text: str, url: str) -> str:
    safe_url = url.replace("\\", "\\\\").replace(")", "\\)")
    return f"[{esc(text)}]({safe_url})"


def send(text: str, markdown=False, no_preview=False) -> int | None:
    payload = {"chat_id": CHAT_ID, "text": text}
    if markdown:
        payload["parse_mode"] = "MarkdownV2"
    if no_preview:
        payload["link_preview_options"] = {"is_disabled": True}
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[TG] 发送失败: {e}")
        return None


def send_md(text: str, no_preview=False) -> int | None:
    return send(text, markdown=True, no_preview=no_preview)
