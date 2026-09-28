"""Structured logging setup."""
import logging
import sys


def configure_logging() -> None:
    # Windows consoles and redirected pipes default to cp1252, where any emoji
    # in a log payload (chat titles carry one, so do LLM answers) raises
    # UnicodeEncodeError *inside* the handler. The handler then prints the
    # encoding error instead of the real traceback, hiding the actual fault.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):  # pragma: no cover - exotic streams
            pass

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
