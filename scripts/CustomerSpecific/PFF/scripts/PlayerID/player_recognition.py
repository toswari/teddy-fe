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

    def recognize_batch(self, player_crops):
        """Batch processing wrapper for EasyOCR - processes crops sequentially"""
        results = []
        for crop in player_crops:
            number, confidence = self.recognize(crop)
            results.append((number, confidence))
        return results


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


def recognize_player_numbers_batch(
    all_crops_data,
    recognizer=None,
    debug_folder="debug_crops",
    use_grounding_dino=False,
):
    """
    Batch process player number recognition for multiple crops from multiple frames
    
    Args:
        all_crops_data: List of (frame_idx, crop, uuid, video_frame) tuples
        recognizer: Recognizer instance with recognize_batch method
        debug_folder: Base debug folder path
        use_grounding_dino: Whether to use GroundingDINO preprocessing
    
    Returns:
        dict: {frame_idx: [recognition_results]} 
    """
    if not all_crops_data:
        return {}
    
    # Define debug folder paths
    debug_raw_folder = debug_folder + "_raw"
    debug_grounding_folder = debug_folder + "_grounding_cropped" if use_grounding_dino else None
    
    # Check if debug folders exist and contain files
    skip_generation = (
        os.path.exists(debug_raw_folder) and 
        (not use_grounding_dino or (debug_grounding_folder and os.path.exists(debug_grounding_folder)))
    )
    
    if skip_generation:
        # Load crops from existing debug folders
        crops_for_recognition = []
        crop_metadata = []
        
        if use_grounding_dino and debug_grounding_folder and os.path.exists(debug_grounding_folder):
            # Get all jpg files from grounding folder
            grounding_files = [f for f in os.listdir(debug_grounding_folder) if f.endswith('.jpg')]
            grounding_files.sort()  # Sort for consistent ordering
            
            for filename in grounding_files:
                # Parse metadata from filename: crop_{timestamp}_{uuid}_grounding.jpg
                parts = filename.replace('crop_', '').replace('_grounding.jpg', '').split('_')
                if len(parts) >= 2:
                    timestamp = '_'.join(parts[:-1])
                    uuid = parts[-1]
                    
                    # Load the crop image
                    crop_path = os.path.join(debug_grounding_folder, filename)
                    crop_img = cv2.imread(crop_path)
                    if crop_img is not None:
                        crops_for_recognition.append(crop_img)
                        # Use frame_idx=0 as placeholder since we're processing existing crops
                        crop_metadata.append((0, uuid, crop_img, timestamp, None))
        else:
            # Load from raw folder when not using grounding dino
            raw_files = [f for f in os.listdir(debug_raw_folder) if f.endswith('.jpg')]
            raw_files.sort()  # Sort for consistent ordering
            
            for filename in raw_files:
                # Parse metadata from filename: crop_{timestamp}_{uuid}_raw.jpg
                parts = filename.replace('crop_', '').replace('_raw.jpg', '').split('_')
                if len(parts) >= 2:
                    timestamp = '_'.join(parts[:-1])
                    uuid = parts[-1]
                    
                    # Load the crop image
                    crop_path = os.path.join(debug_raw_folder, filename)
                    crop_img = cv2.imread(crop_path)
                    if crop_img is not None:
                        crops_for_recognition.append(crop_img)
                        # Use frame_idx=0 as placeholder since we're processing existing crops
                        crop_metadata.append((0, uuid, crop_img, timestamp, None))
    else:
        # Original generation logic
        # Create debug folders
        os.makedirs(debug_folder, exist_ok=True)
        os.makedirs(debug_raw_folder, exist_ok=True)
        if use_grounding_dino:
            os.makedirs(debug_grounding_folder, exist_ok=True)

        # Prepare crops for batch processing
        crops_for_recognition = []
        crop_metadata = []  # (frame_idx, uuid, original_crop, timestamp, debug_paths)
        
        if use_grounding_dino:
            from .groundingdino_util import GroundingDINOInference
            grounding_inference = GroundingDINOInference(cpu_only=True)
        
        # Process all crops and prepare for batch recognition
        for frame_idx, crop, uuid, _ in all_crops_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Save raw crop
            raw_filename = f"{debug_raw_folder}/crop_{timestamp}_{uuid}_raw.jpg"
            cv2.imwrite(raw_filename, crop)
            
            if use_grounding_dino:
                # Get the smallest valid box and cropped region
                cropped_for_recognition, grounding_box = grounding_inference.detect_and_crop_numbers(crop)
                
                # Save GroundingDINO cropped version
                grounding_filename = f"{debug_grounding_folder}/crop_{timestamp}_{uuid}_grounding.jpg"
                cv2.imwrite(grounding_filename, cropped_for_recognition)
            else:
                cropped_for_recognition = crop
                grounding_box = None
            
            crops_for_recognition.append(cropped_for_recognition)
            crop_metadata.append((frame_idx, uuid, crop, timestamp, grounding_box))
    
    # Batch recognize all crops
    if hasattr(recognizer, 'recognize_batch'):
        crop_filenames = [f"{meta[3]}_{meta[1]}" for meta in crop_metadata]
        batch_results = recognizer.recognize_batch(crops_for_recognition, crop_filenames)
    else:
        # Fallback to sequential processing
        batch_results = []
        for crop in crops_for_recognition:
            number, confidence = recognizer.recognize(crop)
            batch_results.append((number, confidence))
    
    # Organize results by frame and save debug crops
    player_recognitions = {}
    for i, (number, confidence) in enumerate(batch_results):
        frame_idx, uuid, original_crop, timestamp, grounding_box = crop_metadata[i]
        
        # Initialize frame results if needed
        if frame_idx not in player_recognitions:
            player_recognitions[frame_idx] = []
        
        # Save debug crop with visualization if needed
        crop_filename = f"{debug_folder}/crop_{timestamp}_{uuid}_num{number}_conf{confidence:.3f}.jpg"
        debug_crop = original_crop.copy()
        if grounding_box is not None:
            x1, y1, x2, y2 = grounding_box
            cv2.rectangle(debug_crop, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Green thin box
        
        cv2.imwrite(crop_filename, debug_crop)
        
        # Store result
        player_recognitions[frame_idx].append({
            "uuid": uuid, 
            "player_number": number, 
            "confidence": confidence
        })
    
    return player_recognitions


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
