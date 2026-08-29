import os
import signal
import subprocess
import sys
import time


def main() -> int:
    worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "app.celery_app:celery_app",
            "worker",
            "--loglevel",
            os.environ.get("LOG_LEVEL", "INFO"),
            "--concurrency",
            "1",
        ]
    )

    api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.http_api:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.environ.get("PORT", "7860"),
        ]
    )

    def stop_children(signum, _frame):
        for process in (api, worker):
            if process.poll() is None:
                process.send_signal(signum)

    signal.signal(signal.SIGTERM, stop_children)
    signal.signal(signal.SIGINT, stop_children)
    try:
        while True:
            api_code = api.poll()
            worker_code = worker.poll()
            if api_code is not None:
                return api_code
            if worker_code is not None:
                return worker_code
            time.sleep(1)
    finally:
        for process in (api, worker):
            if process.poll() is None:
                process.terminate()
        for process in (api, worker):
            if process.poll() is None:
                process.wait(timeout=20)


if __name__ == "__main__":
    raise SystemExit(main())
