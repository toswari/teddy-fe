import os
import json
from PIL import Image

def create_coco_annotation(directory):
    coco_annotation = {
        "images": [],
        "annotations": [],
        "categories": [
            {"id": 1, "name": "Fails", "supercategory": "Quality"},
            {"id": 2, "name": "Pass", "supercategory": "Quality"},
            {"id": 3, "name": "Poor Image Quality", "supercategory": "Quality"}
        ],
        "info": {
            "year": 2025,
            "version": "1.0",
            "description": "COCO annotations for image quality check"
        }
    }
    annotation_id = 1
    image_id = 1
    for quality_folder in os.listdir(directory):
        quality_folder_path = os.path.join(directory, quality_folder)
        if os.path.isdir(quality_folder_path):
            for reason_folder in os.listdir(quality_folder_path):
                reason_folder_path = os.path.join(quality_folder_path, reason_folder)
                if os.path.isdir(reason_folder_path):
                    for img_file in os.listdir(reason_folder_path):
                        img_path = os.path.join(reason_folder_path, img_file)
                        
                        if img_file.lower().endswith(('png', 'jpg', 'jpeg')):
                            abs_img_path = os.path.abspath(img_path)

                            with Image.open(abs_img_path) as img:
                                width, height = img.size
                            image_info = {
                                "id": image_id,
                                "file_name": abs_img_path,
                                "width": width,
                                "height": height
                            }
                            coco_annotation["images"].append(image_info)
                            annotation = {
                                "id": annotation_id,
                                "image_id": image_id,
                                "category_id": 1 if quality_folder == "Fails" else 2 if quality_folder == "Passes" else 3,
                                "bbox": [0, 0, width, height], 
                                "area": width * height,
                                "attributes": {"reason": reason_folder}
                            }
                            coco_annotation["annotations"].append(annotation)
                            image_id += 1
                            annotation_id += 1
    with open("impression_check_annotations.json", "w") as f:
        json.dump(coco_annotation, f, indent=4)
root_directory = "Impression Check"
create_coco_annotation(root_directory)
