import os
import zipfile
from functools import cache
from types import SimpleNamespace

import requests
import torch
from clarifai.client import User
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
from google.protobuf.json_format import MessageToDict
from PIL import Image
from requests.adapters import HTTPAdapter, Retry
from torch.utils.data import Dataset
from torchvision import tv_tensors


def build_stub():
    # Initialize channel locally to support multi process data loading
    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)
    return stub


class RecursiveNamespace(SimpleNamespace):
    """A namespace that recursively converts dictionaries to RecursiveNamespace objects."""

    @staticmethod
    def map_entry(entry):
        if isinstance(entry, dict):
            return RecursiveNamespace(**entry)

        return entry

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for key, val in kwargs.items():
            if isinstance(val, dict):
                setattr(self, key, RecursiveNamespace(**val))
            elif isinstance(val, list):
                setattr(self, key, list(map(self.map_entry, val)))


class ClarifaiTorchGrpcDataset(Dataset):
    """
    A PyTorch Dataset that interfaces with Clarifai applications to provide training data.

    This dataset class connects to a Clarifai app via gRPC API to fetch inputs (images) 
    and their annotations for machine learning training. It supports both cached and 
    real-time data loading, with automatic retry mechanisms for robust API communication.

    Args:
        user_id (str): Clarifai user ID for authentication
        pat (str): Personal Access Token for Clarifai API authentication
        app_id (str): Clarifai application ID containing the training data
        dataset_id (str): Specific dataset ID within the app. If None, uses all inputs from the app
        transform (callable, optional): Optional transform to be applied to images
        target_transform (callable, optional): Optional transform to be applied to target annotations
        cache_dir (str, optional): Directory path for caching dataset as zip file. If None, loads directly from API

    Attributes:
        concepts (list): List of concept dictionaries with 'id' and 'name' keys, sorted by name
        classes (list): Sorted list of concept names
        inputs (dict): Mapping of input IDs to image URLs
        annotations (dict): Mapping of input IDs to lists of annotation objects
        input_ids (list): List of all input IDs in the dataset

    Example:
        >>> dataset = ClarifaiTorchGrpcDataset(
        ...     user_id="user123",
        ...     pat="your_pat_token",
        ...     app_id="app456",
        ...     dataset_id="dataset789",
        ...     cache_dir="/path/to/cache"
        ... )
        >>> print(f"Dataset size: {len(dataset)}")
        >>> image, annotations = dataset[0]

    Note:
        - When cache_dir is provided and cache doesn't exist, the dataset's annotations will be downloaded and cached
        - When cache_dir is None, data is loaded directly from the API on each access
        - The dataset automatically handles pagination for large datasets
        - Annotations are converted to RecursiveNamespace objects for easy attribute access
    """

    def __init__(
        self,
        user_id,
        pat,
        app_id,
        dataset_id: str,
        transform=None,
        target_transform=None,
        cache_dir=None,
    ):
        self.transform = transform
        self.target_transform = target_transform
        self._api_key = pat
        self._metadata = [("authorization", f"Key {pat}")]
        self.user_id = user_id
        self.app_id = app_id
        self.dataset_id = dataset_id
        self.cache_dir = cache_dir
        self.cache_path = os.path.join(self.cache_dir, f"{self.dataset_id}-cache.zip")

        self.requests_session = requests.Session()
        self.requests_session.headers.update({"Authorization": f"Key {pat}"})

        retry = Retry(total=5, backoff_factor=0.1)

        self.requests_session.mount("https://", HTTPAdapter(max_retries=retry))

        self._get_concepts()

        self._input_ids = None

        if self.cache_dir is None:
            print("loading from api")
            self._get_inputs()
        elif not os.path.exists(self.cache_path):
            print("generating cache")
            os.makedirs(self.cache_dir, exist_ok=True)
            ds = User(self.user_id, pat=self._api_key).app(self.app_id).dataset(self.dataset_id)
            zip_url = ds.archive_zip(wait=True)
            resp = self.requests_session.get(zip_url)
            with open(self.cache_path, "wb") as f:
                f.write(resp.content)

    def _load_cache(self):
        assert os.path.exists(self.cache_path)
        print("loading cache")
        self._input_ids = []
        self.inputs = {}
        self.annotations = {}
        with zipfile.ZipFile(self.cache_path, "r") as zf:
            for filename in zf.namelist():
                if filename.startswith("all/"):
                    with zf.open(filename) as f:
                        batch = resources_pb2.InputBatch.FromString(f.read())
                        for input in batch.inputs:
                            self._input_ids.append(input.id)
                            self.inputs[input.id] = input.data.image.url
                            self.annotations.setdefault(input.id, []).append(
                                RecursiveNamespace(
                                    **MessageToDict(
                                        input,
                                        preserving_proto_field_name=True,
                                        always_print_fields_with_no_presence=True,
                                    )
                                )
                            )

    def _get_inputs(self):
        stub = build_stub()

        # Initialize user_app_id for Clarifai API
        user_app_id = resources_pb2.UserAppIDSet(user_id=self.user_id, app_id=self.app_id)

        inputs = []
        page = 1
        r = None # pass ruff check
        if self.dataset_id is None:
            while page == 1 or len(r.inputs) > 0:
                # Get list of inputs in the app
                r = stub.ListInputs(
                    service_pb2.ListInputsRequest(
                        user_app_id=user_app_id, per_page=100, page=page
                    ),
                    metadata=self._metadata,
                )
                # Check status
                if r.status.code != status_code_pb2.SUCCESS:
                    raise Exception("List failed, status: " + r.status.description)
                # save the full list, list of ids, and add image urls to self
                inputs.extend(list(r.inputs))
                page += 1
        else:
            while page == 1 or len(r.dataset_inputs) > 0:
                r = stub.ListDatasetInputs(
                    service_pb2.ListDatasetInputsRequest(
                        user_app_id=user_app_id,
                        dataset_id=self.dataset_id,
                        per_page=100,
                        page=page,
                    ),
                    metadata=self._metadata,
                )
                # Check status
                if r.status.code != status_code_pb2.SUCCESS:
                    raise Exception("List failed, status: " + r.status.description)
                inputs.extend([di.input for di in r.dataset_inputs])
                page += 1

        self.input_ids = [io.id for io in inputs]
        self.inputs = {io.id: io.data.image.url for io in inputs}

        # Get annotations from the app
        # Note that the order is NOT guaranteed to match self.inputs
        page = 1
        annotations = []
        while page == 1 or len(r.annotations) > 0:
            r = stub.ListAnnotations(
                service_pb2.ListAnnotationsRequest(
                    input_ids=self.input_ids,
                    user_app_id=user_app_id,
                    per_page=1000,
                    page=page,
                ),
                metadata=self._metadata,
            )
            annotations.extend(r.annotations)
            page += 1

        self.annotations = {}
        for ann in annotations:
            self.annotations.setdefault(ann.input_id, []).append(
                RecursiveNamespace(
                    **MessageToDict(
                        ann,
                        preserving_proto_field_name=True,
                        always_print_fields_with_no_presence=True,
                    )
                )
            )

    def _get_concepts(self):
        stub = build_stub()

        # Initialize user_app_id for Clarifai API
        user_app_id = resources_pb2.UserAppIDSet(user_id=self.user_id, app_id=self.app_id)

        # Get all concepts in the app
        app_concepts = stub.ListConcepts(
            service_pb2.ListConceptsRequest(user_app_id=user_app_id),
            metadata=self._metadata,
        ).concepts

        # store concepts as classes
        self.concepts = sorted(
            [dict(id=c.id, name=c.name) for c in app_concepts], key=lambda x: x["name"]
        )
        self.classes = sorted(c.name for c in app_concepts)
        # add unknown class
        # self.classes.append('_UNK')

    def __len__(self):
        return len(self.annotations)

    @property
    def input_ids(self):
        if not self._input_ids:
            self._load_cache()
        return self._input_ids

    @cache
    def get_image(self, image_url):
        return Image.open(self.requests_session.get(image_url, stream=True).raw)


class ClarifaiClassificationDataset(ClarifaiTorchGrpcDataset):
    """A PyTorch Dataset backed by a Clarifai app for classification"""

    def __getitem__(self, idx):
        input_id = self.input_ids[idx]

        x = self.get_image(self.inputs[input_id])
        x = self.transform(x) if self.transform else x

        y = self.annotations[input_id].data.concepts[0].name
        y = self.classes.index(y)
        y = self.target_transform(y) if self.target_transform else y
        return x, y


class ClarifaiDetectionDataset(ClarifaiTorchGrpcDataset):
    """A PyTorch Dataset backed by a Clarifai app for object detection"""

    def __getitem__(self, idx):
        input_id = self.input_ids[idx]

        x = self.get_image(self.inputs[input_id])

        w, h = x.size
        x = self.transform(x) if self.transform else x

        anns = self.annotations[input_id]
        boxes = []
        labels = []
        for ann in anns:
            for region in ann.data.regions:
                box = region.region_info.bounding_box
                boxes.append(
                    [
                        box.left_col * w,
                        box.top_row * h,
                        box.right_col * w,
                        box.bottom_row * h,
                    ]
                )
                labels.append(self.classes.index(region.data.concepts[0].name))

        boxes = tv_tensors.BoundingBoxes(boxes, format="xyxy", canvas_size=(h, w))
        labels = torch.tensor(labels).long()

        target = {}
        target["boxes"] = boxes
        target["labels"] = labels

        target = self.target_transform(target) if self.target_transform else target
        return x, target


class ClarifaiObjectDataset(ClarifaiTorchGrpcDataset):
    """A PyTorch Dataset backed by a Clarifai app using detection data via crops (e.g., for classification / embedding)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def object_index(self):
        if self._object_index is None:
            self._object_index = []
            for input_id in self.input_ids:
                anns = self.annotations[input_id]
                for ann in anns:
                    for region in ann.data.regions:
                        self.object_index.append((input_id, region))
        return self._object_index

    def __len__(self):
        return len(self.object_index)

    def __getitem__(self, idx):
        input_id, region = self.object_index[idx]

        img = self.get_image(self.inputs[input_id])
        w, h = img.size

        box = region.region_info.bounding_box
        left = int(box.left_col * w)
        top = int(box.top_row * h)
        right = int(box.right_col * w)
        bottom = int(box.bottom_row * h)

        crop = img.crop((left, top, right, bottom))
        if self.transform:
            crop = self.transform(crop)

        label = self.classes.index(region.data.concepts[0].name)
        if self.target_transform:
            label = self.target_transform(label)

        return crop, label


class ClarifaiObjectEmbeddingDataset(ClarifaiObjectDataset):
    """A PyTorch Dataset backed by a Clarifai app for object embedding training."""

    def __init__(self, *args, positive_transform=None, include_concepts=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.positive_transform = positive_transform
        self.include_concepts = include_concepts
        self._object_index = None

    @property
    def object_index(self):
        if self._object_index is None:
            self._object_index = [
                (i, r)
                for i, r in super().object_index
                if self.include_concepts is not None
                and len(r.data.concepts)
                and r.data.concepts[0].name in self.include_concepts
            ]
        return self._object_index

    def __getitem__(self, idx):
        input_id, anchor_region = self.object_index[idx]

        img = self.get_image(self.inputs[input_id])

        w, h = img.size

        box = anchor_region.region_info.bounding_box
        left = int(box.left_col * w)
        top = int(box.top_row * h)
        right = int(box.right_col * w)
        bottom = int(box.bottom_row * h)

        anchor_crop = img.crop((left, top, right, bottom))
        if self.positive_transform:
            positive_crop = self.positive_transform(anchor_crop)
        else:
            positive_crop = anchor_crop

        other_objects = [r for (i, r) in self.object_index if i == input_id and r != anchor_region]
        negative_crops = [
            img.crop(
                (
                    r.region_info.bounding_box.left_col * w,
                    r.region_info.bounding_box.top_row * h,
                    r.region_info.bounding_box.right_col * w,
                    r.region_info.bounding_box.bottom_row * h,
                )
            )
            for r in other_objects
        ]

        if self.transform:
            anchor_crop = self.transform(anchor_crop)
            positive_crop = self.transform(positive_crop)
            negative_crops = [self.transform(c) for c in negative_crops]

        return anchor_crop, positive_crop, negative_crops

    @staticmethod
    def collate_fn(batch):
        return (
            torch.stack([x[0] for x in batch]),
            torch.stack([x[1] for x in batch]),
            [torch.stack(x[-1]) for x in batch],
        )
