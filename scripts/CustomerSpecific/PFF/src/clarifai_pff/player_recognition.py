import cv2
import numpy as np
import easyocr
from PIL import Image
from collections import defaultdict, Counter


def extract_player_regions(frame, detections):
    player_crops = []
    player_boxes = []
    
    for region in detections:
        if hasattr(region, 'data') and region.data.concepts and region.data.concepts[0].name == 'players':
            x1 = region.region_info.bounding_box.left_col * frame.shape[1]
            y1 = region.region_info.bounding_box.top_row * frame.shape[0]
            x2 = region.region_info.bounding_box.right_col * frame.shape[1]
            y2 = region.region_info.bounding_box.bottom_row * frame.shape[0]
            
            crop = frame[int(y1):int(y2), int(x1):int(x2)]
            player_crops.append(crop) # uint8, shape (height, width, 3) Values: 0-255 for each RGB channel
            player_boxes.append((x1, y1, x2, y2))
    
    return player_crops, player_boxes


def player_recognition(player_crop):
    if player_crop.size == 0:
        return -1, 0.0
    
    img = Image.fromarray(cv2.cvtColor(player_crop, cv2.COLOR_BGR2RGB))
    img_resized = img.resize((128, 128))
    
    reader = easyocr.Reader(['en'], gpu=False)
    results = reader.readtext(np.array(img_resized), allowlist='0123456789')
    
    if results:
        bbox, text, confidence = results[0]
        try:
            number = int(text)
            if 0 <= number <= 99:
                return number, confidence
        except ValueError:
            pass
    
    return -1, 0.0


def recognize_player_numbers(frame, detections):
    player_crops, player_boxes = extract_player_regions(frame, detections)
    results = []
    
    for crop, box in zip(player_crops, player_boxes):
        number, confidence = player_recognition(crop)
        results.append({
            'bbox': box,
            'player_number': number,
            'confidence': confidence
        })
    
    return results


def assign_player_ids_to_tracks(track_data, player_recognitions):
    track_player_votes = defaultdict(list)
    
    for frame_idx, recognitions in player_recognitions.items():
        frame_tracks = track_data[track_data['frame'] == frame_idx]
        
        for _, track in frame_tracks.iterrows():
            track_box = (track['x'], track['y'], track['xx'], track['yy'])
            
            for recognition in recognitions:
                if recognition['player_number'] != -1:
                    print(track_box, recognition['bbox'])
                    if boxes_overlap(track_box, recognition['bbox']):
                        track_player_votes[track['object_id']].append(
                            (recognition['player_number'], recognition['confidence'])
                        )
    
    track_player_assignments = {}
    for track_id, votes in track_player_votes.items():
        if votes:
            vote_counts = defaultdict(int)
            for number, confidence in votes:
                vote_counts[number] += 1
            
            best_number = max(vote_counts.items(), key=lambda x: x[1])
            track_player_assignments[track_id] = best_number[0]
    
    return track_player_assignments


def boxes_overlap(box1, box2):
    x1, y1, x2, y2 = box1
    a1, b1, a2, b2 = box2
    
    return x1 == a1 and y1 == b1 and x2 == a2 and y2 == b2