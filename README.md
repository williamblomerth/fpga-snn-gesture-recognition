# FPGA SNN Gesture Recognition #
A spiking neural network implemented on an FPGA for real-time recognition of hand gestures.

## Live webcam inference

Install the Python dependencies from this directory with
`python -m pip install -r requirements.txt`, then train a model with
`python -m software.training.train_snn_rate`. The training script saves class
names and the frame count with the weights. Start webcam inference with
`python -m software.training.live_video_test`; press `q` or Escape to exit.
Use `--weights` to select another checkpoint and `--camera` to select a
different webcam. For older weight files that contain only a state dict, also
provide `--classes` followed by the class names in training order.
