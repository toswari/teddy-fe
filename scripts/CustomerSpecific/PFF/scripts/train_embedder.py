import json
import os
import sys
import time

import torch
import torch.nn.functional as F
import torchvision as tv
from safetensors.torch import load_file, save_file
from torch.utils.tensorboard import SummaryWriter
from torchvision.transforms import v2
from tqdm import tqdm

from clarifai_pff.utils.torch_datasets import ClarifaiObjectEmbeddingDataset

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process image embeddings")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size for processing")
    parser.add_argument("--learning_rate", type=float, default=0.001, help="Learning rate")
    parser.add_argument("--epochs", type=int, default=30, help="Number of epochs")
    parser.add_argument("--image_size", type=int, default=64, help="Image size for resizing")
    parser.add_argument(
        "--num_workers", type=int, default=16, help="Number of data loading workers"
    )
    parser.add_argument(
        "--output_dir", type=str, default="outputs", help="Directory to save outputs"
    )
    parser.add_argument("--embedding_dim", type=int, default=32, help="Dimension of embeddings")
    parser.add_argument("--visualize", action="store_true")
    parser.add_argument("--resume_from", type=str, default=None, help="checkpoint to resume from")

    parser.add_argument("--onnx_from", type=str, default=None, help="checkpoint to export")

    args = parser.parse_args()

    model = tv.models.resnet18()
    model.fc = torch.nn.Linear(model.fc.in_features, args.embedding_dim)

    if args.onnx_from is not None:
        state_dict = load_file(args.onnx_from)
        model.load_state_dict(state_dict)
        torch.onnx.export(
            model,
            (torch.randn(1, 3, args.image_size, args.image_size),),
            "model.onnx",
            input_names=["crops"],
            output_names=["embeddings"],
            dynamic_axes={"crops": {0: "batch_size"}, "embeddings": {0: "batch_size"}},
        )
        sys.exit(0)

    ds = ClarifaiObjectEmbeddingDataset(
        user_id="pff-org",
        pat=os.environ["CLARIFAI_PAT"],
        app_id="labelstudio-unified",
        dataset_id="train",
        transform=v2.Compose(
            [
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Resize((args.image_size, args.image_size)),
                v2.RandomHorizontalFlip(p=0.5),
                v2.RandomApply([v2.ColorJitter(0.16, 0.16, 0.16, 0.04)], p=0.8),
                v2.RandomGrayscale(p=0.2),
                v2.RandomApply([v2.GaussianBlur(3)], p=0.5),
            ]
        ),
        target_transform=None,
        include_concepts=["players", "referee"],
        cache_dir="cache",
    )
    if args.visualize:
        import cv2
        import numpy as np

        for i in range(10):
            x = ds[i]
            im = np.zeros((args.image_size, 10 * args.image_size, 3))
            im[:, : args.image_size, :] = x[0].moveaxis(0, -1).numpy()
            im[:, args.image_size : (2 * args.image_size), :] = x[0].moveaxis(0, -1).numpy()
            for i, y in enumerate(x[-1][:8], 3):
                im[:, (i - 1) * args.image_size : i * args.image_size, :] = y.moveaxis(
                    0, -1
                ).numpy()
            cv2.imshow("f", im)
            cv2.waitKey(0)
        cv2.destroyAllWindows()
        sys.exit(0)

    val_ds = ClarifaiObjectEmbeddingDataset(
        user_id="pff-org",
        pat=os.environ["CLARIFAI_PAT"],
        app_id="labelstudio-unified",
        dataset_id="val",
        transform=v2.Compose(
            [
                v2.ToImage(),
                v2.ToDtype(torch.float32, scale=True),
                v2.Resize((args.image_size, args.image_size)),
            ]
        ),
        target_transform=None,
        include_concepts=["players", "referee"],
        cache_dir="cache",
    )

    dl = torch.utils.data.DataLoader(
        ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        collate_fn=ds.collate_fn,
    )

    val_dl = torch.utils.data.DataLoader(
        val_ds,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        collate_fn=val_ds.collate_fn,
    )

    if torch.cuda.is_available():
        model = model.cuda()

    opt = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    epoch = -1
    if args.resume_from is not None:
        state_dict = load_file(args.resume_from)
        model.load_state_dict(state_dict)

        state_dict = torch.load(
            args.resume_from.replace("model_", "optimizer_").replace("safetensors", "pt")
        )
        opt.load_state_dict(state_dict)
        epoch = int(os.path.splitext(os.path.basename(args.resume_from))[0].split("_")[1])

    os.makedirs(args.output_dir, exist_ok=True)

    tb_writer = SummaryWriter(args.output_dir)
    hparams = dict(vars(args))
    hparams.pop("output_dir")
    tb_writer.add_hparams(hparams, {})

    i = 0
    for epoch in range(epoch + 1, epoch + 1 + args.epochs):
        model = model.train()
        data_time_start = time.perf_counter_ns()
        for i, x in enumerate(tqdm(dl), i + 1):
            logs = {"phase": "train", "epoch": epoch, "iter": i}
            logs["data_time"] = (time.perf_counter_ns() - data_time_start) * 1e-9
            tb_writer.add_scalar("times/data", logs["data_time"], i)
            opt.zero_grad()

            x = (x[0].cuda(), x[1].cuda(), [y.cuda() for y in x[2]])

            model_time_start = time.perf_counter_ns()
            anchor, positive, negs = model(x[0]), model(x[1]), [model(y) for y in x[2]]

            logs["model_time"] = (time.perf_counter_ns() - model_time_start) * 1e-9
            tb_writer.add_scalar("times/model", logs["model_time"], i)

            anchor = anchor / anchor.norm(dim=1).unsqueeze(1)
            positive = positive / positive.norm(dim=1).unsqueeze(1)
            negs = [n / n.norm(dim=1).unsqueeze(1) for n in negs]

            pos_dist = F.pairwise_distance(anchor, positive)
            neg_dist = torch.tensor(
                [torch.min(F.pairwise_distance(a, neg)) for a, neg in zip(anchor, negs)]
            )

            pos_loss = F.cosine_embedding_loss(
                anchor,
                positive,
                torch.ones(anchor.size(0), device=anchor.device),
                reduction="none",
                margin=0.1,
            ).mean()
            neg_loss = max(
                [
                    F.cosine_embedding_loss(
                        a.unsqueeze(0),
                        neg,
                        -torch.ones(1, device=a.device),
                        reduction="none",
                        margin=0.1,
                    ).max()
                    for a, neg in zip(anchor, negs)
                ]
            )

            loss = pos_loss + neg_loss
            logs["loss"] = loss.item()
            tb_writer.add_scalar("loss/train-pos", pos_loss, i)
            tb_writer.add_scalar("loss/train-neg", neg_loss, i)
            tb_writer.add_scalar("loss/train", logs["loss"], i)
            loss.backward()

            opt.step()
            tqdm.write(json.dumps(logs))
            data_time_start = time.perf_counter_ns()
        model = model.eval()
        save_file(
            model.state_dict(),
            os.path.join(args.output_dir, f"model_{epoch}.safetensors"),
        )
        torch.save(opt.state_dict(), os.path.join(args.output_dir, f"optimizer_{epoch}.pt"))

        for j, x in enumerate(val_dl):
            logs = {"phase": "val", "epoch": epoch, "iter": i}
            x = (x[0].cuda(), x[1].cuda(), [y.cuda() for y in x[2]])

            model_time_start = time.perf_counter_ns()
            anchor, positive, negs = model(x[0]), model(x[1]), [model(y) for y in x[2]]

            logs["model_time"] = (time.perf_counter_ns() - model_time_start) * 1e-9
            tb_writer.add_scalar("times/model", logs["model_time"], i)

            anchor = anchor / anchor.norm(dim=1).unsqueeze(1)
            positive = positive / positive.norm(dim=1).unsqueeze(1)
            negs = [n / n.norm(dim=1).unsqueeze(1) for n in negs]

            pos_dist = F.pairwise_distance(anchor, positive)
            neg_dist = torch.tensor(
                [torch.min(F.pairwise_distance(a, neg)) for a, neg in zip(anchor, negs)]
            )

            pos_loss = F.cosine_embedding_loss(
                anchor,
                positive,
                torch.ones(anchor.size(0), device=anchor.device),
                reduction="none",
                margin=0.1,
            ).mean()
            neg_loss = max(
                [
                    F.cosine_embedding_loss(
                        a.unsqueeze(0),
                        neg,
                        -torch.ones(1, device=a.device),
                        reduction="none",
                        margin=0.1,
                    ).max()
                    for a, neg in zip(anchor, negs)
                ]
            )

            loss = pos_loss + neg_loss
            logs["loss"] = loss.item()
            tb_writer.add_scalar("loss/val-pos", pos_loss, i)
            tb_writer.add_scalar("loss/val-neg", neg_loss, i)
            tb_writer.add_scalar("loss/val", logs["loss"], i)

            tqdm.write(json.dumps(logs))
            data_time_start = time.perf_counter_ns()
