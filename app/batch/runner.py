import argparse

from app.batch.compute_metrics import (
    compute_drift_metrics,
    prepare_drift_output_dir,
    publish_drift_metrics,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=("prepare", "compute", "publish"),
        default="compute",
    )
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    if args.action == "prepare":
        prepare_drift_output_dir(output_dir=args.output_dir)
        return
    if args.action == "publish":
        publish_drift_metrics(run_date=args.run_date, output_dir=args.output_dir)
        return

    compute_drift_metrics(run_date=args.run_date, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
