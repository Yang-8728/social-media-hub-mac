"""
生产者-消费者交互队列。

feature 调用 push() 把需要用户确认的消息放入队列，
bot.py 主循环调用 pop() 取出并发给用户，
用户回复后调用 resolve() 触发回调。
"""
import queue
import threading

_q: queue.Queue = queue.Queue()
_pending: dict = {}   # current item waiting for reply
_lock = threading.Lock()
_interactive_mode = threading.Event()  # set = 交互中，monitor 暂停推送


def set_interactive(active: bool):
    if active:
        _interactive_mode.set()
    else:
        _interactive_mode.clear()


def is_interactive() -> bool:
    return _interactive_mode.is_set()


def push(message: str, callback, on_sent=None):
    """
    feature 调用。
    message:  发给用户的文字
    callback: 收到回复后调用，参数为用户输入的原始文本
    on_sent:  消息发送成功后调用，参数为 Telegram message_id
    """
    _q.put({"message": message, "callback": callback, "on_sent": on_sent})


def pop(block=True):
    """bot.py 调用，取出下一条待发送消息。"""
    return _q.get(block=block)


def set_pending(item: dict):
    """bot.py 标记当前正在等待回复的消息。"""
    with _lock:
        _pending["item"] = item


def resolve(answer: str):
    """
    bot.py 收到用户回复时调用。
    answer: 用户原始文本
    """
    with _lock:
        item = _pending.pop("item", None)
    if item:
        threading.Thread(target=item["callback"], args=(answer,), daemon=True).start()


def has_pending() -> bool:
    with _lock:
        return "item" in _pending
