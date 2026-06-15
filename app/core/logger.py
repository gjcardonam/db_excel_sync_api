"""
Application logging.

Hybrid strategy:
  * A JSON formatter writes structured logs to stdout ALWAYS (12-factor / container
    friendly). Crucially, this captures the ``extra={...}`` context that the plain
    text formatter used to drop silently.
  * An optional, fully asynchronous handler persists records to a Postgres table
    (audit trail). It runs in a background thread via QueueHandler/QueueListener so
    it never blocks request handling, and it degrades gracefully: if the log DB is
    unreachable, the app keeps running and records still reach stdout.
"""
import atexit
import json
import logging
import logging.config
import logging.handlers
import queue
from datetime import UTC, datetime
from pathlib import Path

from app.core.settings import settings

_configured = False
_listener: logging.handlers.QueueListener | None = None

# Attributes already present on a stdlib LogRecord; anything else was passed via
# ``extra=`` and should be surfaced as structured context.
_RESERVED_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
    "pathname", "process", "processName", "relativeCreated", "stack_info",
    "thread", "threadName", "taskName",
}


class SafeLogger(logging.Logger):
    """
    Logger that never raises when an ``extra={...}`` key collides with a reserved
    LogRecord attribute (e.g. ``filename``, ``module``). Colliding keys are kept
    but prefixed with ``ctx_`` instead of crashing the caller's request.
    """

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        if extra:
            safe_extra = {}
            for key, value in extra.items():
                if key in _RESERVED_ATTRS or key in ("message", "asctime"):
                    safe_extra[f"ctx_{key}"] = value
                else:
                    safe_extra[key] = value
            extra = safe_extra
        return super().makeRecord(
            name, level, fn, lno, msg, args, exc_info, func, extra, sinfo
        )


# Ensure every logger obtained via get_logger() is collision-safe.
logging.setLoggerClass(SafeLogger)


def _record_context(record: logging.LogRecord) -> dict:
    """Extract the ``extra={...}`` fields attached to a record."""
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_ATTRS and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """Render each log record as a single JSON line, including extra context."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=UTC
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = _record_context(record)
        if context:
            payload["context"] = context
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


class PostgresLogHandler(logging.Handler):
    """
    Persist log records to a Postgres table. Intended to run behind a
    QueueListener (background thread), so blocking inserts are acceptable here.

    The table is created on first use if it does not exist. Any failure is
    swallowed via ``handleError`` so logging can never take the app down.
    """

    def __init__(self, engine, table: str, level=logging.INFO):
        super().__init__(level=level)
        self._engine = engine
        self._table = table
        self._ensure_table()

    def _ensure_table(self) -> None:
        from sqlalchemy import text

        ddl = text(
            f"""
            CREATE TABLE IF NOT EXISTS {self._table} (
                id          BIGSERIAL PRIMARY KEY,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                level       VARCHAR(20),
                logger      TEXT,
                message     TEXT,
                module      TEXT,
                func        TEXT,
                line        INTEGER,
                context     JSONB,
                exc_info    TEXT
            )
            """
        )
        with self._engine.begin() as conn:
            conn.execute(ddl)

    def emit(self, record: logging.LogRecord) -> None:
        from sqlalchemy import text

        try:
            context = _record_context(record)
            exc_text = (
                self.formatException(record.exc_info) if record.exc_info else None
            )
            stmt = text(
                f"""
                INSERT INTO {self._table}
                    (created_at, level, logger, message, module, func, line, context, exc_info)
                VALUES
                    (:created_at, :level, :logger, :message, :module, :func, :line,
                     CAST(:context AS JSONB), :exc_info)
                """
            )
            with self._engine.begin() as conn:
                conn.execute(
                    stmt,
                    {
                        "created_at": datetime.fromtimestamp(
                            record.created, tz=UTC
                        ),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                        "module": record.module,
                        "func": record.funcName,
                        "line": record.lineno,
                        "context": json.dumps(context, default=str) if context else None,
                        "exc_info": exc_text,
                    },
                )
        except Exception:
            # Never let logging crash the application.
            self.handleError(record)


def _build_db_handler() -> PostgresLogHandler | None:
    """Create the Postgres log handler, or return None if unavailable/disabled."""
    if not (settings.db_logging_enabled and settings.LOG_DB_HOST):
        return None
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import URL

        url = URL.create(
            drivername="postgresql+psycopg2",
            username=settings.LOG_DB_USER,
            password=settings.LOG_DB_PASSWORD,
            host=settings.LOG_DB_HOST,
            port=settings.LOG_DB_PORT,
            database=settings.LOG_DB_NAME,
        )
        engine = create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=2)
        return PostgresLogHandler(
            engine, settings.LOG_DB_TABLE, level=settings.LOG_DB_LEVEL
        )
    except Exception:
        # Fall back to stdout-only logging; surface the reason on stderr.
        logging.getLogger(__name__).warning(
            "Database logging disabled: could not initialize log DB handler",
            exc_info=True,
        )
        return None


def setup_logging() -> None:
    """Configure application-wide logging (idempotent)."""
    global _configured, _listener
    if _configured:
        return
    _configured = True  # set early to avoid recursion via get_logger()

    json_formatter = JsonFormatter()

    # Terminal handlers that actually write somewhere.
    sink_handlers: list[logging.Handler] = []

    console = logging.StreamHandler()
    console.setFormatter(json_formatter)
    console.setLevel(settings.LOG_LEVEL)
    sink_handlers.append(console)

    if settings.LOG_TO_FILE:
        log_path = Path(settings.LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path),
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(json_formatter)
        file_handler.setLevel(settings.LOG_LEVEL)
        sink_handlers.append(file_handler)

    db_handler = _build_db_handler()
    if db_handler is not None:
        sink_handlers.append(db_handler)

    # Route records through an in-memory queue so the (potentially slow) sink
    # handlers run in a single background thread instead of the request thread.
    log_queue: queue.Queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(settings.LOG_LEVEL)
    root.addHandler(queue_handler)

    _listener = logging.handlers.QueueListener(
        log_queue, *sink_handlers, respect_handler_level=True
    )
    _listener.start()
    atexit.register(_listener.stop)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
