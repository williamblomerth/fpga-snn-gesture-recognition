import tempfile
import unittest
from pathlib import Path

import torch

from software.training.live_video_test import load_model
from software.training.models.gesture_snn import GestureSNN


class LoadModelTests(unittest.TestCase):
    def test_loads_checkpoint_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "checkpoint.pth"
            model = GestureSNN(num_classes=2)
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "classes": ["stop", "wave"],
                    "num_frames": 12,
                },
                path,
            )

            loaded_model, classes, num_frames = load_model(
                path, torch.device("cpu")
            )

        self.assertEqual(classes, ["stop", "wave"])
        self.assertEqual(num_frames, 12)
        self.assertFalse(loaded_model.training)

    def test_legacy_state_dict_requires_ordered_class_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "legacy.pth"
            torch.save(GestureSNN(num_classes=2).state_dict(), path)

            with self.assertRaisesRegex(ValueError, "no class names"):
                load_model(path, torch.device("cpu"))

            _, classes, num_frames = load_model(
                path, torch.device("cpu"), ["stop", "wave"]
            )

        self.assertEqual(classes, ["stop", "wave"])
        self.assertEqual(num_frames, 32)


if __name__ == "__main__":
    unittest.main()
