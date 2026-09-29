"""One-shot container boot: converge the DB schema, then hand over to gunicorn.

Replaces `alembic upgrade head` at boot. See db_bootstrap.py for why.
Exactly ONE worker — APScheduler must run once or alerts duplicate.
"""
import sys

from app.core.db_bootstrap import bootstrap_database

if __name__ == "__main__":
    try:
        bootstrap_database()
        print("DB bootstrap OK", flush=True)
    except Exception as e:  # noqa: BLE001 — boot must not crash-loop on a transient DB blip
        print(f"DB bootstrap failed (continuing to serve; app tolerates schema drift): {e}", file=sys.stderr, flush=True)
    import os

    os.execvp(
        "gunicorn",
        [
            "gunicorn",
            "app.main:app",
            "-k",
            "uvicorn.workers.UvicornWorker",
            "-w",
            "1",
            "-b",
            "0.0.0.0:8000",
            "--timeout",
            "120",
        ],
    )
