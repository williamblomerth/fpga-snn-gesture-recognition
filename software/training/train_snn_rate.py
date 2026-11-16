"""Rate-encoding training for the gesture SNN."""
import argparse
import time
from collections.abc import Callable
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from snntorch import spikegen
import snntorch.functional as SF
from software.training.models.gesture_snn import GestureSNN

LOG_PATH = "software/log/gesture_snn_rate_training_log.txt"
with open(LOG_PATH, "w", encoding="utf-8") as file:
    file.write("Gesture SNN Rate Training Output Log\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        default="/project/ece601/EEG_ALS/jester/jester_preprocessed/train/",
        help="ImageFolder root containing the training images.",
    )
    parser.add_argument(
        "--validation-root",
        default="/project/ece601/EEG_ALS/jester/jester_preprocessed/validation/",
        help=(
            "ImageFolder root for validation; defaults to a sibling "
            "'validation' directory next to --data-root."
        ),
    )
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=32,
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
    if args.epochs < 1 or args.batch_size < 1 or args.num_steps < 1:
        parser.error("--epochs, --batch-size, and --num-steps must be > 0")
    if args.num_workers < 0:
        parser.error("--num-workers must be non-negative")
    return args


def evaluate(
    model: GestureSNN,
    data_loader: DataLoader,
    criterion: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
    device: torch.device,
    num_steps: int,
) -> tuple[float, float]:
    model.eval()
    total_loss = torch.zeros((), device=device)
    total_correct = torch.zeros((), device=device)
    total_images = 0

    with torch.no_grad():
        for images, labels in data_loader:
            images = images.flatten(start_dim=1).to(device)
            labels = labels.to(device)
            spike_data = spikegen.rate(images, num_steps=num_steps)
            spk_rec = model(spike_data, num_steps=num_steps)
            loss = criterion(spk_rec, labels).squeeze()

            batch_size = labels.size(0)
            predictions = spk_rec.sum(dim=0).argmax(dim=1)
            total_loss += loss * batch_size
            total_correct += (predictions == labels).sum()
            total_images += batch_size

    return (
        (total_loss / total_images).item(),
        (total_correct / total_images).item(),
    )


def main() -> None:
    args = parse_args()
    transform = transforms.Compose(
        [
            transforms.Grayscale(num_output_channels=1),
            transforms.ToTensor(),
            transforms.Normalize((0,), (1,)),
        ]
    )
    train_dataset = datasets.ImageFolder(
        root=args.data_root,
        transform=transform,
    )
    validation_root = (
        Path(args.validation_root)
        if args.validation_root
        else Path(args.data_root).parent / "validation"
    )
    validation_dataset = datasets.ImageFolder(
        root=validation_root,
        transform=transform,
    )
    if not validation_dataset:
        raise ValueError(f"No validation images found in {validation_root}")
    if train_dataset.class_to_idx != validation_dataset.class_to_idx:
        raise ValueError(
            "Training and validation class mappings differ. Ensure both "
            "ImageFolder directories contain the same class subdirectories."
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
    validation_loader = DataLoader(
        validation_dataset,
        **{**loader_options, "shuffle": False},
    )

    model = GestureSNN(num_classes=len(train_dataset.classes)).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = SF.ce_rate_loss()

    print(
        f"Device: {device}; images: {len(train_dataset)}; "
        f"validation images: {len(validation_dataset)}; "
        f"classes: {len(train_dataset.classes)}; workers: {args.num_workers}"
    )
    with open(LOG_PATH, "a", encoding="utf-8") as file:
        file.write(f"Device: {device}; images: {len(train_dataset)}; ")
        file.write(f"validation images: {len(validation_dataset)}; ")
        file.write(f"classes: {len(train_dataset.classes)}; workers: {args.num_workers}\n")
    for epoch in range(args.epochs):
        epoch_started = time.perf_counter()
        model.train()
        total_loss = torch.zeros((), device=device)
        total_images = 0
        for images, labels in train_loader:
            images = images.flatten(start_dim=1).to(
                device, non_blocking=pin_memory
            )
            labels = labels.to(device, non_blocking=pin_memory)
            spike_data = spikegen.rate(images, num_steps=args.num_steps)
            spk_rec = model(spike_data, num_steps=args.num_steps)
            loss = criterion(spk_rec, labels).squeeze()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()

            batch_size = labels.size(0)
            total_loss += loss.detach() * batch_size
            total_images += batch_size

        if device.type == "cuda":
            torch.cuda.synchronize(device)
        elapsed = time.perf_counter() - epoch_started
        mean_loss = (total_loss / total_images).item()
        print(
            f"Epoch {epoch + 1}/{args.epochs} "
            f"Loss: {mean_loss:.4f} "
            f"Time: {elapsed / 60:.1f} min "
            f"Images/sec: {total_images / elapsed:.1f}"
        )
        with open(LOG_PATH, "a", encoding="utf-8") as file:
            file.write(f"Epoch {epoch + 1}/{args.epochs} ")
            file.write(f"Loss: {mean_loss:.4f} ")
            file.write(f"Time: {elapsed / 60:.1f} min ")
            file.write(f"Images/sec: {total_images / elapsed:.1f}\n")
        validation_started = time.perf_counter()
        validation_loss, validation_accuracy = evaluate(
            model,
            validation_loader,
            criterion,
            device,
            args.num_steps,
        )
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        validation_elapsed = time.perf_counter() - validation_started
        print(
            f"Validation Loss: {validation_loss:.4f} "
            f"Accuracy: {validation_accuracy:.2%} "
            f"Time: {validation_elapsed / 60:.1f} min"
        )
        with open(LOG_PATH, "a", encoding="utf-8") as file:
            file.write(f"Validation Loss: {validation_loss:.4f} ")
            file.write(f"Accuracy: {validation_accuracy:.2%} ")
            file.write(f"Time: {validation_elapsed / 60:.1f} min\n")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_path)
    print(f"Saved model weights to {output_path}")
    with open(LOG_PATH, "a", encoding="utf-8") as file:
        file.write(f"Saved model weights to {output_path}")


if __name__ == "__main__":
    main()
