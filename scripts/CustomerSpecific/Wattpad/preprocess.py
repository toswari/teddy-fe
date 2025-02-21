import csv
import requests 
import os
import json
import shutil
import cv2
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

# First part: Download images
with open('Testing Wattpad Prompt on Minicpm-o-2_6  - Results for Prompt #1.csv', 'r') as file:
    reader = csv.reader(file)
    header = next(reader)
    for row in reader:
        url = row[1]
        response = requests.get(url)
        if response.status_code == 200:
            # Check if the directory exists, if not create it
            if not os.path.exists('./images'):
                os.makedirs('./images')
            
            # Now write the file
            with open(f'./images/{row[0]}.jpg', 'wb') as f:
                f.write(response.content)
                print(f'Downloaded {row[0]}.jpg')

# Second part: Create COCO JSON
coco_format = {
    "info": {
        "description": "Wattpad Image Dataset",
        "version": "1.0",
        "year": 2024,
        "contributor": "Augment"
    },
    "images": [],
    "categories": [],
    "annotations": []
}

# Read CSV again to create JSON
with open('Testing Wattpad Prompt on Minicpm-o-2_6  - Results for Prompt #1.csv', 'r') as file:
    reader = csv.reader(file)
    header = next(reader)
    
    # Create unique categories from WP Category and Rating combinations
    categories = set()
    
    for row in reader:
        image_id = int(row[0])
        url = row[1]
        wp_category = row[2]
        wp_rating = row[3]
        category = f"{wp_category}_{wp_rating}"
        categories.add(category)
        
        # Get image dimensions
        image_path = f'./images/{image_id}.jpg'
        if os.path.exists(image_path):
            try:
                img = cv2.imread(image_path)
                height, width = img.shape[:2]
            except:
                height, width = 0, 0  # Default if image can't be read
        else:
            height, width = 0, 0  # Default if image doesn't exist
        
        # Add image info
        image_info = {
            "id": image_id,
            "file_name": f"{image_id}.jpg",
            "width": width,
            "height": height,
            "url": url
        }
        coco_format["images"].append(image_info)
        
        # Add annotation
        annotation = {
            "id": image_id,
            "image_id": image_id,
            "category_id": len(coco_format["categories"]) + 1,
            "wp_category": wp_category,
            "wp_rating": wp_rating,
            "model_prediction": row[6] if len(row) > 6 else "",
            "category_correct": row[7] if len(row) > 7 else "",
            "rating_correct": row[8] if len(row) > 8 else "",
            "model_response": row[9] if len(row) > 9 else ""
        }
        coco_format["annotations"].append(annotation)

# Add categories
for idx, category in enumerate(sorted(categories), 1):
    category_info = {
        "id": idx,
        "name": category,
        "supercategory": category.split('_')[0]
    }
    coco_format["categories"].append(category_info)

# Save the COCO JSON file
with open('wattpad_dataset.json', 'w') as f:
    json.dump(coco_format, f, indent=2)

print("COCO JSON file created successfully!")

