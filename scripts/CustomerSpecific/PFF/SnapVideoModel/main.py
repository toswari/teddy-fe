import pandas as pd
import os
import random
from typing import Iterator, Tuple, Dict, List
import glob
import cv2
import torch
from torch.utils.data import IterableDataset
import numpy as np
import argparse
import torchvision as tv
import json
import sys

def generate_frame_quads(root_directory: str, csv_path: str, fps: int = 30, 
                           clip_length: int = 8) -> Iterator[Tuple[str, int, int]]:
    """
    Generate triplets of (path, start_frame, end_frame) for video clips.
    
    Args:
        root_directory: Root directory containing video files
        csv_path: Path to CSV with game_id, play_id, snap_time columns
        fps: Frames per second (default: 30)
        clip_length: Length of clip in frames (default: 8)
    
    Yields:
        Tuple of (video_path, start_frame, end_frame)
    """
    # Preload available videos indexed by play_id
    video_index = _build_video_index(root_directory)
    
    # Load CSV data
    df = pd.read_csv(csv_path)
    
    for _, row in df.iterrows():
        play_id = str(row['play_id'])
        snap_time = float(row['snap_time'].split(':')[0]) * 60 + float(row['snap_time'].split(':')[1])
        
        # Check if videos exist for this play_id
        if play_id not in video_index:
            print(f"No videos found for play_id {play_id}, skipping.")
            continue
            
        # Get all available videos for this play_id
        video_path = video_index[play_id]
        
        # Calculate snap frame
        snap_frame = int(snap_time * fps)

        # If start_frame and end_frame are provided, use them directly
        if 'start_frame' in row and 'end_frame' in row:
            start_frame = int(row['start_frame'])
            end_frame = int(row['end_frame'])
            yield (video_path, start_frame, end_frame, 1 if snap_frame >= start_frame and snap_frame <= end_frame else 0, snap_frame)
            continue
        
        # Generate random offset to shift the start frame
        max_offset = clip_length // 2
        random_offset = random.randint(-max_offset, max_offset)
        
        start_frame = max(0, snap_frame - clip_length // 2 + random_offset)
        end_frame = start_frame + clip_length

        cap = cv2.VideoCapture(video_path)
        try:
            video_end = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            cap.release()

        if random.random() < 0.5:
            non_snap_end = random.randint(clip_length, max(clip_length, snap_frame - 1))
            non_snap_start = non_snap_end - clip_length
        else:
            non_snap_start = random.randint(snap_frame + 1, video_end - clip_length)
            non_snap_end = non_snap_start + clip_length

        yield (video_path, start_frame, end_frame, 1, snap_frame)
        yield (video_path, non_snap_start, non_snap_end, 0, snap_frame)

        # Generate additional non-snap quadruplets for the same videos
def _build_video_index(root_directory: str) -> Dict[str, str]:
    """
    Build an index of videos by play_id.
    
    Args:
        root_directory: Root directory containing video files
        
    Returns:
        Dictionary mapping play_id to list of video paths
    """
    video_index = {}
    
    # Find all MP4 files matching the pattern
    pattern = "*_*_*_*_*.mp4"
    video_files = [os.path.join(root_directory, f) for f in glob.glob(pattern, root_dir=root_directory)]

    for video_path in video_files:
        filename = os.path.basename(video_path)
        # Parse filename: {league}_{game}_{play}_{team}_{view}.mp4
        parts = os.path.basename(filename).replace('.mp4', '').split('_')
        
        if len(parts) >= 3:
            play_id = parts[2]  # Extract play_id (third component)
            
            if play_id in video_index:
                raise Exception(f"Duplicate play_id {play_id} found in video files.")
            video_index[play_id] = video_path
    
    return video_index

class FrameQuadIterDataset(IterableDataset):
    """
    PyTorch IterableDataset that yields frame quads from videos.
    """
    
    def __init__(self, root_directory: str, csv_path: str, fps: int = 30, 
                    clip_length: int = 8):
        """
        Initialize the dataset.
        
        Args:
            root_directory: Root directory containing video files
            csv_path: Path to CSV with game_id, play_id, snap_time columns
            fps: Frames per second (default: 30)
            clip_length: Length of clip in frames (default: 8)
        """
        self.root_directory = root_directory
        self.csv_path = csv_path
        self.fps = fps
        self.clip_length = clip_length
    
    def __iter__(self):
        """
        Iterate over frame quads and return video frames as tensors.
        
        Yields:
            Tuple of (frames_tensor, label, snap_frame) where:
            - frames_tensor: torch.Tensor of shape (clip_length, height, width, channels)
            - label: int (1 for snap, 0 for non-snap)
            - snap_frame: int (frame number of the snap)
        """
        for video_path, start_frame, end_frame, label, snap_frame in generate_frame_quads(
            self.root_directory, self.csv_path, self.fps, self.clip_length
        ):
            # Load video frames
            cap = cv2.VideoCapture(video_path)
            frames = []
            
            try:
                for frame_idx in range(start_frame, end_frame):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frames.append(frame)
                
                if len(frames) == self.clip_length:
                    # Convert to tensor: (clip_length * channels, height, width)
                    frames_array = np.array(frames)
                    frames_tensor = torch.from_numpy(frames_array).float()
                    yield frames_tensor.moveaxis(-1, 1).reshape(-1, *frames_tensor.shape[1:3]), label, snap_frame
                    
            finally:
                cap.release()

class FrameQuadMapDataset(torch.utils.data.Dataset):
    """
    PyTorch Dataset that yields frame quads from videos using map-style access.
    """
    
    def __init__(self, root_directory: str, csv_path: str, fps: int = 30, 
                    clip_length: int = 8):
        """
        Initialize the dataset.
        
        Args:
            root_directory: Root directory containing video files
            csv_path: Path to CSV with game_id, play_id, snap_time columns
            fps: Frames per second (default: 30)
            clip_length: Length of clip in frames (default: 8)
        """
        self.root_directory = root_directory
        self.csv_path = csv_path
        self.fps = fps
        self.clip_length = clip_length
        
        # Pre-generate all samples
        self.samples = list(generate_frame_quads(
            self.root_directory, self.csv_path, self.fps, self.clip_length
        ))
    
    def __len__(self):
        """Return the total number of samples."""
        return len(self.samples)
    
    def __getitem__(self, idx):
        """
        Get a single sample by index.
        
        Args:
            idx: Index of the sample to retrieve
            
        Returns:
            Tuple of (frames_tensor, label, snap_frame) where:
            - frames_tensor: torch.Tensor of shape (clip_length * channels, height, width)
            - label: int (1 for snap, 0 for non-snap)
            - snap_frame: int (frame number of the snap)
        """
        video_path, start_frame, end_frame, label, snap_frame = self.samples[idx]
        
        # Load video frames
        cap = cv2.VideoCapture(video_path)
        frames = []
        
        try:
            for frame_idx in range(start_frame, end_frame):
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)
            
            if len(frames) == self.clip_length:
                # Convert to tensor: (clip_length * channels, height, width)
                frames_array = np.array(frames)
                frames_tensor = torch.from_numpy(frames_array).float()
                return frames_tensor.moveaxis(-1, 1).reshape(-1, *frames_tensor.shape[1:3]), label, snap_frame
            else:
                # Handle case where we don't have enough frames
                raise IndexError(f"Not enough frames loaded: {len(frames)} < {self.clip_length}")
                
        finally:
            cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate frame triplets for video clips')
    parser.add_argument('root_directory', help='Root directory containing video files')
    parser.add_argument('train_csv_path', help='Path to CSV with game_id, play_id, snap_time columns')
    parser.add_argument('val_csv_path', help='Path to CSV with game_id, play_id, snap_time columns')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second (default: 30)')
    parser.add_argument('--max_iters', default=1, type=int, help='Number of iterations to train')
    parser.add_argument('--val_every', default=100, type=int, help='Validate every N iterations')
    parser.add_argument('--chkpt_every', default=500, type=int, help='Checkpoint every N iterations')
    parser.add_argument('--batch_size', default=8, type=int, help='Batch size for training and validation')
    parser.add_argument('--clip_length', default=8, type=int, help='Number of frames per clip')
    
    args = parser.parse_args()

    for i, quad in enumerate(generate_frame_quads(args.root_directory, args.train_csv_path,
                                         args.fps)):
        print(quad)
        if i >= 10:  # Limit output for demonstration
            break

    ds = FrameQuadIterDataset(args.root_directory, args.train_csv_path, args.fps)
    for i, (frames_tensor, label, snap_frame) in enumerate(ds):
        print(frames_tensor.shape, label, snap_frame)
        if i >= 3:  # Limit output for demonstration
            break

    model = tv.models.resnet50(weights=tv.models.ResNet50_Weights.IMAGENET1K_V2)

    new_weights = model.conv1.weight.data.repeat(1, args.clip_length, 1, 1)

    model.conv1 = torch.nn.Conv2d(args.clip_length * 3, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
    model.conv1.weight.data = new_weights

    model.fc = torch.nn.Linear(model.fc.in_features, 2)

    dl = torch.utils.data.DataLoader(ds, batch_size=args.batch_size)

    val_ds = FrameQuadMapDataset(args.root_directory, args.val_csv_path, args.fps)
    val_dl = torch.utils.data.DataLoader(val_ds, batch_size=args.batch_size)

    device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'))

    print(device)

    model = model.to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    for i, (frames_tensor, label, snap_frame) in enumerate(dl, 1):
        model.train()

        optimizer.zero_grad()
        outputs = model(frames_tensor.to(device))

        loss = torch.nn.functional.cross_entropy(outputs, label.to(device))
        loss.backward()
        optimizer.step()

        log_entry = {
            "iteration": i,
            "train_loss": loss.item()
        }
        print(json.dumps(log_entry))

        if i % args.chkpt_every == 0:
            torch.save(model.state_dict(), f'snap_model_iter_{i}.pth')

        if i % args.val_every == 0:
            model.eval()
            val_loss = 0.0
            val_count = 0
            with torch.no_grad():
                for val_frames_tensor, val_label, val_snap_frame in val_dl:
                    val_outputs = model(val_frames_tensor.to(device))
                    v_loss = torch.nn.functional.cross_entropy(val_outputs, val_label.to(device))
                    val_loss += v_loss.item() * val_frames_tensor.size(0)
                    val_count += val_frames_tensor.size(0)
            avg_val_loss = val_loss / val_count if val_count > 0 else float('inf')
            print(json.dumps({
                "iteration": i,
                "val_loss": avg_val_loss
            }))

        if i >= args.max_iters:
            break

    torch.save(model.state_dict(), f'snap_model_iter_{i}.pth')