"""
Celery worker entry point for running the worker via CLI.
"""

from conf import get_celery_worker_log_level


def main():
    """Start the Celery worker with configured settings."""
    from scraper.celery import app

    # Run celery worker with thread pool
    argv = [
        "worker",
        "--pool=threads",
        f"--loglevel={get_celery_worker_log_level()}",
    ]

    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
