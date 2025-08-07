import json
import csv
from clarifai.client.workflow import Workflow
import os
from pathlib import Path

def process_image_classification(image_path, workflow_url, pat):
    """Process a single image and return parsed results from both models"""
    
    # Create workflow
    workflow = Workflow(url=workflow_url, pat=pat)
    
    # Load image
    with open(image_path, 'rb') as f:
        imagebytes = f.read()
    
    # Get predictions
    result = workflow.predict_by_bytes(input_bytes=imagebytes, input_type="image")
    
    # Parse results
    parsed_results = {
        'image_path': image_path,
        'filename': os.path.basename(image_path)
    }
    
    # Model 1: JSON-based Recognition Models (Output 1)
    if len(result.results[0].outputs) > 1:
        json_text = result.results[0].outputs[1].data.text.raw
        # Extract JSON from the markdown code block
        json_start = json_text.find('[')
        json_end = json_text.rfind(']') + 1
        if json_start != -1 and json_end != 0:
            json_data = json.loads(json_text[json_start:json_end])
            
            # Process JSON model responses (typically multiple identical models)
            if json_data:
                # Use the first model's scores (they're typically identical)
                scores = json_data[0]["Scores"]
                
                # Model 1: Content moderation categories
                if "moderation-recognition" in scores:
                    mod_scores = scores["moderation-recognition"]
                    parsed_results.update({
                        'model1_drug': mod_scores.get("drug", 0),
                        'model1_explicit': mod_scores.get("explicit", 0),
                        'model1_gore': mod_scores.get("gore", 0),
                        'model1_safe': mod_scores.get("safe", 0),
                        'model1_suggestive': mod_scores.get("suggestive", 0)
                    })
                
                # Model 1: Additional categories (NSFW and hate symbols)
                if "nsfw-recognition" in scores:
                    parsed_results.update({
                        'model1_nsfw_sfw': scores["nsfw-recognition"].get("sfw", 0),
                        'model1_nsfw_nsfw': scores["nsfw-recognition"].get("nsfw", 0)
                    })
                
                if "hate-symbol-detection" in scores:
                    hate_symbols = scores["hate-symbol-detection"]
                    parsed_results['model1_hate_symbols'] = len(hate_symbols) > 0
                
    
    # Model 2: Concepts Model (Output 2)
    if len(result.results[0].outputs) > 2:
        concepts = result.results[0].outputs[2].data.concepts
        
        # Model 2: Same content categories for comparison
        for concept in concepts:
            parsed_results[f'model2_{concept.name}'] = concept.value
    
    # Determine if models agree on dominant category
    comparable_categories = ['drug', 'explicit', 'gore', 'safe', 'suggestive']
    
    # Find model 1 dominant category
    model1_scores = {cat: parsed_results.get(f'model1_{cat}', 0) for cat in comparable_categories}
    model1_dominant = max(model1_scores, key=model1_scores.get) if model1_scores else None
    
    # Find model 2 dominant category  
    model2_scores = {cat: parsed_results.get(f'model2_{cat}', 0) for cat in comparable_categories}
    model2_dominant = max(model2_scores, key=model2_scores.get) if model2_scores else None
    
    # Check if they agree
    parsed_results['models_agree'] = model1_dominant == model2_dominant and model1_dominant is not None
    parsed_results['model1_dominant'] = model1_dominant
    parsed_results['model2_dominant'] = model2_dominant
    
    return parsed_results

def process_all_images(images_dir, output_csv, workflow_url, pat):
    """Process all images in directory and save to CSV"""
    
    # Find all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.avif'}
    image_files = []
    
    for root, dirs, files in os.walk(images_dir):
        for file in files:
            if Path(file).suffix.lower() in image_extensions:
                image_files.append(os.path.join(root, file))
    
    if not image_files:
        print("No image files found!")
        return
    
    print(f"Found {len(image_files)} image files")
    
    # Process all images
    all_results = []
    for i, image_path in enumerate(image_files, 1):
        print(f"Processing {i}/{len(image_files)}: {os.path.basename(image_path)}")
        try:
            result = process_image_classification(image_path, workflow_url, pat)
            all_results.append(result)
        except Exception as e:
            print(f"Error processing {image_path}: {e}")
            continue
    
    if not all_results:
        print("No results to save!")
        return
    
    # Define column order
    fieldnames = [
        'filename',
        'image_path',
        'model1_drug',
        'model1_explicit',
        'model1_gore',
        'model1_safe',
        'model1_suggestive',
        'model1_nsfw_nsfw',
        'model1_nsfw_sfw',
        'model1_hate_symbols',
        'model2_drug',
        'model2_explicit',
        'model2_gore',
        'model2_safe',
        'model2_suggestive',
        'models_agree',
        'model1_dominant',
        'model2_dominant'
    ]
    
    # Write to CSV
    with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    
    print(f"Results saved to {output_csv}")
    print(f"Processed {len(all_results)} images successfully")

if __name__ == "__main__":
    # Configuration
    workflow_url = "https://clarifai.com/clarifai/OpenTable_Review/workflows/comparison"
    pat = "PAT HERE"
    images_dir = "Images"
    output_csv = "classification_results.csv"
    
    # Process all images
    process_all_images(images_dir, output_csv, workflow_url, pat)