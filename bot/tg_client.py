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


def inline_keyboard(buttons: list[list[tuple[str, str]]]) -> dict:
    """构建 InlineKeyboardMarkup。buttons 是二维列表，每项为 (label, callback_data)。"""
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in buttons
        ]
    }


def send(text: str, markdown=False, no_preview=False, reply_markup=None) -> int | None:
    payload = {"chat_id": CHAT_ID, "text": text}
    if markdown:
        payload["parse_mode"] = "MarkdownV2"
    if no_preview:
        payload["link_preview_options"] = {"is_disabled": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[TG] 发送失败: {e}")
        return None


def send_md(text: str, no_preview=False, reply_markup=None) -> int | None:
    return send(text, markdown=True, no_preview=no_preview, reply_markup=reply_markup)


def answer_callback(callback_query_id: str, text: str = "") -> None:
    try:
        requests.post(f"{BASE_URL}/answerCallbackQuery",
                      json={"callback_query_id": callback_query_id, "text": text}, timeout=5)
    except Exception:
        pass


def send_force_reply(text: str, quote: str = "", markdown=False) -> int | None:
    """发一条带 ForceReply 的消息，让用户进入引用回复模式。"""
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "reply_markup": {"force_reply": True, "input_field_placeholder": "输入回复内容..."},
    }
    if quote:
        payload["reply_markup"]["selective"] = True
    if markdown:
        payload["parse_mode"] = "MarkdownV2"
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[TG] force_reply 发送失败: {e}")
        return None
