import argparse
import csv
from pathlib import Path

from PIL import Image
from torchvision import transforms


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def read_annotations(annotation_file: Path) -> list[tuple[str, str]]:
    with annotation_file.open("r", encoding="utf-8-sig", newline="") as file:
        sample = file.read(4096)
        file.seek(0)
        delimiter = ";" if ";" in sample else ","
        rows = list(csv.reader(file, delimiter=delimiter))

    annotations = []
    seen_video_ids = set()
    for row_number, row in enumerate(rows, start=1):
        if not row or not any(field.strip() for field in row):
            continue
        if row_number == 1 and len(row) >= 2 and row[0].strip().lower() in {
            "video_id",
            "video",
            "id",
        }:
            continue
        if len(row) < 2:
            raise ValueError(
                f"{annotation_file}:{row_number}: expected a video ID "
                "and label"
            )

        video_id, label = row[0].strip(), row[1].strip()
        if not video_id or not label:
            raise ValueError(
                f"{annotation_file}:{row_number}: video ID and label "
                "must not be empty"
            )
        if Path(video_id).name != video_id or video_id in {".", ".."}:
            raise ValueError(
                f"{annotation_file}:{row_number}: invalid video ID "
                f"{video_id!r}"
            )
        if video_id in seen_video_ids:
            raise ValueError(
                f"{annotation_file}:{row_number}: duplicate video ID "
                f"{video_id!r}"
            )

        seen_video_ids.add(video_id)
        annotations.append((video_id, label))

    if not annotations:
        raise ValueError(f"No labeled videos found in {annotation_file}")
    return annotations


def preprocess_dataset(
    input_dir: Path,
    annotation_file: Path,
    output_dir: Path,
    split: str,
) -> tuple[int, int]:
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Frame directory does not exist: {input_dir}")
    if Path(split).name != split or split in {".", ".."}:
        raise ValueError(f"Invalid split name: {split!r}")

    annotation_rows = read_annotations(annotation_file)
    transform = transforms.Compose(
        [
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((32, 32)),
        ]
    )

    processed_clips = 0
    processed_images = 0
    for video_id, label in annotation_rows:
        clip_dir = input_dir / video_id
        if not clip_dir.is_dir():
            raise FileNotFoundError(
                f"No extracted-frame directory for video {video_id!r}: "
                f"{clip_dir}"
            )

        frame_paths = sorted(
            path
            for path in clip_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
        if not frame_paths:
            raise FileNotFoundError(f"No image frames found in {clip_dir}")

        class_name = label.replace("/", "_").replace("\\", "_").strip()
        if not class_name or class_name in {".", ".."}:
            raise ValueError(
                f"Invalid class label for video {video_id!r}: {label!r}"
            )
        class_dir = output_dir / split / class_name / video_id
        class_dir.mkdir(parents=True, exist_ok=True)

        for frame_index, frame_path in enumerate(frame_paths):
            with Image.open(frame_path) as frame:
                processed = transform(frame)
                processed.save(class_dir / f"frame_{frame_index:05d}.png")

        processed_clips += 1
        processed_images += len(frame_paths)

    return processed_clips, processed_images


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert extracted Jester video frames into labeled 32x32 "
            "grayscale PNGs suitable for loading with "
            "torchvision.datasets.ImageFolder."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/jester"),
        help=(
            "Directory containing one extracted-frame subdirectory per video."
        ),
    )
    parser.add_argument(
        "--annotations",
        type=Path,
        default=Path("data/jester-v1-train.csv"),
        help="Jester annotation CSV with video ID and gesture label columns.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/jester_preprocessed"),
        help="Root directory for the preprocessed dataset.",
    )
    parser.add_argument(
        "--split",
        default="train",
        help="Output split directory name (for example, train or validation).",
    )
    args = parser.parse_args()

    clips, images = preprocess_dataset(
        args.input_dir, args.annotations, args.output_dir, args.split
    )
    print(
        f"Processed {images} frames from {clips} clips into "
        f"{args.output_dir / args.split}"
    )


if __name__ == "__main__":
    main()
