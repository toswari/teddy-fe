import cv2
import numpy as np
import easyocr
from PIL import Image
from collections import defaultdict
import os
from datetime import datetime


# Import YOLORecognizer
try:
    from .yolo_recognizer import YOLORecognizer
    YOLO_AVAILABLE = True
except ImportError:
    YOLORecognizer = None
    YOLO_AVAILABLE = False


class EasyOCRRecognizer:
    def __init__(self, **kwargs):
        self.reader = easyocr.Reader(["en"], gpu=kwargs.get("gpu", False))

        self.allowlist = kwargs.get("allowlist", "0123456789")

    def recognize(self, player_crop):
        if player_crop.size == 0:
            return -1, 0.0

        img = Image.fromarray(cv2.cvtColor(player_crop, cv2.COLOR_BGR2RGB))
        results = self.reader.readtext(np.array(img), allowlist=self.allowlist)

        if results:
            bbox, text, confidence = results[0]
            try:
                number = int(text)
                if 0 <= number <= 99:
                    return number, confidence
            except ValueError:
                pass

        return -1, 0.0


def create_recognizer(recognizer_type, **kwargs):
    """
    Factory function to create recognizer instances
    
    Args:
        recognizer_type: str, either "EasyOCRRecognizer" or "YOLORecognizer"
        **kwargs: additional parameters for the recognizer
    
    Returns:
        Recognizer instance
    """
    if recognizer_type == "EasyOCRRecognizer":
        return EasyOCRRecognizer(**kwargs)
    elif recognizer_type == "YOLORecognizer":
        if not YOLO_AVAILABLE:
            raise ImportError("YOLORecognizer is not available. Check yolo_recognizer.py import.")
        return YOLORecognizer(**kwargs)
    else:
        raise ValueError(f"Unknown recognizer type: {recognizer_type}. "
                        f"Available types: EasyOCRRecognizer, YOLORecognizer")


def extract_player_regions(frame, detections, min_detect_confidence):
    player_crops = []
    player_uuids = []

    for region in detections:
        if (
            hasattr(region, "data")
            and region.data.concepts
            and region.data.concepts[0].name == "players"
            and region.value >= min_detect_confidence
        ):
            x1 = region.region_info.bounding_box.left_col * frame.shape[1]
            y1 = region.region_info.bounding_box.top_row * frame.shape[0]
            x2 = region.region_info.bounding_box.right_col * frame.shape[1]
            y2 = region.region_info.bounding_box.bottom_row * frame.shape[0]

            crop = frame[int(y1) : int(y2), int(x1) : int(x2)]
            player_crops.append(
                crop
            )  # uint8, shape (height, width, 3) Values: 0-255 for each RGB channel
            player_uuids.append(region.id)

    return player_crops, player_uuids


def recognize_player_numbers(
    frame,
    detections,
    min_detect_confidence=0.0,
    recognizer=None,
    debug_folder="debug_crops",
    use_grounding_dino=False,
):
    player_crops, player_uuids = extract_player_regions(
        frame, detections, min_detect_confidence
    )
    results = []

    # Create debug folders
    os.makedirs(debug_folder, exist_ok=True)
    debug_raw_folder = debug_folder + "_raw"
    os.makedirs(debug_raw_folder, exist_ok=True)
    if use_grounding_dino:
        debug_grounding_folder = debug_folder + "_grounding_cropped"
        os.makedirs(debug_grounding_folder, exist_ok=True)

    if use_grounding_dino and player_crops:
        from .groundingdino_util import GroundingDINOInference
        
        grounding_inference = GroundingDINOInference(cpu_only=True)
        
        for crop, uuid in zip(player_crops, player_uuids):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Save raw crop
            raw_filename = f"{debug_raw_folder}/crop_{timestamp}_{uuid}_raw.jpg"
            cv2.imwrite(raw_filename, crop)
            
            # Get the smallest valid box and cropped region
            cropped_for_recognition, grounding_box = grounding_inference.detect_and_crop_numbers(crop)
            
            # Save GroundingDINO cropped version
            grounding_filename = f"{debug_grounding_folder}/crop_{timestamp}_{uuid}_grounding.jpg"
            cv2.imwrite(grounding_filename, cropped_for_recognition)
            
            number, confidence = recognizer.recognize(cropped_for_recognition)
            
            crop_filename = f"{debug_folder}/crop_{timestamp}_{uuid}_num{number}_conf{confidence:.3f}.jpg"
            
            # Save debug crop with GroundingDINO box visualization if it exists
            debug_crop = crop.copy()
            if grounding_box is not None:
                x1, y1, x2, y2 = grounding_box
                cv2.rectangle(debug_crop, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Green thin box
            
            cv2.imwrite(crop_filename, debug_crop)
            
            results.append(
                {"uuid": uuid, "player_number": number, "confidence": confidence}
            )
    else:
        for crop, uuid in zip(player_crops, player_uuids):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Save raw crop
            raw_filename = f"{debug_raw_folder}/crop_{timestamp}_{uuid}_raw.jpg"
            cv2.imwrite(raw_filename, crop)
            
            number, confidence = recognizer.recognize(crop)

            crop_filename = f"{debug_folder}/crop_{timestamp}_{uuid}_num{number}_conf{confidence:.3f}.jpg"
            cv2.imwrite(crop_filename, crop)

            results.append(
                {"uuid": uuid, "player_number": number, "confidence": confidence}
            )

    return results


def assign_player_ids_to_tracks(track_data, player_recognitions):
    track_player_votes = defaultdict(list)

    for frame_idx, recognitions in player_recognitions.items():
        frame_tracks = track_data[track_data["frame"] == frame_idx]

        for _, track in frame_tracks.iterrows():
            for recognition in recognitions:
                if recognition["player_number"] != -1:
                    if track["uuid"] == recognition["uuid"]:
                        track_player_votes[track["object_id"]].append(
                            (recognition["player_number"], recognition["confidence"])
                        )

    track_player_assignments = {}
    for track_id, votes in track_player_votes.items():
        if votes:
            vote_counts = defaultdict(list)
            for number, confidence in votes:
                vote_counts[number].append(confidence)

            print(f"Track {track_id}: votes = {dict(vote_counts)}")
            best_number = max(vote_counts.items(), key=lambda x: len(x[1]))
            track_player_assignments[track_id] = best_number[0]

    return track_player_assignments
