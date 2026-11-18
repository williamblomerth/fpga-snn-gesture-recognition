"""Classify live webcam gestures with a trained gesture SNN."""
import argparse
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path

import cv2
import torch
from PIL import Image
from torchvision import transforms

from software.training.models.gesture_snn import GestureSNN


DEFAULT_NUM_FRAMES = 32
DEFAULT_WEIGHTS = (
    Path(__file__).resolve().parents[1] / "models" / "gesture_snn_rate.pth"
)


def load_model(
    weights_path: Path,
    device: torch.device,
    class_names: Sequence[str] | None = None,
) -> tuple[GestureSNN, list[str], int]:
    """Load a current metadata checkpoint or a legacy state-dict checkpoint."""
    checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
    if not isinstance(checkpoint, Mapping):
        raise ValueError(f"Unsupported checkpoint format: {weights_path}")

    if "model_state_dict" in checkpoint:
        state_dict = checkpoint["model_state_dict"]
        saved_classes = checkpoint.get("classes")
        num_frames = checkpoint.get("num_frames", DEFAULT_NUM_FRAMES)
        if not isinstance(saved_classes, list) or not all(
            isinstance(name, str) and name for name in saved_classes
        ):
            raise ValueError("Checkpoint is missing valid gesture class names")
        if class_names is not None and list(class_names) != saved_classes:
            raise ValueError(
                "The supplied class names do not match the checkpoint metadata"
            )
        class_names = saved_classes
    else:
        state_dict = checkpoint
        num_frames = DEFAULT_NUM_FRAMES
        if class_names is None:
            raise ValueError(
                "This older checkpoint has no class names. Provide them with "
                "--classes in the order used during training."
            )

    if not isinstance(state_dict, Mapping):
        raise ValueError("Checkpoint model_state_dict must be a mapping")
    output_weights = state_dict.get("fc2.weight")
    if not isinstance(output_weights, torch.Tensor) or output_weights.ndim != 2:
        raise ValueError("Checkpoint does not contain valid fc2 output weights")
    if (
        not isinstance(num_frames, int)
        or isinstance(num_frames, bool)
        or num_frames < 1
    ):
        raise ValueError("Checkpoint num_frames must be a positive integer")
    if class_names is None:
        raise ValueError("Gesture class names are required")
    if len(class_names) != output_weights.shape[0]:
        raise ValueError(
            f"Checkpoint has {output_weights.shape[0]} output classes but "
            f"{len(class_names)} class names were provided"
        )

    model = GestureSNN(num_classes=len(class_names)).to(device)
    model.load_state_dict(state_dict)
    model.eval()
    return model, list(class_names), num_frames


def preprocess_frame(frame, transform) -> torch.Tensor:
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return transform(Image.fromarray(rgb_frame))


def classify_window(
    model: GestureSNN,
    frames: Sequence[torch.Tensor],
    device: torch.device,
) -> tuple[int | None, float]:
    clip = torch.stack(list(frames)).flatten(start_dim=1).unsqueeze(1).to(device)
    with torch.inference_mode():
        spikes = model(clip, num_steps=len(frames)).sum(dim=0).squeeze(0)
    total_spikes = spikes.sum().item()
    if total_spikes == 0:
        return None, 0.0
    prediction = int(spikes.argmax().item())
    return prediction, float(spikes[prediction].item() / total_spikes)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--weights",
        type=Path,
        default=DEFAULT_WEIGHTS,
        help="Checkpoint produced by train_snn_rate.py.",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="Webcam device index (default: 0).",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        help="Ordered class names, required only for older state-dict checkpoints.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model, classes, num_frames = load_model(args.weights, device, args.classes)
    transform = transforms.Compose(
        [
            transforms.Grayscale(num_output_channels=1),
            transforms.Resize((32, 32)),
            transforms.ToTensor(),
            transforms.Normalize((0,), (1,)),
        ]
    )

    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"Could not open webcam device {args.camera}")

    frame_window: deque[torch.Tensor] = deque(maxlen=num_frames)
    try:
        while True:
            success, frame = camera.read()
            if not success:
                raise RuntimeError("Could not read a frame from the webcam")
            frame_window.append(preprocess_frame(frame, transform))

            if len(frame_window) == num_frames:
                prediction, confidence = classify_window(
                    model, list(frame_window), device
                )
                if prediction is None:
                    label = "No spikes"
                else:
                    label = f"{classes[prediction]} ({confidence:.0%})"
            else:
                label = f"Collecting frames: {len(frame_window)}/{num_frames}"

            cv2.putText(
                frame,
                label,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.imshow("Live Gesture Recognition", frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()