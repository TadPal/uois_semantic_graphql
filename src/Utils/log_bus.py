# logging_bus.py
import asyncio, json, logging, time, queue
from collections import deque
from dataclasses import dataclass, asdict
from logging.handlers import QueueHandler, QueueListener
from typing import Any, Deque, Dict, List, Optional

LEVEL_COLORS = {
    "DEBUG": "#6b7280",
    "INFO": "#2563eb",
    "WARNING": "#d97706",
    "ERROR": "#dc2626",
    "CRITICAL": "#7c3aed",
}


@dataclass
class LogItem:
    ts: float
    level: str
    logger: str
    message: str
    module: str
    func: str
    line: int
    process: int
    thread: int
    user_id: Optional[str] = None
    req_id: Optional[str] = None
    task: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    exc_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["iso"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.ts))
        return d


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        exc_text = self.formatException(record.exc_info) if record.exc_info else None
        try:
            import asyncio

            task = asyncio.current_task()
            task_name = task.get_name() if task else None
        except Exception:
            task_name = None

        # extra z recordu (mimo standardní klíče)
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
            }
        } or None

        item = LogItem(
            ts=record.created,
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            module=record.module,
            func=record.funcName,
            line=record.lineno,
            process=record.process,
            thread=record.thread,
            user_id=getattr(record, "user_id", None),
            req_id=getattr(record, "req_id", None),
            task=task_name,
            extra=extra,
            exc_text=exc_text,
        )
        return json.dumps(item.to_dict(), ensure_ascii=False)


class LogBus:
    def __init__(self, maxlen: int = 10000):
        self.buffer: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        self.q: asyncio.Queue = asyncio.Queue()

    def push_json(self, json_line: str):
        try:
            obj = json.loads(json_line)
        except Exception:
            obj = {
                "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": "ERROR",
                "logger": "logbus",
                "message": f"Invalid JSON log line: {json_line}",
            }
        self.buffer.append(obj)
        try:
            self.q.put_nowait(obj)
        except asyncio.QueueFull:
            pass

    def get_last(self, n: int) -> List[Dict[str, Any]]:
        if n <= 0 or n >= len(self.buffer):
            return list(self.buffer)
        return list(self.buffer)[-n:]


LOG_BUS = LogBus()


class InMemoryHandler(logging.Handler):
    def __init__(self, formatter: logging.Formatter):
        super().__init__()
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord):
        try:
            LOG_BUS.push_json(self.format(record))
        except Exception:
            self.handleError(record)


_listener: Optional[QueueListener] = None
_queue: Optional[queue.Queue] = None


def setup_logging(level=logging.INFO, use_queue=False):
    """Call once on startup."""
    global _listener, _queue
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):  # čistý start
        root.removeHandler(h)

    fmt = JSONFormatter()

    if not use_queue:
        root.addHandler(InMemoryHandler(fmt))
        return

    _queue = queue.Queue()
    root.addHandler(QueueHandler(_queue))
    mem = InMemoryHandler(fmt)
    _listener = QueueListener(_queue, mem, respect_handler_level=True)
    _listener.start()
