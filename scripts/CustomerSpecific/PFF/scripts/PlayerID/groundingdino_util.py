import os
import torch
from PIL import Image
import cv2

import groundingdino.datasets.transforms as T
from groundingdino.models import build_model
from groundingdino.config import GroundingDINO_SwinT_OGC
from groundingdino.util.slconfig import SLConfig
from groundingdino.util.utils import clean_state_dict, get_phrases_from_posmap


def load_image_from_array(image_array):
    """
    Load image from numpy array (BGR format from OpenCV) and convert to PIL and tensor format
    """
    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
    image_pil = Image.fromarray(image_rgb)
    
    transform = T.Compose(
        [
            T.RandomResize([800], max_size=1333),
            T.ToTensor(),
            T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ]
    )
    image_tensor, _ = transform(image_pil, None)  # 3, h, w
    return image_pil, image_tensor


def load_model(model_config_path, model_checkpoint_path, cpu_only=False):
    """
    Load GroundingDINO model from config and checkpoint - matches official script
    """
    args = SLConfig.fromfile(model_config_path)
    args.device = "cuda" if not cpu_only else "cpu"
    model = build_model(args)
    checkpoint = torch.load(model_checkpoint_path, map_location="cpu")
    load_res = model.load_state_dict(clean_state_dict(checkpoint["model"]), strict=False)
    print(f"Model loading result: {load_res}")
    model.eval()
    return model


def get_grounding_output(model, image, caption, box_threshold, text_threshold, cpu_only=False, with_logits=True):
    """
    Get grounding output from model for single image - matches official script exactly
    """
    caption = caption.lower().strip()
    if not caption.endswith("."):
        caption = caption + "."
    
    device = "cuda" if not cpu_only else "cpu"
    model = model.to(device)
    image = image.to(device)
    
    with torch.no_grad():
        outputs = model(image[None], captions=[caption])
    
    logits = outputs["pred_logits"].sigmoid()[0]  # (nq, 256)
    boxes = outputs["pred_boxes"][0]  # (nq, 4)
    
    # Filter output
    logits_filt = logits.cpu().clone()
    boxes_filt = boxes.cpu().clone()
    filt_mask = logits_filt.max(dim=1)[0] > box_threshold
    logits_filt = logits_filt[filt_mask]  # num_filt, 256
    boxes_filt = boxes_filt[filt_mask]  # num_filt, 4
    
    # Get phrases
    tokenlizer = model.tokenizer
    tokenized = tokenlizer(caption)
    pred_phrases = []
    
    for logit in logits_filt:
        pred_phrase = get_phrases_from_posmap(logit > text_threshold, tokenized, tokenlizer)
        if with_logits:
            pred_phrases.append(pred_phrase + f"({str(logit.max().item())[:4]})")
        else:
            pred_phrases.append(pred_phrase)
    
    return boxes_filt, pred_phrases


class GroundingDINOInference:
    """
    GroundingDINO inference class for detecting and cropping number regions from player images
    """
    
    def __init__(self, 
                 config_path=None,
                 checkpoint_path="/Users/bingqingyu/Downloads/groundingdino_swint_ogc.pth",
                 cpu_only=False):
        self.config_path = config_path
        self.checkpoint_path = checkpoint_path
        self.cpu_only = cpu_only
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the GroundingDINO model using the official load_model function"""
        # Use the same approach as experiment script
        if self.config_path is None:
            self.config_path = GroundingDINO_SwinT_OGC.__file__
            
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        if not os.path.exists(self.checkpoint_path):
            raise FileNotFoundError(f"Checkpoint file not found: {self.checkpoint_path}")
        
        self.model = load_model(
            self.config_path, 
            self.checkpoint_path, 
            cpu_only=self.cpu_only
        )
    
    def detect_and_crop_numbers(self, image, box_threshold=0.3, text_threshold=0.25):
        """
        Detect and crop the smallest valid number region from an image
        
        Args:
            image: numpy array (BGR format from OpenCV)
            box_threshold: threshold for box detection
            text_threshold: threshold for text detection
            
        Returns:
            tuple: (cropped_image, box_coords_xyxy) where:
                - cropped_image: numpy array of the cropped region, or original image if no detection
                - box_coords_xyxy: tuple (x1, y1, x2, y2) of the box used, or None if no detection
        """
        # Convert image to the format expected by the model
        _, image_tensor = load_image_from_array(image)
        
        # Use official get_grounding_output function
        boxes_filt, _ = get_grounding_output(
            self.model, 
            image_tensor, 
            "numbers", 
            box_threshold, 
            text_threshold, 
            cpu_only=self.cpu_only
        )
        
        if len(boxes_filt) == 0:
            return image, None
        
        # Get the smallest box (by area) among valid detections
        H, W = image.shape[:2]
        smallest_box = None
        smallest_area = float('inf')
        
        for box in boxes_filt:
            # Box format: [cx, cy, w, h] in normalized coordinates
            cx, cy, w, h = box
            area = w * h  # normalized area
            if area < smallest_area:
                smallest_area = area
                smallest_box = box
        
        # Convert box from normalized coordinates to pixel coordinates
        cx, cy, w, h = smallest_box
        
        # Convert to pixel coordinates
        cx_px = cx * W
        cy_px = cy * H
        w_px = w * W
        h_px = h * H
        
        # Convert to xyxy format
        x1 = int(cx_px - w_px / 2)
        y1 = int(cy_px - h_px / 2)
        x2 = int(cx_px + w_px / 2)
        y2 = int(cy_px + h_px / 2)
        
        # Ensure coordinates are within image bounds
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(W, x2)
        y2 = min(H, y2)
        
        # Crop the region
        cropped = image[y1:y2, x1:x2]
        
        if cropped.size > 0:
            return cropped, (x1, y1, x2, y2)
        else:
            return image, None