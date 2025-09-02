import torchvision as tv
import torch
from torchvision.transforms import v2
import einops
import argparse
import cv2
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sliding window inference across video + plotting')
    parser.add_argument('video_path')
    parser.add_argument('weights')
    parser.add_argument('--clip_length', default=16)
    parser.add_argument('--model', default='mvit')
    parser.add_argument('--conf_thresh', default=0., type=float)

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

    cap = cv2.VideoCapture(args.video_path)
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
        for i in tqdm(range(frames.shape[1] - args.clip_length)):
            frames_tensor = frames[:1, i:i+args.clip_length, ...]
            outputs.append(model(preprocess(frames_tensor)).cpu())

    outputs = torch.cat(outputs)
    probs = outputs.softmax(dim=1)
    probs[:,1] = probs[:,1] * (probs[:,1] > args.conf_thresh)
    preds = probs.argmax(dim=1)

    plt.plot(probs[:,1])
    plt.plot(preds)
    plt.savefig('fig.png')

    votes = torch.zeros(frames.shape[1])
    for i, pred in enumerate(preds):
        votes[i:i+args.clip_length] += pred
    plt.plot(votes)
    plt.savefig('votes.png')

    print(votes.argmax().item(), probs[:,1].argmax().item())
