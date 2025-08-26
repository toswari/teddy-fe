"evaluate readout against ground truth snap frame"
import torchvision as tv
import torch
from torchvision.transforms import v2
import einops
import argparse
import os
import glob
from tqdm import tqdm
import pandas as pd
import cv2
import numpy as np

def infer(model, video_path, conf_thresh, clip_length):
    cap = cv2.VideoCapture(video_path)
    frames = []
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
    finally:
        cap.release()
 
    frames = torch.tensor(np.array(frames), device=device).moveaxis(-1,1).unsqueeze(0)
    outputs = []
    with torch.inference_mode():
        for i in tqdm(range(frames.shape[1] - clip_length), leave=False):
            frames_tensor = frames[:1, i:i+clip_length, ...]
            outputs.append(model(preprocess(frames_tensor)).cpu())

    outputs = torch.cat(outputs)
    probs = outputs.softmax(dim=1)
    probs[:,1] = probs[:,1] * (probs[:,1] > conf_thresh)
    preds = probs.argmax(dim=1)

    votes = torch.zeros(frames.shape[1])
    for i, pred in enumerate(preds):
        votes[i:i+args.clip_length] += pred

    return outputs, probs, preds, votes

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate frame triplets for video clips')
    parser.add_argument('root_directory', help='Root directory containing video files')
    parser.add_argument('val_csv_path', help='Path to CSV with game_id, play_id, snap_time columns')
    parser.add_argument('weights', help='Path to model weights')
    parser.add_argument('--clip_length', default=16, type=int, help='Number of frames per clip')
    parser.add_argument('--model', default='mvit', type=str, help='Model architecture to use', choices=['resnet50', 'mvit'])
    parser.add_argument('--conf_thresh', type=float, default=0)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--max_examples', type=int, default=None)
    parser.add_argument('--output_csv', type=str, default='eval2_out.csv')

    args = parser.parse_args()

    if args.model == 'resnet50':
        weights = tv.models.ResNet50_Weights.IMAGENET1K_V2
        preprocess = v2.Compose([
            v2.Lambda(lambda x: einops.rearrange(x, 'b f c h w -> (b f) c h w')),
            weights.transforms(),
            v2.Lambda(lambda x: einops.rearrange(x, '(b f) c h w -> b (f c) h w', b=args.batch_size)),
        ])
        model = tv.models.resnet50(weights=weights)

        new_weights = model.conv1.weight.data.repeat(1, args.clip_length, 1, 1)

        model.conv1 = torch.nn.Conv2d(args.clip_length * 3, 64, kernel_size=(7, 7), stride=(2, 2), padding=(3, 3), bias=False)
        model.conv1.weight.data = new_weights

        model.fc = torch.nn.Linear(model.fc.in_features, 2)
    elif args.model == 'mvit':
        assert args.clip_length == 16, "MViT model currently only supports clip_length of 16"
        weights = tv.models.video.MViT_V2_S_Weights.KINETICS400_V1
        preprocess = weights.transforms()
        model = tv.models.video.mvit_v2_s(weights=weights)
        model.head[1] = torch.nn.Linear(model.head[1].in_features, 2)
    else:
        raise ValueError(f"Unsupported model architecture: {args.model}")

    device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'))

    print(device)

    model = model.to(device)
    model.load_state_dict(torch.load(args.weights))
    model = model.eval()

    val_df = pd.read_csv(args.val_csv_path)
    if args.max_examples:
        val_df = val_df.iloc[:args.max_examples]
    val_df['snap_time'] = val_df['snap_time'].apply(lambda x: float(x.split(':')[0])*60 + float(x.split(':')[1]))

    videos = {int(os.path.basename(p).split('_')[2]): os.path.join(args.root_directory, p) for p in glob.glob('*.mp4', root_dir=args.root_directory)}

    pred_times = []
    for i, row in tqdm(val_df.iterrows(), total=len(val_df)):
        video_path = videos[row['play_id']]
        outputs, probs, preds, votes = infer(model, video_path, args.conf_thresh, args.clip_length)
        pred_time = votes.argmax().item() / args.fps
        pred_times.append(pred_time)

    val_df['pred_time'] = pred_times
    val_df['err'] = val_df['pred_time'] - val_df['snap_time']
    val_df['abs_err'] = val_df['err'].abs()
    val_df.to_csv(args.output_csv)
    print(f'output written to {args.output_csv}')

    print(f"ME: {val_df['err'].mean()}")
    print(f"MAE: {val_df['abs_err'].mean()}")
    print(f"MSE: {(val_df['abs_err']**2).mean()}")
    print(f"RMSE: {(val_df['abs_err']**2).mean()**0.5}")
