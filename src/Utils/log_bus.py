# logging_bus.py
import asyncio, json, logging, time, queue
from collections import deque
from dataclasses import dataclass
from logging.handlers import QueueHandler, QueueListener
from typing import Any, Deque, Dict, List, Optional

LEVEL_COLORS = {
    "DEBUG": "#6b7280",
    "INFO": "#2563eb",
    "WARNING": "#d97706",
    "ERROR": "#dc2626",
    "CRITICAL": "#7c3aed",
}

# Klíče v recordu, které bereme jako "standardní"
_STD_KEYS = {
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

# Extra klíče, které mohou vést k cyklům nebo gigantickým strukturám
_DANGEROUS_EXTRA = {
    "request",
    "scope",
    "environ",
    "session",
    "state",
    "headers",
    "cookies",
    "app",
    "router",
    "receive",
    "send",
    "ws",
    "websocket",
    "client",
    "server",
    "context",
}


def _clip_str(s: str, limit=5000):
    return s if len(s) <= limit else s[:limit] + f"... <clipped {len(s)-limit}B>"


def _to_jsonable(obj: Any, *, max_depth: int = 4, _seen: Optional[set] = None) -> Any:
    """Bezpečně převést libovolný objekt na JSON-serializovatelnou strukturu.
    - Omezí hloubku.
    - Detekuje cykly.
    - Ne-serializovatelné typy převádí na repr().
    """
    if _seen is None:
        _seen = set()

    # Základní primitivní typy
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj

    if isinstance(obj, str):
        return _clip_str(obj)  # ořez stringů

    oid = id(obj)
    if oid in _seen:
        return f"<recursion {type(obj).__name__}>"
    _seen.add(oid)

    if max_depth <= 0:
        return f"<truncated {type(obj).__name__}>"

    # Mappings
    if isinstance(obj, dict):
        out = {}
        for k, v in list(obj.items()):
            # klíč do str kvůli JSON
            try:
                key_str = str(k)
            except Exception:
                key_str = repr(k)
            # Vyhoďme evidentně nebezpečné větve
            if key_str in _DANGEROUS_EXTRA:
                continue
            out[key_str] = _to_jsonable(v, max_depth=max_depth - 1, _seen=_seen)
        return out

    # Iterables (list/tuple/set)
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [
            _to_jsonable(v, max_depth=max_depth - 1, _seen=_seen) for v in list(obj)
        ]

    # Dataclass-like: vem __dict__ pokud existuje
    dct = getattr(obj, "__dict__", None)
    if isinstance(dct, dict):
        return _to_jsonable(dct, max_depth=max_depth - 1, _seen=_seen)

    # Fallback: pokud projde json.dumps, vrať rovnou; jinak repr
    try:
        json.dumps(obj)
        return obj
    except Exception:
        try:
            return repr(obj)
        except Exception:
            return f"<unserializable {type(obj).__name__}>"


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
        # POZOR: nepoužívat dataclasses.asdict (dělá deepcopy)
        d: Dict[str, Any] = {
            "ts": self.ts,
            "iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.ts)),
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "module": self.module,
            "func": self.func,
            "line": self.line,
            "process": self.process,
            "thread": self.thread,
            "user_id": self.user_id,
            "req_id": self.req_id,
            "task": self.task,
            "exc_text": self.exc_text,
        }
        if self.extra:
            d["extra"] = _to_jsonable(self.extra)
        else:
            d["extra"] = None
        return d


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        exc_text = None
        if record.exc_info:
            try:
                exc_text = self.formatException(record.exc_info)
            except Exception:
                exc_text = repr(record.exc_info)

        # Zkusit zjistit jméno asyncio tasku (bezpečně)
        try:
            task = asyncio.current_task()
            task_name = task.get_name() if task else None
        except Exception:
            task_name = None

        # poskládat extra z record.__dict__ s vyřazením standardních a nebezpečných klíčů
        extra_raw = {}
        for k, v in record.__dict__.items():
            if k in _STD_KEYS or k.startswith("_"):
                continue
            if k in _DANGEROUS_EXTRA:
                continue
            extra_raw[k] = v

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
            extra=extra_raw or None,
            exc_text=exc_text,
        )

        # Serializace na JSON string
        return json.dumps(item.to_dict(), ensure_ascii=False)


class LogBus:
    def __init__(self, maxlen: int = 10000):
        self.buffer: Deque[Dict[str, Any]] = deque(maxlen=maxlen)
        # Neomezujeme, ale i tak chráníme put_nowait try/except
        self.q: asyncio.Queue = asyncio.Queue()

    def push_json(self, json_line: str):
        try:
            obj = json.loads(json_line)
        except Exception:
            obj = {
                "iso": time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": "ERROR",
                "logger": "logbus",
                "message": f"Invalid JSON log line: {json_line!r}",
            }
        self.buffer.appendleft(obj)
        try:
            self.q.put_nowait(obj)
        except asyncio.QueueFull:
            pass

    def get_last(self, n: int) -> List[Dict[str, Any]]:
        if n <= 0 or n >= len(self.buffer):
            return list(self.buffer)
        return list(self.buffer)[n:]
        # return list(self.buffer)[-n:]


LOG_BUS = LogBus()


class InMemoryHandler(logging.Handler):
    def __init__(self, formatter: logging.Formatter):
        super().__init__()
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord):
        try:
            # Pozor: LOG_BUS.push_json nesmí logovat do stejného loggeru
            LOG_BUS.push_json(self.format(record))
        except Exception:
            # Neposílat to zpátky do loggeru (vyhnout se smyčce)
            logging.Handler.handleError(self, record)


_listener: Optional[QueueListener] = None
_queue: Optional[queue.Queue] = None


def setup_logging(level=logging.INFO, use_queue: bool = False):
    global _listener, _queue
    root = logging.getLogger()
    root.setLevel(level)
    logging.raiseExceptions = False  # potlačí dumpy při selhání handleru v prod
    for h in list(root.handlers):
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
