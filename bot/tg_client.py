import requests

BOT_TOKEN = "8783329976:AAHtpcx-FXEARHNHAE859MeNhE7f97SoTPY"
CHAT_ID   = "6930861685"
BASE_URL  = f"https://api.telegram.org/bot{BOT_TOKEN}"

# 群组话题
GROUP_CHAT_ID = -1003930642546
TOPIC_SPAM    = 2   # 🗑️ 垃圾评论
TOPIC_COMMENT = 3   # 💬 正常评论
TOPIC_DM      = 4   # ✉️ 私信
TOPIC_SYSTEM  = 5   # ⚙️ 系统通知


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


def _send_raw(chat_id, text: str, markdown=False, no_preview=False,
              reply_markup=None, reply_to_message_id: int = None,
              thread_id: int = None) -> int | None:
    payload = {"chat_id": chat_id, "text": text}
    if markdown:
        payload["parse_mode"] = "MarkdownV2"
    if no_preview:
        payload["link_preview_options"] = {"is_disabled": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
        payload["allow_sending_without_reply"] = True
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10,
                          proxies={"http": None, "https": None})
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[TG] 发送失败: {e}")
        return None


def send(text: str, markdown=False, no_preview=False, reply_markup=None,
         reply_to_message_id: int = None) -> int | None:
    return _send_raw(GROUP_CHAT_ID, text, markdown=markdown, no_preview=no_preview,
                     reply_markup=reply_markup, reply_to_message_id=reply_to_message_id,
                     thread_id=TOPIC_SYSTEM)


def send_md(text: str, no_preview=False, reply_markup=None) -> int | None:
    return send(text, markdown=True, no_preview=no_preview, reply_markup=reply_markup)


def send_topic(thread_id: int, text: str, markdown=False, no_preview=False,
               reply_markup=None) -> int | None:
    """发消息到群组指定话题。"""
    return _send_raw(GROUP_CHAT_ID, text, markdown=markdown, no_preview=no_preview,
                     reply_markup=reply_markup, thread_id=thread_id)


def send_topic_md(thread_id: int, text: str, no_preview=False,
                  reply_markup=None) -> int | None:
    return send_topic(thread_id, text, markdown=True, no_preview=no_preview,
                      reply_markup=reply_markup)


def delete_message(chat_id, message_id: int) -> bool:
    try:
        r = requests.post(f"{BASE_URL}/deleteMessage",
                          json={"chat_id": chat_id, "message_id": message_id}, timeout=10,
                          proxies={"http": None, "https": None})
        return r.json().get("ok", False)
    except Exception:
        return False


def answer_callback(callback_query_id: str, text: str = "") -> None:
    try:
        requests.post(f"{BASE_URL}/answerCallbackQuery",
                      json={"callback_query_id": callback_query_id, "text": text}, timeout=5,
                      proxies={"http": None, "https": None})
    except Exception:
        pass


def send_force_reply(text: str, markdown=False, chat_id=None, thread_id: int = None) -> int | None:
    """发一条带 ForceReply 的消息，让用户进入引用回复模式。"""
    payload = {
        "chat_id": chat_id or GROUP_CHAT_ID,
        "text": text,
        "reply_markup": {"force_reply": True, "input_field_placeholder": "输入回复内容..."},
    }
    if markdown:
        payload["parse_mode"] = "MarkdownV2"
    if thread_id:
        payload["message_thread_id"] = thread_id
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10,
                          proxies={"http": None, "https": None})
        return r.json().get("result", {}).get("message_id")
    except Exception as e:
        print(f"[TG] force_reply 发送失败: {e}")
        return None
