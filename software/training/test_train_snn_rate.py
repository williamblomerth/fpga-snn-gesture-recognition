import tempfile
import unittest
from pathlib import Path

import torch
from PIL import Image
from torchvision import transforms

from software.training.train_snn_rate import (
    GestureClipDataset,
    sample_frame_indices,
)


class GestureClipDatasetTests(unittest.TestCase):
    def test_samples_a_clip_as_ordered_fixed_length_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            for class_name in ("wave", "stop"):
                clip_dir = root / class_name / f"{class_name}_clip"
                clip_dir.mkdir(parents=True)
                for frame_index in range(5):
                    Image.new(
                        "RGB",
                        (8, 8),
                        color=(frame_index * 40, frame_index * 40, frame_index * 40),
                    ).save(clip_dir / f"frame_{frame_index:05d}.png")

            dataset = GestureClipDataset(
                root,
                num_frames=3,
                transform=transforms.Compose(
                    [
                        transforms.Grayscale(num_output_channels=1),
                        transforms.ToTensor(),
                    ]
                ),
            )

            clip, label = dataset[0]

        self.assertEqual(len(dataset), 2)
        self.assertEqual(dataset.classes, ["stop", "wave"])
        self.assertEqual(label, dataset.class_to_idx["stop"])
        self.assertEqual(clip.shape, (3, 1, 8, 8))
        frame_values = clip[:, 0, 0, 0]
        self.assertTrue(
            torch.allclose(frame_values, torch.tensor([0, 80, 160]) / 255)
        )

    def test_uniform_sampling_handles_short_clips_and_single_frame(self) -> None:
        self.assertEqual(sample_frame_indices(5, 3), [0, 2, 4])
        self.assertEqual(sample_frame_indices(2, 4), [0, 0, 1, 1])
        self.assertEqual(sample_frame_indices(5, 1), [2])


if __name__ == "__main__":
    unittest.main()
