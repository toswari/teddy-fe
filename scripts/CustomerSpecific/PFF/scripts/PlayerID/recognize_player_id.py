import argparse
import cv2
import json
import os

from clarifai_grpc.grpc.api.resources_pb2 import Data
from src.clarifai_pff.player_recognition import recognize_player_numbers_batch, EasyOCRRecognizer, create_recognizer, extract_player_regions

def main():
    p = argparse.ArgumentParser(description="Run player ID recognition on MOT data.")
    p.add_argument("MOT_PB", help="Path to MOT protobuf file")
    p.add_argument("FRAMES_DIR", help="Directory containing video frames")
    p.add_argument(
        "--player_recognition_config",
        type=str,
        default="config/player_recognition/base_config.json",
        help="Path to player recognition configuration file",
    )
    p.add_argument(
        "--output_folder",
        type=str,
        default="cyu_outputs",
        help="Output folder for debug crops",
    )
    args = p.parse_args()

    # Extract folder name from FRAMES_DIR path (parent of 'frames' folder)
    mot_folder = os.path.basename(os.path.dirname(args.FRAMES_DIR))
    # Create output directory structure
    debug_folder = os.path.join(args.output_folder, mot_folder, "debug_crops")
    os.makedirs(debug_folder, exist_ok=True)

    # Load MOT data
    with open(args.MOT_PB, "rb") as f:
        mot_data = Data.FromString(f.read())

    # Load player recognition config
    with open(args.player_recognition_config, "r") as f:
        player_recognition_params = json.load(f)

    # Create recognizer from config
    RECOGNIZERS = {"EasyOCRRecognizer": EasyOCRRecognizer}
    
    # Add YOLORecognizer if user wants it
    if "YOLORecognizer" == player_recognition_params["recognizer"]:
        RECOGNIZERS["YOLORecognizer"] = lambda **kwargs: create_recognizer("YOLORecognizer", **kwargs)
    
    recognizer_type = player_recognition_params["recognizer"]
    recognizer_params = player_recognition_params.get("recognizer_params", {})
    recognizer = RECOGNIZERS[recognizer_type](**recognizer_params)

    # Step 1: Collect all detection crops from all frames
    print("Collecting all detection crops...")
    all_crops_data = []  # List of (frame_idx, crop, uuid, video_frame) tuples
    
    for frame_idx, frame in enumerate(
        mot_data.frames, 1
    ):  # frame_idx begin at 1 for the first frame
        video_frame = cv2.imread(
            os.path.join(args.FRAMES_DIR, f"{frame_idx:04d}.jpg")
        )  # loads images in BGR format
        
        # Extract player crops for this frame
        player_crops, player_uuids = extract_player_regions(
            video_frame, 
            frame.data.regions, 
            player_recognition_params["min_detect_confidence"]
        )
        
        # Store crop data for batch processing
        for crop, uuid in zip(player_crops, player_uuids):
            all_crops_data.append((frame_idx, crop, uuid, video_frame))
    
    print(f"Collected {len(all_crops_data)} crops from {len(mot_data.frames)} frames")
    
    # Step 2: Batch process all crops with recognizer
    print("Processing crops with recognizer...")
    player_recognitions = recognize_player_numbers_batch(
        all_crops_data,
        recognizer=recognizer,
        debug_folder=debug_folder,
        use_grounding_dino=True,
    )

    print("done!")


if __name__ == "__main__":
    main()
