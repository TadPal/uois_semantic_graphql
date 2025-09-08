# mcp_servers/http_log.py
import logging, os, requests


class HttpLogHandler(logging.Handler):
    def __init__(self, sink_url: str | None = None, timeout: float = 0.3):
        super().__init__()
        self.sink_url = sink_url or os.getenv("LOG_SINK_URL")
        self.timeout = timeout

    def emit(self, record: logging.LogRecord):
        if not self.sink_url:
            return
        try:
            payload = {
                "logger": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "func": record.funcName,
                "line": record.lineno,
                "process": record.process,
                "thread": record.thread,
                "extra": {
                    k: v
                    for k, v in record.__dict__.items()
                    if k
                    not in (
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
                    )
                },
            }
            requests.post(self.sink_url, json=payload, timeout=self.timeout)
        except Exception:
            pass


def setup_remote_logging(sink_url: str | None = None):
    # root + uvicorn budou propagovat do handleru
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    root.addHandler(sh)

    root.addHandler(HttpLogHandler(sink_url))

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        lg = logging.getLogger(name)
        lg.propagate = True
        lg.setLevel(logging.INFO)
