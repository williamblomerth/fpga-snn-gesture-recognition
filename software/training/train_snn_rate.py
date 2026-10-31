# don't run this yet, no storage space on SCC, dataset needs to be extracted
# python3 -m software.training.train_snn_rate
""" Rate Encoding Training method
    Run this on SCC to access dataset stored there."""
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from snntorch import spikegen
import snntorch as snn
import snntorch.functional as SF
from software.training.models.gesture_snn import GestureSNN

# 1. Define Image Transformations (already preprocessed to 32x32 grayscale)
transform = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),  # Ensure single channel
    transforms.ToTensor(),  # Scales pixel values to [0.0, 1.0]
    transforms.Normalize((0,), (1,))
])

# 2. Load Dataset (e.g., ImageFolder containing gesture subfolders)
# Directory structure: data/jester_preprocessed/train/Drumming Fingers/, etc.
# train_dataset = datasets.ImageFolder(root='/project/ece601/EEG_ALS/jester/', transform=transform)  # for SCC user
train_dataset = datasets.ImageFolder(root='data/jester_preprocessed/train/', transform=transform)  # for local training
train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)

# 3. Model Training Loop
num_steps = 32  # T = 32 timesteps
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = GestureSNN(num_classes=len(train_dataset.classes)).to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)  # Adam: adaptation of stochastic gradient descent, has become default for training deep NNs
criterion = SF.ce_rate_loss()  # Cross-entropy loss based on spike counts

for epoch in range(10):
    for images, labels in train_loader:
        # images shape: [Batch_Size, 1, 32, 32]

        # Flatten image to match 1024 input nodes (32*32)
        images = images.view(images.size(0), -1).to(device)  # Shape: [Batch_Size, 1024]

        # Convert static images into 1-bit Rate Encoded Spikes
        # Output shape: [num_steps, Batch_Size, 1024]
        spike_data = spikegen.rate(images, num_steps=num_steps)

        # Forward pass through the SNN
        spk_rec = model(spike_data, num_steps=num_steps)  # Output shape: [num_steps, Batch_Size, Classes]

        # Compute loss & backpropagate
        loss = criterion(spk_rec, labels.to(device))
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    print(f"Epoch {epoch+1} Loss: {loss.item():.4f}")

torch.save(model.state_dict(), "software/models/gesture_snn_rate.pth")
