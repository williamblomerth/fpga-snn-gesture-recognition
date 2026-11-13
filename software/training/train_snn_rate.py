"""Train the gesture SNN on ordered frame sequences from video clips."""
import argparse
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
import snntorch.functional as SF
from software.training.models.gesture_snn import GestureSNN

LOG_PATH = Path("software/log/gesture_snn_rate_training_log.txt")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def sample_frame_indices(frame_count: int, num_frames: int) -> list[int]:
    if frame_count < 1:
        raise ValueError("A clip must contain at least one frame")
    if num_frames < 1:
        raise ValueError("num_frames must be greater than zero")
    if num_frames == 1:
        return [(frame_count - 1) // 2]
    return [
        round(index * (frame_count - 1) / (num_frames - 1))
        for index in range(num_frames)
    ]


class GestureClipDataset(Dataset):
    """Load each class/video directory as one ordered, fixed-length sample."""

    def __init__(
        self,
        root: str | Path,
        num_frames: int,
        transform: Callable[[Image.Image], torch.Tensor],
    ) -> None:
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f"Dataset directory does not exist: {self.root}")
        if num_frames < 1:
            raise ValueError("num_frames must be greater than zero")

        self.num_frames = num_frames
        self.transform = transform
        self.classes = sorted(
            path.name for path in self.root.iterdir() if path.is_dir()
        )
        if not self.classes:
            raise ValueError(f"No class directories found in {self.root}")
        self.class_to_idx = {
            class_name: index for index, class_name in enumerate(self.classes)
        }
        self.samples: list[tuple[list[Path], int]] = []
        self.clip_ids: set[str] = set()

        for class_name in self.classes:
            class_dir = self.root / class_name
            clip_dirs = sorted(path for path in class_dir.iterdir() if path.is_dir())
            for clip_dir in clip_dirs:
                frame_paths = sorted(
                    path
                    for path in clip_dir.iterdir()
                    if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
                )
                if not frame_paths:
                    raise ValueError(
                        f"No image frames found in clip directory {clip_dir}"
                    )
                self.samples.append((frame_paths, self.class_to_idx[class_name]))
                self.clip_ids.add(clip_dir.name)

        if not self.samples:
            raise ValueError(
                f"No video clips found in {self.root}; expected "
                "class/video_id/frame images"
            )
        self.targets = [label for _, label in self.samples]

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        frame_paths, label = self.samples[index]
        indices = sample_frame_indices(len(frame_paths), self.num_frames)
        frames = []
        for frame_index in indices:
            with Image.open(frame_paths[frame_index]) as image:
                frames.append(self.transform(image.convert("RGB")))
        return torch.stack(frames), label


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        default="/project/ece601/EEG_ALS/jester/jester_preprocessed/train/",
        help="Root with class/video_id/frame image directories for training.",
    )
    parser.add_argument(
        "--validation-root",
        default="/project/ece601/EEG_ALS/jester/jester_preprocessed/validation/",
        help=(
            "Root with class/video_id/frame image directories for validation."
        ),
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--num-frames",
        "--num-steps",
        dest="num_frames",
        type=int,
        default=32,
        help="Ordered frames sampled from each clip and processed by the SNN.",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help=(
            "DataLoader worker processes; use 0 if workers hurt "
            "shared-filesystem performance."
        ),
    )
    parser.add_argument(
        "--output",
        default="software/models/gesture_snn_rate.pth",
        help="Path for the trained model weights.",
    )
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.num_frames < 1:
        parser.error("--epochs, --batch-size, and --num-frames must be > 0")
    if args.num_workers < 0:
        parser.error("--num-workers must be non-negative")
    return args


def evaluate(
    model: GestureSNN,
    data_loader: DataLoader,
    criterion: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    device: torch.device,
    num_frames: int,
) -> tuple[float, float]:
    model.eval()
    total_loss = torch.zeros((), device=device)
    total_correct = torch.zeros((), device=device)
    total_clips = 0

    with torch.no_grad():
        for clips, labels in data_loader:
            clips = clips.permute(1, 0, 2, 3, 4).flatten(start_dim=2).to(device)
            labels = labels.to(device)
            spk_rec = model(clips, num_steps=num_frames)
            loss = criterion(spk_rec, labels).squeeze()

            batch_size = labels.size(0)
            predictions = spk_rec.sum(dim=0).argmax(dim=1)
            total_loss += loss * batch_size
            total_correct += (predictions == labels).sum()
            total_clips += batch_size

    return (
        (total_loss / total_clips).item(),
        (total_correct / total_clips).item(),
    )


def main() -> None:
    args = parse_args()
    transform = transforms.Compose(
        [
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((32, 32)),
            transforms.ToTensor(),
            transforms.Normalize((0,), (1,)),
        ]
    )
    train_dataset = GestureClipDataset(
        root=args.data_root,
        num_frames=args.num_frames,
        transform=transform,
    )
    validation_root = (
        Path(args.validation_root)
        if args.validation_root
        else Path(args.data_root).parent / "validation"
    )
    validation_dataset = GestureClipDataset(
        root=validation_root,
        num_frames=args.num_frames,
        transform=transform,
    )
    if train_dataset.class_to_idx != validation_dataset.class_to_idx:
        raise ValueError(
            "Training and validation class mappings differ. Ensure both "
            "directories contain the same class subdirectories."
        )
    overlapping_clips = train_dataset.clip_ids & validation_dataset.clip_ids
    if overlapping_clips:
        examples = ", ".join(sorted(overlapping_clips)[:5])
        raise ValueError(
            "Training and validation contain clips with the same video IDs "
            f"(for example: {examples})"
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pin_memory = device.type == "cuda"
    loader_options = {
        "batch_size": args.batch_size,
        "shuffle": True,
        "num_workers": args.num_workers,
        "pin_memory": pin_memory,
    }
    if args.num_workers > 0:
        loader_options["persistent_workers"] = True
        loader_options["prefetch_factor"] = 2
    train_loader = DataLoader(
        train_dataset,
        **loader_options,
    )
    train_eval_loader = DataLoader(
        train_dataset,
        **{**loader_options, "shuffle": False},
    )
    validation_loader = DataLoader(
        validation_dataset,
        **{**loader_options, "shuffle": False},
    )

    model = GestureSNN(num_classes=len(train_dataset.classes)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = SF.ce_rate_loss()
    train_class_counts = Counter(train_dataset.targets)
    majority_class = max(
        range(len(train_dataset.classes)),
        key=lambda class_index: train_class_counts[class_index],
    )
    majority_baseline = sum(
        label == majority_class for label in validation_dataset.targets
    ) / len(validation_dataset)

    print(
        f"Device: {device}; clips: {len(train_dataset)}; "
        f"validation clips: {len(validation_dataset)}; "
        f"classes: {len(train_dataset.classes)}; workers: {args.num_workers}; "
        f"frames per clip: {args.num_frames}"
    )
    print(
        f"Validation majority-class baseline "
        f"({train_dataset.classes[majority_class]}): {majority_baseline:.2%}"
    )
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8") as file:
        file.write("Gesture SNN Clip Training Output Log\n")
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"Device: {device}; clips: {len(train_dataset)}; ")
        file.write(f"validation clips: {len(validation_dataset)}; ")
        file.write(
            f"classes: {len(train_dataset.classes)}; workers: {args.num_workers}; "
            f"frames per clip: {args.num_frames}\n"
        )
        file.write(
            f"Validation majority-class baseline: {majority_baseline:.2%}\n"
        )
    for epoch in range(args.epochs):
        epoch_started = time.perf_counter()
        model.train()
        total_loss = torch.zeros((), device=device)
        total_clips = 0
        for clips, labels in train_loader:
            clips = clips.permute(1, 0, 2, 3, 4).flatten(start_dim=2).to(
                device, non_blocking=pin_memory
            )
            labels = labels.to(device, non_blocking=pin_memory)
            spk_rec = model(clips, num_steps=args.num_frames)
            loss = criterion(spk_rec, labels).squeeze()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()

            batch_size = labels.size(0)
            total_loss += loss.detach() * batch_size
            total_clips += batch_size

        if device.type == "cuda":
            torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - epoch_started
        print(
            f"Epoch {epoch + 1}/{args.epochs} "
            f"Optimization loss: {(total_loss / total_clips).item():.4f} "
            f"Time: {elapsed / 60:.1f} min "
            f"Clips/sec: {total_clips / elapsed:.1f}"
        )
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(f"Epoch {epoch + 1}/{args.epochs} ")
            file.write(
                f"Optimization loss: {(total_loss / total_clips).item():.4f} "
            )
            file.write(f"Time: {elapsed / 60:.1f} min ")
            file.write(f"Clips/sec: {total_clips / elapsed:.1f}\n")

        train_eval_started = time.perf_counter()
        train_loss, train_accuracy = evaluate(
            model,
            train_eval_loader,
            criterion,
            device,
            args.num_frames,
        )
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        train_eval_elapsed = time.perf_counter() - train_eval_started
        print(
            f"Training Loss: {train_loss:.4f} "
            f"Accuracy: {train_accuracy:.2%} "
            f"Evaluation time: {train_eval_elapsed / 60:.1f} min"
        )
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(f"Training Loss: {train_loss:.4f} ")
            file.write(f"Accuracy: {train_accuracy:.2%} ")
            file.write(
                f"Evaluation time: {train_eval_elapsed / 60:.1f} min\n"
            )

        validation_started = time.perf_counter()
        validation_loss, validation_accuracy = evaluate(
            model,
            validation_loader,
            criterion,
            device,
            args.num_frames,
        )
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        validation_elapsed = time.perf_counter() - validation_started
        print(
            f"Validation Loss: {validation_loss:.4f} "
            f"Accuracy: {validation_accuracy:.2%} "
            f"Majority baseline: {majority_baseline:.2%} "
            f"Time: {validation_elapsed / 60:.1f} min"
        )
        with LOG_PATH.open("a", encoding="utf-8") as file:
            file.write(f"Validation Loss: {validation_loss:.4f} ")
            file.write(f"Accuracy: {validation_accuracy:.2%} ")
            file.write(f"Majority baseline: {majority_baseline:.2%} ")
            file.write(f"Time: {validation_elapsed / 60:.1f} min\n")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)
    print(f"Saved model weights to {output_path}")
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(f"Saved model weights to {output_path}")


if __name__ == "__main__":
    main()
