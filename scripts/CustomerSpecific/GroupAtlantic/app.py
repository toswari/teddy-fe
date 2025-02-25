import os
import shutil
from PIL import Image
import numpy as np
from clarifai.client.model import Model
from clarifai.client.input import Inputs
from clarifai.client.auth.helper import ClarifaiAuthHelper
from dotenv import load_dotenv
import io
import sys

# Load environment variables
load_dotenv()
CLARIFAI_PAT = os.getenv("CLARIFAI_PAT")
USER_ID = os.getenv("USER_ID")

def setup_clarifai():
    """Initialize Clarifai client"""
    os.environ["CLARIFAI_PAT"] = CLARIFAI_PAT
    auth = ClarifaiAuthHelper.from_env(validate=False)
    return auth

def image_to_bytes(image: Image.Image) -> bytes:
    """Convert PIL Image to bytes"""
    with io.BytesIO() as buffer:
        image.save(buffer, format='JPEG')
        return buffer.getvalue()

def create_output_directories(base_dir):
    """Create output directories if they don't exist"""
    object_present_dir = os.path.join(base_dir, 'object_present')
    not_present_dir = os.path.join(base_dir, 'not_present')
    
    os.makedirs(object_present_dir, exist_ok=True)
    os.makedirs(not_present_dir, exist_ok=True)
    
    return object_present_dir, not_present_dir

def parse_llm_response(response_text):
    """
    Parse LLM response to determine if object is present and confidence level
    Returns: (is_present, confidence_level, is_certain)
    """
    try:
        # Try to extract JSON from the response
        import json
        # Remove any potential markdown formatting
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        response_json = json.loads(clean_text)
        
        # Parse the JSON response
        is_present = response_json["present"].lower() == "yes"
        confidence_level = int(response_json["confidence"])
        reasoning = response_json.get("reasoning", "").lower()
        
        # Automatically mark as not present with 100% confidence if it's a document/text
        if any(keyword in reasoning for keyword in ['document', 'text', 'paper', 'printed', 'writing']):
            return False, 100, True
        
        # Different confidence thresholds for present vs not present
        if is_present:
            is_certain = confidence_level >= 80  # Must be 90%+ confident it IS present
        else:
            is_certain = confidence_level >= 100  # Must be 100% confident it's NOT present
        
        return is_present, confidence_level, is_certain
    except:
        # Fallback to original text parsing if JSON parsing fails
        response_lower = response_text.lower()
        
        # Check for document/text indicators in the response
        if any(keyword in response_lower for keyword in ['document', 'text', 'paper', 'printed', 'writing']):
            return False, 100, True
        
        is_present = None
        if 'yes' in response_lower.split():
            is_present = True
        elif 'no' in response_lower.split():
            is_present = False
        
        try:
            numbers = [int(s) for s in response_lower.split() if s.isdigit()]
            confidence_level = next((n for n in numbers if 0 <= n <= 100), 0)
        except:
            confidence_level = 0
        
        # Apply same confidence thresholds to text parsing
        if is_present:
            is_certain = confidence_level >= 95
        else:
            is_certain = confidence_level >= 95
        
        return is_present, confidence_level, is_certain

def get_reference_object_description(object_image_path, auth):
    """Get LLM description of the reference object to use in comparison prompt"""
    # Load and convert image
    object_image = Image.open(object_image_path)
    image_bytes = image_to_bytes(object_image)
    
    # Initialize the model
    model = Model(
        pat=auth._pat,
        url="https://clarifai.com/openai/chat-completion/models/gpt-4o",
        user_id=USER_ID,
    )
    
    # Define the prompt for reference object
    reference_prompt = """In this image, a green outlined grid displays multiple examples of the object we're seeking, providing a clear basis for identification. Describe this object in a single, detailed paragraph, focusing solely on: 1) What type of object it is—such as its specific function or purpose (e.g., a sensor, tool, or mechanical part); 2) Its key physical characteristics, including its color (e.g., metallic, matte, or multi-toned), shape (e.g., cylindrical, flat, or irregular), and components (e.g., wires, connectors, or moving parts); 3) How it's typically installed or connected, detailing its attachment method (e.g., bolted to a surface, inserted into a system, or wired into a larger mechanism). Craft the response as a seamless, flowing paragraph that paints a vivid and precise picture of the object, suitable for someone unfamiliar with it to recognize it clearly."""

    try:
        # Get description from LLM
        response = model.predict(
            inputs=[
                Inputs.get_multimodal_input(
                    input_id="",
                    image_bytes=image_bytes,
                    raw_text=reference_prompt,
                )
            ],
            inference_params={
                "temperature": 0.7,
                "max_tokens": 512,
            }
        )
        
        return response.outputs[0].data.text.raw
    
    except Exception as e:
        print(f"Error getting reference object description: {str(e)}")
        return None

def create_reference_grid(directory_path):
    """Create a grid image from all chip images with minimal white space"""
    # Get all chip images
    chip_images = [f for f in os.listdir(directory_path) 
                  if f.lower().startswith('chip') and 
                  f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
    
    if not chip_images:
        raise Exception("No chip images found! Images should be named chip1.jpg, chip2.jpg, etc.")
    
    # Load all images and calculate their aspect ratios
    images_with_ratios = []
    for f in chip_images:
        img = Image.open(os.path.join(directory_path, f))
        # Add green border to each image
        border_width = 3  # Width of the green border
        bordered_img = Image.new('RGB', (img.size[0] + 2*border_width, img.size[1] + 2*border_width), (0, 255, 0))  # Green border
        bordered_img.paste(img, (border_width, border_width))
        aspect_ratio = bordered_img.size[0] / bordered_img.size[1]
        images_with_ratios.append((bordered_img, aspect_ratio))
    
    # Sort images by aspect ratio (wide to narrow)
    images_with_ratios.sort(key=lambda x: x[1], reverse=True)
    images = [img for img, _ in images_with_ratios]
    
    # Set minimum target height
    MIN_TARGET_HEIGHT = 300
    target_height = max(MIN_TARGET_HEIGHT, min(img.size[1] for img in images))
    
    # Resize images while maintaining aspect ratio
    resized_images = []
    for img in images:
        aspect_ratio = img.size[0] / img.size[1]
        new_width = int(target_height * aspect_ratio)
        resized_images.append(img.resize((new_width, target_height), Image.Resampling.LANCZOS))
    
    # Calculate number of rows based on number of images
    num_images = len(resized_images)
    rows = max(1, round(num_images ** 0.5))  # Square root for approximate square grid
    
    # Calculate optimal row arrangements to minimize white space
    current_row = []
    rows_of_images = []
    current_row_width = 0
    target_row_width = sum(img.size[0] for img in resized_images) / rows
    
    for img in resized_images:
        if current_row_width + img.size[0] > target_row_width and current_row:
            rows_of_images.append(current_row)
            current_row = []
            current_row_width = 0
        current_row.append(img)
        current_row_width += img.size[0]
    
    if current_row:
        rows_of_images.append(current_row)
    
    # Calculate final grid dimensions
    max_row_width = max(sum(img.size[0] for img in row) for row in rows_of_images)
    grid_height = target_height * len(rows_of_images)
    
    # Create the grid image with a small gap between images
    gap = 5  # Gap between images in pixels
    grid_image = Image.new('RGB', 
                          (max_row_width + gap * (len(rows_of_images[0]) - 1), 
                           grid_height + gap * (len(rows_of_images) - 1)), 
                          'white')
    
    # Paste images into grid with gaps
    y_offset = 0
    for row in rows_of_images:
        x_offset = 0
        for img in row:
            grid_image.paste(img, (x_offset, y_offset))
            x_offset += img.size[0] + gap
        y_offset += target_height + gap
    
    return grid_image

def compare_and_sort_images(directory_path):
    """Compare images against reference grid and sort them"""
    # Setup Clarifai
    auth = setup_clarifai()
    
    # Create reference grid from root directory first
    print("Creating reference grid from chip images in root directory...")
    root_dir = os.path.dirname(os.path.abspath(__file__))
    reference_grid = create_reference_grid(root_dir)
    
    # Save grid in the target directory
    grid_path = os.path.join(directory_path, 'reference_grid.jpg')
    reference_grid.save(grid_path)
    print(f"Reference grid saved to: {grid_path}")
    
    # Create analyzed_images directory
    analyzed_dir = os.path.join(directory_path, 'analyzed_images')
    os.makedirs(analyzed_dir, exist_ok=True)
    
    # Create output directories
    object_present_dir, not_present_dir = create_output_directories(directory_path)
    
    # Get all image files from the directory (excluding chip images and grid)
    image_files = [f for f in os.listdir(directory_path) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))
                  and not f.lower().startswith('chip')
                  and f != 'reference_grid.jpg'
                  and os.path.isfile(os.path.join(directory_path, f))]
    
    total_images = len(image_files)
    processed_count = 0
    skipped_count = 0
    
    print(f"\nFound {total_images} images to process")
    
    # Now get the description using the grid image
    reference_description = get_reference_object_description(grid_path, auth)
    
    if not reference_description:
        print("Failed to get reference object description, using default description...")
        reference_description = "a temperature sensor or thermocouple. These sensors are primarily black and brass with some electrical components, have a cylindrical shape with a narrow probe extending from them, and are attached to wires for transmitting data or power. They are typically connected to pipes for monitoring or controlling temperature or flow."
    
    # Initialize the model
    model = Model(
        pat=auth._pat,
        url="https://clarifai.com/anthropic/completion/models/claude-3-sonnet", #"https://clarifai.com/openai/chat-completion/models/gpt-4o",
        user_id=USER_ID,
    )

    # Define the prompt using the reference description
    prompt = f"""Compare the two images shown side by side with a red line separating them. The image on the left shows a grid of reference images with a green border containing the object we're looking for - {reference_description}

Is this object present in the image on the right? It may be at a different scale, angle, or slightly obscured behind other objects. If the image is of a document or an image of an image, it should be 100% certain it is not present.

Respond ONLY with a JSON object in the following format:
{{
    "present": "YES" or "NO",
    "confidence": <number between 0 and 100>,
    "reasoning": "<brief explanation of your decision>"
}}

Be precise and ensure your confidence value is as accurate as possible."""
    
    for image_file in image_files:
        processed_count += 1
        print(f"\nProcessing image {processed_count}/{total_images}: {image_file}")
        
        # Load the image from the directory
        dir_image_path = os.path.join(directory_path, image_file)
        dir_image = Image.open(dir_image_path)
        
        # Create side-by-side comparison image
        height = max(reference_grid.size[1], dir_image.size[1])
        grid_resized = reference_grid.resize((int(reference_grid.size[0] * height / reference_grid.size[1]), height))
        dir_image_resized = dir_image.resize((int(dir_image.size[0] * height / dir_image.size[1]), height))
        
        # Add 10 pixels for red separator line
        separator_width = 10
        new_image_width = grid_resized.size[0] + separator_width + dir_image_resized.size[0]
        new_image = Image.new('RGB', (new_image_width, height), 'white')
        
        # Paste grid on left
        new_image.paste(grid_resized, (0, 0))
        
        # Draw red separator line
        for x in range(grid_resized.size[0], grid_resized.size[0] + separator_width):
            for y in range(height):
                new_image.putpixel((x, y), (255, 0, 0))  # RGB for red
        
        # Paste query image on right
        new_image.paste(dir_image_resized, (grid_resized.size[0] + separator_width, 0))
        
        # Save the comparison image
        comparison_path = os.path.join(analyzed_dir, f'analyzed_{image_file}')
        new_image.save(comparison_path)
        print(f"Saved comparison image to: {comparison_path}")
        
        try:
            # Send to LLM for comparison
            response = model.predict(
                inputs=[
                    Inputs.get_multimodal_input(
                        input_id="",
                        image_bytes=image_to_bytes(new_image),
                        raw_text=prompt,
                    )
                ],
                inference_params={
                    "temperature": 0.8,
                    "max_tokens": 512,
                }
            )
            
            # Get the response text
            response_text = response.outputs[0].data.text.raw
            print("\nLLM Analysis:", response_text)
            
            # Parse the response
            is_present, confidence, is_certain = parse_llm_response(response_text)
            
            if is_certain:
                # Move the image to appropriate directory
                destination_dir = object_present_dir if is_present else not_present_dir
                destination_path = os.path.join(destination_dir, image_file)
                shutil.move(dir_image_path, destination_path)
                print(f"Moved to: {'object_present' if is_present else 'not_present'} (Confidence: {confidence}%)")
            else:
                skipped_count += 1
                print(f"Skipped due to uncertainty (Confidence: {confidence}%)")
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            skipped_count += 1
            continue
    
    print(f"\nProcessing complete!")
    print(f"Total images processed: {total_images}")
    print(f"Images skipped due to uncertainty: {skipped_count}")
    print(f"Images sorted: {total_images - skipped_count}")

def reset_sorted_images(directory_path):
    """Move all sorted images back to the original directory"""
    # Get paths for the sorted directories
    object_present_dir = os.path.join(directory_path, 'object_present')
    not_present_dir = os.path.join(directory_path, 'not_present')
    analyzed_dir = os.path.join(directory_path, 'analyzed_images')
    
    moved_count = 0
    print("\nResetting sorted images...")
    
    # Move images from object_present back to main directory
    if os.path.exists(object_present_dir):
        for image_file in os.listdir(object_present_dir):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                source_path = os.path.join(object_present_dir, image_file)
                dest_path = os.path.join(directory_path, image_file)
                shutil.move(source_path, dest_path)
                moved_count += 1
    
    # Move images from not_present back to main directory
    if os.path.exists(not_present_dir):
        for image_file in os.listdir(not_present_dir):
            if image_file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                source_path = os.path.join(not_present_dir, image_file)
                dest_path = os.path.join(directory_path, image_file)
                shutil.move(source_path, dest_path)
                moved_count += 1
    
    # Remove the reference grid if it exists
    grid_path = os.path.join(directory_path, 'reference_grid.jpg')
    if os.path.exists(grid_path):
        os.remove(grid_path)
        print("Removed reference grid")
    
    # Remove analyzed images directory and its contents
    if os.path.exists(analyzed_dir):
        shutil.rmtree(analyzed_dir)
        print("Removed analyzed images directory")
    
    # Try to remove empty directories
    try:
        if os.path.exists(object_present_dir):
            os.rmdir(object_present_dir)
        if os.path.exists(not_present_dir):
            os.rmdir(not_present_dir)
    except OSError as e:
        print(f"Note: Could not remove directories: {str(e)}")
    
    print(f"Reset complete! Moved {moved_count} images back to original directory")

if __name__ == "__main__":
    directory_path = './SFDownload'
    # Add argument handling for reset
    if len(sys.argv) > 1 and sys.argv[1] == '--reset':
        reset_sorted_images(directory_path)
    else:
        compare_and_sort_images(directory_path)

