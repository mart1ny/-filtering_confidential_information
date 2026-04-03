import argparse

from app.infrastructure.config.settings import settings
from app.review.store import ReviewQueueStore


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-path", required=True)
    args = parser.parse_args()

    store = ReviewQueueStore(
        storage_dir=settings.review_storage_dir,
        database_url=settings.resolved_review_database_url,
    )
    store.export_labeled_dataset(args.output_path)


if __name__ == "__main__":
    main()
