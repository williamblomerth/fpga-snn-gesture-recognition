"""Remove selected gesture classes from one or more Jester label CSV files."""
import argparse
import csv
import os
import stat
import tempfile
from pathlib import Path


EXCLUDED_CLASSES = {
    "Drumming Fingers",
    "Pulling Hand In",
    "Pulling Two Fingers In",
    "Pushing Hand Away",
    "Pushing Two Fingers Away",
    "Rolling Hand Backward",
    "Rolling Hand Forward",
    "Shaking Hand",
    "Turning Hand Clockwise",
    "Turning Hand Counterclockwise",
}
EXCLUDED_CLASSES_NORMALIZED = {label.casefold() for label in EXCLUDED_CLASSES}
HEADER_NAMES = {"video_id", "video", "id"}


def filter_csv(csv_path: Path, in_place: bool) -> tuple[Path, int, int]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    output_path = (
        csv_path
        if in_place
        else csv_path.with_name(f"{csv_path.stem}.filtered{csv_path.suffix}")
    )
    if not in_place and output_path.exists():
        raise FileExistsError(
            f"Filtered output already exists: {output_path}. "
            "Remove it or choose another input filename."
        )

    with csv_path.open("rb") as source:
        has_bom = source.read(3) == b"\xef\xbb\xbf"
    encoding = "utf-8-sig" if has_bom else "utf-8"
    temporary_path: Path | None = None
    kept_rows = 0
    removed_rows = 0

    try:
        with csv_path.open("r", encoding=encoding, newline="") as source:
            sample = source.read(4096)
            source.seek(0)
            delimiter = ";" if ";" in sample else ","
            reader = csv.reader(source, delimiter=delimiter)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding=encoding,
                newline="",
                dir=csv_path.parent,
                prefix=f".{csv_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                writer = csv.writer(
                    temporary,
                    delimiter=delimiter,
                    lineterminator="\n",
                )
                for row_number, row in enumerate(reader, start=1):
                    if not row or not any(field.strip() for field in row):
                        writer.writerow(row)
                        continue
                    if row_number == 1 and len(row) >= 2 and (
                        row[0].strip().casefold() in HEADER_NAMES
                    ):
                        writer.writerow(row)
                        continue
                    if len(row) < 2:
                        raise ValueError(
                            f"{csv_path}:{row_number}: expected a video ID "
                            "and label column"
                        )
                    label = row[1].strip().casefold()
                    if label in EXCLUDED_CLASSES_NORMALIZED:
                        removed_rows += 1
                        continue
                    writer.writerow(row)
                    kept_rows += 1

        source_mode = stat.S_IMODE(csv_path.stat().st_mode)
        os.chmod(temporary_path, source_mode)
        os.replace(temporary_path, output_path)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return output_path, kept_rows, removed_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_files",
        nargs="+",
        type=Path,
        help="Label CSV files to filter (shell wildcards are supported).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Replace each input CSV instead of writing a .filtered copy.",
    )
    args = parser.parse_args()

    for csv_path in args.csv_files:
        output_path, kept_rows, removed_rows = filter_csv(
            csv_path,
            in_place=args.in_place,
        )
        print(
            f"{csv_path}: kept {kept_rows} rows, removed {removed_rows}; "
            f"wrote {output_path}"
        )


if __name__ == "__main__":
    main()