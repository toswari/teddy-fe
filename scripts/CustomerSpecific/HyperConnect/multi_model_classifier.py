import os
import csv
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any
from clarifai.client.workflow import Workflow


def get_category_name(category_code: str) -> str:
    """Map category codes to human-readable names based on Initial_Prompt.txt classification system."""
    category_mapping = {
        # Parent categories
        '1': 'SEVERE VIOLENCE',
        '2': 'FELONY CRIME', 
        '3': 'SEXUAL VIOLENCE',
        '4': 'TERRORISM',
        '5': 'SUICIDE',
        '6': 'CSAM',
        '7': 'PROHIBITED ITEM SALES',
        '8': 'INNOCENT',
        
        # Category 1: SEVERE VIOLENCE subcategories
        '1.1': 'SEVERE VIOLENCE - Shooting Incident',
        '1.2': 'SEVERE VIOLENCE - Life-Threatening Assault',
        '1.3': 'SEVERE VIOLENCE - Group Assault',
        '1.0.0': 'SEVERE VIOLENCE - General/Other',
        
        # Category 2: FELONY CRIME subcategories
        '2.1': 'FELONY CRIME - Murder/Attempted Murder',
        '2.2': 'FELONY CRIME - Kidnapping/Attempted Kidnapping',
        '2.0.0': 'FELONY CRIME - General/Other',
        
        # Category 3: SEXUAL VIOLENCE subcategories
        '3.1': 'SEXUAL VIOLENCE - Non-Consensual Acts',
        '3.0.0': 'SEXUAL VIOLENCE - General/Other',
        
        # Category 4: TERRORISM subcategories
        '4.1': 'TERRORISM - Attacks/Damage Sites',
        '4.2': 'TERRORISM - Public Threats',
        '4.0.0': 'TERRORISM - General/Other',
        
        # Category 5: SUICIDE subcategories
        '5.1': 'SUICIDE - Attempts/Self-Harm',
        '5.0.0': 'SUICIDE - General/Other',
        
        # Category 6: CSAM subcategories
        '6.1': 'CSAM - Violence Against Minors',
        '6.2': 'CSAM - Sex Crimes Involving Minors',
        '6.3': 'CSAM - Child Sexual Abuse Material',
        '6.0.0': 'CSAM - General/Other',
        
        # Category 7: PROHIBITED ITEM SALES subcategories
        '7.1': 'PROHIBITED SALES - Weapons/Explosives',
        '7.2': 'PROHIBITED SALES - Illegal Drugs/Substances',
        '7.3': 'PROHIBITED SALES - Toxic/Hazardous Materials',
        '7.4': 'PROHIBITED SALES - Counterfeit/Fraud Tools',
        '7.0.0': 'PROHIBITED SALES - General/Other',
        
        # Category 8: INNOCENT subcategories
        '8.0.0': 'INNOCENT - All Others'
    }
    
    return category_mapping.get(category_code, f'Unknown Category ({category_code})')


def setup_workflow(pat_token: str) -> Workflow:
    """Initialize the Clarifai workflow with authentication."""
    workflow_url = "https://clarifai.com/clarifai/HyperConnect/workflows/POC-initial"
    return Workflow(url=workflow_url, pat=pat_token)


def get_image_files(directory: str) -> List[str]:
    """Get all image files from directory using os.walk."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    image_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if Path(file).suffix.lower() in image_extensions:
                image_files.append(os.path.join(root, file))
    
    return image_files


def process_image_by_path(workflow: Workflow, image_path: str) -> Dict[str, Any]:
    """Process a single image file and return structured results."""
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        result = workflow.predict_by_bytes(input_bytes=image_bytes, input_type="image")
        return parse_all_clarifai_results(result, image_path, "file")
    
    except Exception as e:
        return create_error_result(image_path, "file", str(e))


def process_image_by_url(workflow: Workflow, image_url: str) -> Dict[str, Any]:
    """Process a single image URL and return structured results."""
    try:
        result = workflow.predict_by_url(image_url, input_type="image")
        return parse_all_clarifai_results(result, image_url, "url")
    
    except Exception as e:
        return create_error_result(image_url, "url", str(e))


def create_error_result(source: str, source_type: str, error_message: str) -> Dict[str, Any]:
    """Create a standardized error result."""
    return {
        'source': source,
        'source_type': source_type,
        'status': 'error',
        'error_message': error_message,
        # Main classification (MiniCPM model)
        'main_predicted_category': None,
        'main_category_name': None,
        'main_reasoning': None,
        'main_confidence_score': None,
        # Basic moderation (Clarifai main model)
        'basic_moderation_suggestive': None,
        'basic_moderation_explicit': None,
        'basic_moderation_safe': None,
        'basic_moderation_drug': None,
        'basic_moderation_gore': None,
        # Detailed moderation (datastrategy model)
        'detailed_moderation_top_concept': None,
        'detailed_moderation_top_score': None,
        'detailed_moderation_concepts': None,
        # Raw results
        'raw_main_result': None,
        'raw_basic_moderation': None,
        'raw_detailed_moderation': None
    }


def parse_all_clarifai_results(result: Any, source: str, source_type: str) -> Dict[str, Any]:
    """Parse all Clarifai API results from multiple models."""
    try:
        # Initialize result structure
        parsed_result = {
            'source': source,
            'source_type': source_type,
            'status': 'success',
            'error_message': None,
            # Main classification (MiniCPM model)
            'main_predicted_category': None,
            'main_category_name': None,
            'main_reasoning': None,
            'main_confidence_score': None,
            # Basic moderation (Clarifai main model)
            'basic_moderation_suggestive': None,
            'basic_moderation_explicit': None,
            'basic_moderation_safe': None,
            'basic_moderation_drug': None,
            'basic_moderation_gore': None,
            # Detailed moderation (datastrategy model)
            'detailed_moderation_top_concept': None,
            'detailed_moderation_top_score': None,
            'detailed_moderation_concepts': None,
            # Raw results
            'raw_main_result': None,
            'raw_basic_moderation': None,
            'raw_detailed_moderation': None
        }
        
        # Check the status of the response
        if hasattr(result, 'status'):
            status = result.status
            if status.code != 10000:  # 10000 is success in Clarifai
                return {
                    'source': source,
                    'source_type': source_type,
                    'status': 'api_error',
                    'error_message': f'API Error {status.code}: {status.description} - {status.details}',
                    'main_predicted_category': None,
                    'main_category_name': None,
                    'main_reasoning': None,
                    'main_confidence_score': None,
                    'basic_moderation_suggestive': None,
                    'basic_moderation_explicit': None,
                    'basic_moderation_safe': None,
                    'basic_moderation_drug': None,
                    'basic_moderation_gore': None,
                    'detailed_moderation_top_concept': None,
                    'detailed_moderation_top_score': None,
                    'detailed_moderation_concepts': None,
                    'raw_main_result': str(result),
                    'raw_basic_moderation': None,
                    'raw_detailed_moderation': None
                }
        
        if hasattr(result, 'results') and result.results:
            first_result = result.results[0]
            if hasattr(first_result, 'outputs') and first_result.outputs:
                # Process each output
                for i, output in enumerate(first_result.outputs):
                    if hasattr(output, 'data') and hasattr(output, 'model'):
                        model_info = output.model
                        model_id = model_info.id if hasattr(model_info, 'id') else f"model_{i}"
                        
                        # Process based on model ID
                        if model_id == "MiniCPM-o-2_6-language":
                            # Main classification model
                            parse_main_classification(output.data, parsed_result)
                        elif model_id == "moderation-recognition":
                            # Basic moderation model
                            parse_basic_moderation(output.data, parsed_result)
                        elif model_id == "moderation-all-resnext-2":
                            # Detailed moderation model
                            parse_detailed_moderation(output.data, parsed_result)
        
        return parsed_result
    
    except Exception as e:
        # For parse errors, we still need to include the main_category_name field
        return {
            'source': source,
            'source_type': source_type,
            'status': 'parse_error',
            'error_message': f'Failed to parse result: {str(e)}',
            'main_predicted_category': None,
            'main_category_name': None,
            'main_reasoning': None,
            'main_confidence_score': None,
            'basic_moderation_suggestive': None,
            'basic_moderation_explicit': None,
            'basic_moderation_safe': None,
            'basic_moderation_drug': None,
            'basic_moderation_gore': None,
            'detailed_moderation_top_concept': None,
            'detailed_moderation_top_score': None,
            'detailed_moderation_concepts': None,
            'raw_main_result': str(result) if result else None,
            'raw_basic_moderation': None,
            'raw_detailed_moderation': None
        }


def parse_main_classification(data_obj: Any, result: Dict[str, Any]):
    """Parse main classification results from MiniCPM model."""
    try:
        if hasattr(data_obj, 'text') and data_obj.text and data_obj.text.raw:
            text_content = data_obj.text.raw.strip()
            
            # Extract JSON from markdown or direct
            json_content = None
            if text_content.startswith('```json') and text_content.endswith('```'):
                json_content = text_content[7:-3].strip()
            elif text_content.startswith('[') or text_content.startswith('{'):
                json_content = text_content
            
            if json_content:
                try:
                    parsed_data = json.loads(json_content)
                    if isinstance(parsed_data, list) and len(parsed_data) > 0:
                        top_result = parsed_data[0]
                        category_code = top_result.get('predicted_category')
                        result['main_predicted_category'] = category_code
                        result['main_category_name'] = get_category_name(category_code) if category_code else None
                        result['main_reasoning'] = top_result.get('reasoning')
                        result['main_confidence_score'] = top_result.get('confidence_score')
                        result['raw_main_result'] = json.dumps(parsed_data)
                    elif isinstance(parsed_data, dict):
                        category_code = parsed_data.get('predicted_category')
                        result['main_predicted_category'] = category_code
                        result['main_category_name'] = get_category_name(category_code) if category_code else None
                        result['main_reasoning'] = parsed_data.get('reasoning')
                        result['main_confidence_score'] = parsed_data.get('confidence_score')
                        result['raw_main_result'] = json.dumps(parsed_data)
                except json.JSONDecodeError:
                    result['raw_main_result'] = json_content
    except Exception as e:
        result['error_message'] = f"Main classification parse error: {str(e)}"


def parse_basic_moderation(data_obj: Any, result: Dict[str, Any]):
    """Parse basic moderation results from Clarifai main model."""
    try:
        if hasattr(data_obj, 'concepts') and data_obj.concepts:
            concepts = {}
            all_concepts = []
            for concept in data_obj.concepts:
                concept_data = {
                    'name': concept.name,
                    'value': concept.value,
                    'id': concept.id
                }
                all_concepts.append(concept_data)
                concepts[concept.name] = concept.value
            
            # Extract specific concepts
            result['basic_moderation_suggestive'] = concepts.get('suggestive')
            result['basic_moderation_explicit'] = concepts.get('explicit')
            result['basic_moderation_safe'] = concepts.get('safe')
            result['basic_moderation_drug'] = concepts.get('drug')
            result['basic_moderation_gore'] = concepts.get('gore')
            result['raw_basic_moderation'] = json.dumps(all_concepts)
    except Exception as e:
        result['error_message'] = f"Basic moderation parse error: {str(e)}"


def parse_detailed_moderation(data_obj: Any, result: Dict[str, Any]):
    """Parse detailed moderation results from datastrategy model."""
    try:
        if hasattr(data_obj, 'concepts') and data_obj.concepts:
            all_concepts = []
            for concept in data_obj.concepts:
                concept_data = {
                    'name': concept.name,
                    'value': concept.value,
                    'id': concept.id
                }
                all_concepts.append(concept_data)
            
            if all_concepts:
                # Sort by confidence and get top result
                sorted_concepts = sorted(all_concepts, key=lambda x: x['value'], reverse=True)
                top_concept = sorted_concepts[0]
                
                result['detailed_moderation_top_concept'] = top_concept['name']
                result['detailed_moderation_top_score'] = top_concept['value']
                # Store top 10 concepts as JSON
                result['detailed_moderation_concepts'] = json.dumps(sorted_concepts[:10])
                result['raw_detailed_moderation'] = json.dumps(all_concepts)
    except Exception as e:
        result['error_message'] = f"Detailed moderation parse error: {str(e)}"


def write_results_to_csv(results: List[Dict[str, Any]], output_file: str):
    """Write all results to a CSV file."""
    if not results:
        print("No results to write.")
        return
    
    fieldnames = [
        'source', 'source_type', 'status', 'error_message',
        # Main classification fields
        'main_predicted_category', 'main_category_name', 'main_confidence_score', 'main_reasoning',
        # Basic moderation fields
        'basic_moderation_suggestive', 'basic_moderation_explicit', 'basic_moderation_safe',
        'basic_moderation_drug', 'basic_moderation_gore',
        # Detailed moderation fields
        'detailed_moderation_top_concept', 'detailed_moderation_top_score', 'detailed_moderation_concepts',
        # Raw results fields
        'raw_main_result', 'raw_basic_moderation', 'raw_detailed_moderation'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"Results written to {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Process images with all models in Clarifai workflow')
    parser.add_argument('--directory', '-d', help='Directory containing images to process')
    parser.add_argument('--urls', '-u', nargs='+', help='List of image URLs to process')
    parser.add_argument('--output', '-o', default='multi_model_results.csv', help='Output CSV file')
    parser.add_argument('--pat-token', '-p', default='pat here', help='Clarifai PAT token')
    
    args = parser.parse_args()
    
    if not args.directory and not args.urls:
        args.directory = "images/"
    
    # Initialize workflow
    workflow = setup_workflow(args.pat_token)
    results = []
    
    # Process directory images
    if args.directory:
        if not os.path.exists(args.directory):
            print(f"Directory {args.directory} does not exist")
            return
        
        image_files = get_image_files(args.directory)
        print(f"Found {len(image_files)} image files in {args.directory}")
        
        for i, image_path in enumerate(image_files, 1):
            print(f"Processing {i}/{len(image_files)}: {os.path.basename(image_path)}")
            result = process_image_by_path(workflow, image_path)
            results.append(result)
    
    # Process URLs
    if args.urls:
        print(f"Processing {len(args.urls)} URLs")
        for i, url in enumerate(args.urls, 1):
            print(f"Processing URL {i}/{len(args.urls)}: {url}")
            result = process_image_by_url(workflow, url)
            results.append(result)
    
    # Write results to CSV
    write_results_to_csv(results, args.output)
    
    # Print summary
    successful = len([r for r in results if r['status'] == 'success'])
    errors = len([r for r in results if r['status'] in ['error', 'parse_error', 'api_error']])
    print(f"\nSummary: {successful} successful, {errors} errors, {len(results)} total")
    
    # Print sample results
    if results and results[0]['status'] == 'success':
        print("\nSample result (first successful image):")
        sample = next(r for r in results if r['status'] == 'success')
        print(f"  Main Classification: {sample.get('main_predicted_category')} - {sample.get('main_category_name')} (confidence: {sample.get('main_confidence_score')})")
        print(f"  Basic Moderation - Suggestive: {sample.get('basic_moderation_suggestive'):.4f}" if sample.get('basic_moderation_suggestive') else "  Basic Moderation - Suggestive: N/A")
        print(f"  Detailed Moderation - Top: {sample.get('detailed_moderation_top_concept')} ({sample.get('detailed_moderation_top_score'):.4f})" if sample.get('detailed_moderation_top_concept') else "  Detailed Moderation - Top: N/A")


if __name__ == "__main__":
    main()