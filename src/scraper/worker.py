"""
Celery worker entry point for running the worker via CLI.
"""


def main():
    """Start the Celery worker with configured settings."""
    from scraper.celery import app

    # Run celery worker with thread pool
    argv = [
        "worker",
        "--pool=threads",
        "--loglevel=DEBUG",
    ]

    app.worker_main(argv=argv)


if __name__ == "__main__":
    main()
