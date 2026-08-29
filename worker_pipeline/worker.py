from app.celery_app import celery_app
from app.config import settings
from app.logging_config import configure_logging


configure_logging()


if __name__ == "__main__":
    celery_app.worker_main(
        [
            "worker",
            "--loglevel",
            settings.log_level,
            "--queues",
            settings.queue_name,
            "--concurrency",
            "1",
        ]
    )
