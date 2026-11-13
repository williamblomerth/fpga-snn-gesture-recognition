import torch
import torch.nn as nn
import snntorch as snn
from snntorch import surrogate

# Define surrogate gradient for LIF activation
spike_grad = surrogate.fast_sigmoid(slope=25)
BETA = 0.5 # Decay factor for LIF neurons


# Build a 2-layer SNN Architecture
class GestureSNN(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        # Input layer: 32x32 = 1024 downsampled pixels -> 128 hidden neurons
        self.fc1 = nn.Linear(1024, 128)
        self.lif1 = snn.Leaky(beta=BETA, spike_grad=spike_grad)

        # Output layer: 128 hidden neurons -> num_classes gesture classes
        self.fc2 = nn.Linear(128, num_classes)
        self.lif2 = snn.Leaky(beta=BETA, spike_grad=spike_grad)

    def forward(self, x, num_steps=32):
        # Initialize membrane potentials
        mem1 = self.lif1.reset_mem()
        mem2 = self.lif2.reset_mem()

        spk2_rec = []  # Record output spikes

        # Batch this transform because inputs are known for all steps.
        cur1_rec = self.fc1(x)
        for step in range(num_steps):
            spk1, mem1 = self.lif1(cur1_rec[step], mem1)
            cur2 = self.fc2(spk1)
            spk2, mem2 = self.lif2(cur2, mem2)
            spk2_rec.append(spk2)

        return torch.stack(spk2_rec, dim=0)  # [T, Batch, Classes]
