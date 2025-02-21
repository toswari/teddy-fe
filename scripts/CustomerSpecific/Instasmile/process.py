import os
import json
from PIL import Image
import uuid

def generate_hex_name():
    """Generate a unique hex name for an image"""
    return uuid.uuid4().hex[:12]

def count_all_images(directory):
    total_images = 0
    found_images = []
    image_extensions = ('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG')
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(image_extensions):
                # Clean up filename by removing "Copy of " prefix
                clean_filename = file[8:] if file.startswith("Copy of ") else file
                full_path = os.path.join(root, file)
                total_images += 1
                found_images.append(full_path)  # Store full path instead of relative
    return total_images, found_images

def normalize_path(path):
    """Normalize path for consistent comparison"""
    # Convert to absolute path first, then normalize
    abs_path = os.path.abspath(path)
    return os.path.normpath(abs_path).lower().replace('\\', '/')

def process_single_image(item_path, quality_folder, current_image_id, current_annotation_id, directory, processed_files, skipped_images, valid_categories, coco_annotation):
    """Process a single image file"""
    norm_path = normalize_path(item_path)
    
    if norm_path in processed_files:
        error_msg = f"Image already processed (relative path: {os.path.relpath(item_path, directory)})"
        print(f"Warning: {error_msg}")
        skipped_images.append((item_path, error_msg))
        return current_image_id, current_annotation_id
    
    if quality_folder not in valid_categories:
        error_msg = f"Invalid quality folder: {quality_folder}"
        print(f"Warning: {error_msg}")
        skipped_images.append((item_path, error_msg))
        return current_image_id, current_annotation_id
    
    try:
        with Image.open(item_path) as img:
            width, height = img.size
    except Exception as e:
        error_msg = f"Failed to open image: {str(e)}"
        print(f"Error: {error_msg}")
        skipped_images.append((item_path, error_msg))
        return current_image_id, current_annotation_id
    
    # Use existing filename instead of generating a new one
    clean_filename = os.path.basename(item_path)
    rel_path = os.path.relpath(item_path, directory)
    
    image_info = {
        "id": current_image_id,
        "file_name": rel_path,
        "original_name": rel_path,  # Keep the same name since it's already renamed
        "width": width,
        "height": height
    }
    coco_annotation["images"].append(image_info)
    
    # Get the directory path relative to the quality folder
    rel_dir = os.path.relpath(os.path.dirname(item_path), os.path.join(directory, quality_folder))
    
    # Get the original reason, ignoring "1st Batch" directory
    path_parts = [part for part in rel_dir.split(os.sep) if part != "1st Batch"]
    original_reason = path_parts[0] if path_parts else ""
    mapped_reason = get_mapped_reason(original_reason)
    
    annotation = {
        "id": current_annotation_id,
        "image_id": current_image_id,
        "category_id": valid_categories[quality_folder],
        "bbox": [0, 0, width, height],
        "area": width * height,
        "attributes": {
            "reason": mapped_reason,  # Use the mapped reason instead of original
            "original_reason": original_reason,  # Keep original reason for reference
            "original_name": rel_path
        }
    }
    coco_annotation["annotations"].append(annotation)
    
    processed_files.add(norm_path)
    #print(f"Successfully processed: {rel_path} -> {new_rel_path}")
    
    return current_image_id + 1, current_annotation_id + 1

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
    
    processed_files = set()
    skipped_images = []
    ignored_folders = set()
    annotation_id = 1
    image_id = 1
    
    valid_categories = {
        "Fails": 1, 
        "Passes": 2, 
        "Pass": 2,
        "Poor Image Quality": 3,
        "Poor_Image_Quality": 3,
        "PoorImageQuality": 3,
        "Poor-Image-Quality": 3,
        "Fail": 1,
        "Failed": 1,
        "Passed": 2
    }
    
    # Get absolute path of directory
    directory = os.path.abspath(directory)
    
    # First, get total count of images
    total_images, all_image_paths = count_all_images(directory)
    all_images = {normalize_path(path) for path in all_image_paths}
    
    print(f"\nInitial scan found {total_images} images in total")
    
    # Process each quality folder
    for quality_folder in os.listdir(directory):
        quality_folder_path = os.path.join(directory, quality_folder)
        if not os.path.isdir(quality_folder_path):
            continue
            
        normalized_quality_folder = quality_folder.replace(" ", "_")
        if normalized_quality_folder not in valid_categories:
            ignored_folders.add(quality_folder)
            print(f"\nSkipping folder {quality_folder} - not a valid category folder")
            continue
        
        print(f"\nProcessing quality folder: {quality_folder}")
        
        # Get all image files in this quality folder and its subdirectories
        image_files = []
        for root, _, files in os.walk(quality_folder_path):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.PNG', '.JPG', '.JPEG')):
                    image_files.append(os.path.join(root, file))
        
        # Process each image
        for image_path in image_files:
            image_id, annotation_id = process_single_image(
                image_path,
                quality_folder,
                image_id,
                annotation_id,
                directory,
                processed_files,
                skipped_images,
                valid_categories,
                coco_annotation
            )

    # Output results
    with open("impression_check_annotations.json", "w") as f:
        json.dump(coco_annotation, f, indent=4)

    print("\n=== Processing Statistics ===")
    print(f"Total images found in directory: {total_images}")
    print(f"Total images processed successfully: {len(processed_files)}")
    print(f"Total annotations created: {len(coco_annotation['annotations'])}")
    
    if ignored_folders:
        print("\n=== Ignored Folders ===")
        for folder in ignored_folders:
            print(f"- {folder}")
    
    if skipped_images:
        print("\n=== Skipped Images ===")
        for img_path, error in skipped_images:
            print(f"- {img_path}")
            print(f"  Error: {error}")
            print()
    
    unprocessed = all_images - processed_files
    if unprocessed:
        print(f"\n=== Unprocessed Images ({len(unprocessed)}) ===")
        # Convert back to relative paths for display
        for path in unprocessed:
            rel_path = os.path.relpath(path, directory)
            print(f"- {rel_path}")
    
    if total_images != len(processed_files):
        print(f"\nWARNING: {total_images - len(processed_files)} images were not processed!")

def get_mapped_reason(original_reason):
    """Map long reason strings to shorter versions"""
    reason_mapping = {
        # Fails category
        "Tray Position - Not centrally aligned in the tray": "tray_misaligned",
        "Underboiled - tray smooth still see the outline": "underboiled",
        "Overboiled - Bubbles all on the putty and teeth": "overboiled",
        "Depth - Teeth not fully pushed into the tray": "depth_issue",
        "Distortion - Margins of teeth not clear or fuzzy": "distortion_issue",
        
        # Poor Image Quality category
        "BLURRY": "blurry",
        "INCORRECT ANGLE": "bad_angle",
        "TOO DARK": "too_dark",
    }
    
    # if original_reason not in reason_mapping:
    #     print(f"Unmapped reason found: {original_reason}")
    
    return reason_mapping.get(original_reason, original_reason)

if __name__ == "__main__":
    root_directory = "Impression Check"
    create_coco_annotation(root_directory)
