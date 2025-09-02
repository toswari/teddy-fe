from main import FrameQuadMapDataset
import torchvision as tv
import torch
from torchvision.transforms import v2
import einops
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate frame triplets for video clips')
    parser.add_argument('root_directory', help='Root directory containing video files')
    parser.add_argument('val_csv_path', help='Path to CSV with game_id, play_id, snap_time columns')
    parser.add_argument('weights', help='Path to model weights')
    parser.add_argument('--clip_length', default=8, type=int, help='Number of frames per clip')
    parser.add_argument('--model', default='resnet50', type=str, help='Model architecture to use', choices=['resnet50', 'mvit'])
    parser.add_argument('--num_dl_workers', default=0, type=int, help='Number of DataLoader workers')
    parser.add_argument('--batch_size', default=8, type=int, help='Batch size for training and validation')
    parser.add_argument('--fps', type=int, default=30, help='Frames per second (default: 30)')

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

    val_ds = FrameQuadMapDataset(args.root_directory, args.val_csv_path, args.fps, clip_length=args.clip_length)
    val_dl = torch.utils.data.DataLoader(val_ds, batch_size=args.batch_size, num_workers=args.num_dl_workers)

    device = torch.device('cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'))

    print(device)

    model = model.to(device)
    model.load_state_dict(torch.load(args.weights))

    gt = []
    outputs = []
    with torch.no_grad():
        for val_frames_tensor, val_label, val_snap_frame in val_dl:
            outputs.append(model(preprocess(val_frames_tensor.to(device))))
            gt.append(val_label)

    gt = torch.cat(gt)
    outputs = torch.cat(outputs).cpu()
    probs = outputs.softmax(dim=1)
    preds = probs.argmax(dim=1)

    tp = preds[(preds == 1) & (gt == 1)].sum()
    fp = preds[(preds == 1) & (gt != 1)].sum()
    fn = preds[(preds == 0) & (gt == 1)].sum()
    p =  tp / (tp + fp)
    r = tp / (tp + fn)

    print(p, r, tp, fp, fn)
