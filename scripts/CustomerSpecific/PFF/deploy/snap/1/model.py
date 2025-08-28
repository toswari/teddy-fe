from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_types.data_types import Video

import os
import torch
import torchvision as tv
from clarifai_pff.utils import video as video_utils
import numpy as np

class Runner(ModelClass):
    def load_model(self):
        weights = tv.models.video.MViT_V2_S_Weights.KINETICS400_V1
        self.preprocess = weights.transforms()
        model = tv.models.video.mvit_v2_s()
        model.head[1] = torch.nn.Linear(model.head[1].in_features, 2)
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model = model.to(self.device)
        model.load_state_dict(torch.load(os.path.join(os.path.dirname(__file__), 'snap_model_iter_1012.pth'), map_location=self.device))
        model = model.eval()
        self.model = model

    @ModelClass.method
    def predict(self, video: Video, conf_thresh: float = 0, clip_length: int = 16) -> float:
        if not video.bytes and not video.url:
            raise ValueError("Video must have either bytes or url set.")

        if video.url:
            video_stream = video_utils.stream_frames_from_url(video.url, download_ok=True)
        elif video.bytes:
            def _bytes_iterator():
                yield video.bytes
            video_stream = video_utils.stream_frames_from_bytes(_bytes_iterator())
        else:
            raise ValueError("Video must have either bytes or url set.")

        frames = np.array([frame.to_ndarray(format="rgb24") for frame in video_stream])
        frames = torch.tensor(frames, device=self.device).moveaxis(-1,1).unsqueeze(0)

        outputs = []
        with torch.inference_mode():
            for i in range(frames.shape[1] - clip_length):
                frames_tensor = frames[:1, i:i+clip_length, ...]
                outputs.append(self.model(self.preprocess(frames_tensor)).cpu())

        outputs = torch.cat(outputs)
        probs = outputs.softmax(dim=1)
        probs[:,1] = probs[:,1] * (probs[:,1] > conf_thresh)
        preds = probs.argmax(dim=1)

        votes = torch.zeros(frames.shape[1])
        for i, pred in enumerate(preds):
            votes[i:i+clip_length] += pred

        return votes.argmax().item() / 30.0  # Assuming 30 FPS