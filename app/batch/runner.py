import argparse

from app.batch.compute_metrics import compute_drift_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    compute_drift_metrics(run_date=args.run_date, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
