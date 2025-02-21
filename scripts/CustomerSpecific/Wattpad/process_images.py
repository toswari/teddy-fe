import os
import json
import time
import requests
import csv
from PIL import Image
import io
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime
from clarifai.client.app import App
from clarifai.client.auth import create_stub
from clarifai.client.auth.helper import ClarifaiAuthHelper
from clarifai.client.input import Inputs
from clarifai.client.model import Model
from dotenv import load_dotenv
import asyncio
from functools import partial
from concurrent.futures import TimeoutError

# Load environment variables
load_dotenv()
env_vars = os.environ
CLARIFAI_PAT = env_vars.get("CLARIFAI_PAT")
USER_ID = env_vars.get("USER_ID")

@dataclass
class ModelConfig:
    name: str
    url: str
    prompt: Optional[str] = None  # Custom prompt is now optional
    temperature: float = 0.8
    max_tokens: int = 512
    top_p: float = 0.8
    timeout: int = 30  # Add timeout parameter

@dataclass
class ProcessingConfig:
    input_json: str
    output_json: str
    image_folder: str
    default_prompt: str  # Default prompt for all models
    models: List[ModelConfig]
    max_images: Optional[int] = None  # Add max_images parameter, None means process all

# Add a class to track model performance
@dataclass
class ModelPerformance:
    total_time: float = 0.0
    call_count: int = 0
    success_count: int = 0
    timeout_count: int = 0
    error_count: int = 0
    
    @property
    def average_time(self) -> float:
        return self.total_time / self.call_count if self.call_count > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        return (self.success_count / self.call_count * 100) if self.call_count > 0 else 0.0

# Global dictionary to store performance metrics
model_performance: Dict[str, ModelPerformance] = {}

def setup_clarifai():
    """Initialize Clarifai client"""
    os.environ["CLARIFAI_PAT"] = CLARIFAI_PAT
    auth = ClarifaiAuthHelper.from_env(validate=False)
    stub = create_stub(auth)
    user_data_object = auth.get_user_app_id_proto()
    app = App(user_id=user_data_object.user_id, app_id=user_data_object.app_id)
    return auth, app

def image_to_bytes(image):
    """Convert PIL Image to bytes with proper format handling"""
    # Convert P (palette) or RGBA mode to RGB
    if image.mode in ('P', 'RGBA'):
        image = image.convert('RGB')
    
    with io.BytesIO() as buffer:
        image.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()

async def async_process_image(image_bytes, model_config: ModelConfig, config: ProcessingConfig, auth):
    """Async version of process_image with timeout"""
    try:
        # Use model-specific prompt if provided, otherwise use default prompt
        prompt = model_config.prompt or config.default_prompt
        
        llvm_class_model = Model(
            pat=auth._pat,
            url=model_config.url,
            user_id=USER_ID,
        )
        
        llvm_inference_params = {
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "top_p": model_config.top_p,
        }
        
        # Run the predict call in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(
                llvm_class_model.predict,
                inputs=[
                    Inputs.get_multimodal_input(
                        input_id="",
                        image_bytes=image_bytes,
                        raw_text=prompt,
                    )
                ],
                inference_params=llvm_inference_params,
            )
        )
        
        raw_output = response.outputs[0].data.text.raw
        clean_output = raw_output.replace("```json", "").replace("```", "").strip()
        print(f"Raw output from {model_config.name}: {raw_output}")
        
        try:
            return json.loads(clean_output)
        except json.JSONDecodeError:
            raise Exception("Failed to parse JSON response")
            
    except Exception as e:
        raise Exception(f"Model processing error: {str(e)}")

def process_image(image_bytes, model_config: ModelConfig, config: ProcessingConfig, auth, timeout_seconds=30):
    """Process single image through a model with timeout and performance tracking"""
    print(f"Classifying image with {model_config.name}...")
    
    # Initialize performance tracking for this model if not exists
    if model_config.name not in model_performance:
        model_performance[model_config.name] = ModelPerformance()
    
    perf = model_performance[model_config.name]
    start_time = time.time()
    
    try:
        # Run the async function with timeout
        result = asyncio.run(
            asyncio.wait_for(
                async_process_image(image_bytes, model_config, config, auth),
                timeout=timeout_seconds
            )
        )
        
        # Update performance metrics
        end_time = time.time()
        processing_time = end_time - start_time
        perf.total_time += processing_time
        perf.call_count += 1
        perf.success_count += 1
        
        print(f"{model_config.name} processed in {processing_time:.2f} seconds")
        return result
        
    except asyncio.TimeoutError:
        end_time = time.time()
        processing_time = end_time - start_time
        perf.total_time += processing_time
        perf.call_count += 1
        perf.timeout_count += 1
        
        print(f"Timeout: {model_config.name} took longer than {timeout_seconds} seconds")
        return {
            "predicted_category": "TIMEOUT",
            "reasoning": f"Model took longer than {timeout_seconds} seconds to respond",
            "confidence_score": 0,
            "processing_time": processing_time
        }
    except Exception as e:
        end_time = time.time()
        processing_time = end_time - start_time
        perf.total_time += processing_time
        perf.call_count += 1
        perf.error_count += 1
        
        print(f"Error with {model_config.name}: {str(e)}")
        return {
            "predicted_category": "ERROR",
            "reasoning": str(e),
            "confidence_score": 0,
            "processing_time": processing_time
        }

def print_performance_report():
    """Generate and print a performance report for all models"""
    print("\n=== Model Performance Report ===")
    print(f"{'Model Name':<30} | {'Avg Time':<10} | {'Success':<10} | {'Timeout':<10} | {'Error':<10} | {'Success Rate':<12}")
    print("-" * 90)
    
    for model_name, perf in model_performance.items():
        print(
            f"{model_name:<30} | "
            f"{perf.average_time:>8.2f}s | "
            f"{perf.success_count:>9} | "
            f"{perf.timeout_count:>9} | "
            f"{perf.error_count:>9} | "
            f"{perf.success_rate:>11.2f}%"
        )
    
    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"model_performance_{timestamp}.txt"
    
    with open(report_file, 'w') as f:
        f.write("=== Model Performance Report ===\n")
        f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"{'Model Name':<30} | {'Avg Time':<10} | {'Success':<10} | {'Timeout':<10} | {'Error':<10} | {'Success Rate':<12}\n")
        f.write("-" * 90 + "\n")
        
        for model_name, perf in model_performance.items():
            f.write(
                f"{model_name:<30} | "
                f"{perf.average_time:>8.2f}s | "
                f"{perf.success_count:>9} | "
                f"{perf.timeout_count:>9} | "
                f"{perf.error_count:>9} | "
                f"{perf.success_rate:>11.2f}%\n"
            )
    
    print(f"\nPerformance report saved to: {report_file}")

def generate_csv_headers(config: ProcessingConfig) -> List[str]:
    """Generate CSV headers based on the models configuration"""
    base_headers = [
        "Image ID",
        "Image URL",
        "WP Category",
        "WP Rating",
        "Image Filename"
    ]
    
    # Add headers for each model
    model_headers = []
    for model in config.models:
        model_prefix = f"{model.name}"
        model_headers.extend([
            f"{model_prefix} - Processing Time (s)",
            f"{model_prefix} - Predicted Category",
            f"{model_prefix} - Confidence Score",
            f"{model_prefix} - Reasoning",
            f"{model_prefix} - Status"  # SUCCESS/TIMEOUT/ERROR
        ])
    
    return base_headers + model_headers

def process_images_to_csv(config: ProcessingConfig, dataset: dict, auth, csv_output: str):
    """Process images and save results to CSV with detailed columns"""
    images_to_process = dataset["images"]
    if config.max_images:
        images_to_process = images_to_process[:config.max_images]
        print(f"Processing {config.max_images} images for testing")
    
    # Generate headers
    csv_headers = generate_csv_headers(config)
    
    with open(csv_output, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(csv_headers)
        
        # Process each image
        for image_info in images_to_process:
            image_path = os.path.join(config.image_folder, image_info["file_name"])
            
            if not os.path.exists(image_path):
                print(f"Image not found: {image_path}")
                continue
            
            # Find corresponding annotation
            annotation = next(
                (ann for ann in dataset["annotations"] if ann["image_id"] == image_info["id"]),
                None
            )
            
            if not annotation:
                continue
            
            # Initialize the row with basic image information
            row = [
                image_info["id"],
                image_info.get("url", ""),
                annotation.get("wp_category", ""),
                annotation.get("wp_rating", ""),
                image_info["file_name"]
            ]
            
            # Load and convert image to bytes
            with Image.open(image_path) as img:
                image_bytes = image_to_bytes(img)
            
            # Process through each model
            for model_config in config.models:
                try:
                    print(f"Processing image {image_info['id']} with model {model_config.name}")
                    result = process_image(image_bytes, model_config, config, auth, timeout_seconds=model_config.timeout)
                    
                    # Add this model's results to the row
                    status = "SUCCESS"
                    if result["predicted_category"] == "TIMEOUT":
                        status = "TIMEOUT"
                    elif result["predicted_category"] == "ERROR":
                        status = "ERROR"
                    
                    row.extend([
                        f"{result.get('processing_time', 0):.2f}",
                        result.get("predicted_category", ""),
                        result.get("confidence_score", 0),
                        result.get("reasoning", ""),
                        status
                    ])
                    
                except Exception as e:
                    print(f"Error processing {image_path} with model {model_config.name}: {str(e)}")
                    row.extend([
                        "0.00",  # processing time
                        "ERROR",  # predicted category
                        "0",     # confidence score
                        str(e),  # reasoning
                        "ERROR"  # status
                    ])
                
                time.sleep(2)  # Delay between model calls
            
            writer.writerow(row)
            print(f"Completed processing image {image_info['id']} through all models")
    
    print(f"Processing complete. Results saved to {csv_output}")

def main():
    # Define default prompt
    default_prompt = """You are responsible for moderating user-generated images submitted to an online storytelling community. These images are typically digital book covers or illustrations. The imagery depicted may be a photograph or an illustration and will range in style from realistic to rudimentary stick figure drawings. Regardless of style, each image should be treated with equal weight. Your task is to analyze the provided image and classify it according to the following taxonomy:

                - Safe: Image does not depict any nudity, sexual suggestion, sexual acts, self-harm, suicide, violence, blood, injuries, wounds, weapons, hate symbols, or CSEM.
                - Nudity_Okay: Images that suggest nudity without explicitly displaying it. This includes artistic or stylized silhouettes, bare shoulders or backs, sheer clothing that obscures explicit body parts, and people wearing swimsuits. Men's bare chests/nipples are allowed. Classic fine art depictions of nudity also fall here, as long as they are non-explicit.
                - Nudity_Mature: Images depicting partial nudity without sexual actions or genital exposure, including people in underwear, artistic depictions of nudity with no explicit genitalia focus, partially exposed bodies (e.g., topless but without full breast or nipple exposure), or excessive cleavage.
                - Nudity_Banned: Images that explicitly expose genitals (vulva, labia, penis, scrotum), uncovered breasts (including female nipples), or uncovered buttocks – even when partially visible through sheer clothing or minimal coverage (e.g., g-strings, thongs). Includes spread buttocks, nudity intended to arouse or shock, and scientific/medical nudity.
                - SexualContent_Okay: Sexually suggestive images that contain no nudity but are intentionally provocative. Examples include lingerie photography, romantic gestures (kissing, embracing), sensual poses, and excessive focus on body parts.
                - SexualContent_Mature: Images that suggest, but don’t graphically depict, sexual acts. Includes sexually suggestive themes like passionate kissing with partial nudity, touching over clothing, close-ups of clothed/partially-clothed body parts (chests, butts, hips, crotches), sensual non-explicit poses, BDSM elements (e.g., ropes, collars as fashion), or unused sex toys. Erotic but not pornographic.
                - SexualContent_Banned: Images depicting sexual activity (real or simulated), visible genitalia in sexual contexts, touching of genitalia, or explicit pornographic content. Sexual aspect takes precedence over nudity if both are present.
                - SelfHarm_Okay: No visible self-harm, injuries, or depictions of self-destructive behavior.
                - SelfHarm_Mature: Indirect references to self-harm, such as bandaged wounds or non-graphic portrayals of mental distress.
                - SelfHarm_Banned: Images showing self-inflicted wounds, scars from self-harm, active acts of self-injury (e.g., cutting, burning, purging), or depictions of suicide (e.g., hanging, overdosing, gun to head).
                - Violence_Okay: Images with no visible wounds, blood, weapons, or graphic acts of violence. May include mild, non-realistic depictions of aggression.
                - Violence_Mature: Limited depictions of violence, such as minimal blood, minor wounds, or combat scenarios with no severe harm (e.g., no broken limbs or gaping wounds). Includes weapons shown but not in use (e.g., firearms, swords).
                - Violence_Banned: Depictions of severe bodily harm, excessive blood, open wounds, dismemberment, gore, torture, extreme brutality, or weapons (especially firearms) in use (e.g., pointed at a living being or viewer).
                - CSEM: Any material depicting minors (or individuals appearing as minors) in a sexualized, nude, or exploitative manner, including explicit or implied sexual situations (real or AI-generated).

                For the provided image, return a strict response in the following JSON format without any additional text:

                ```json
                {
                "predicted_category": "<category_name>",
                "reasoning": "<detailed explanation>",
                "confidence_score": <integer between 1 and 100>
                }
                ```
                """

    # Define configuration with models and max_images
    config = ProcessingConfig(
        input_json="wattpad_dataset.json",
        output_json="wattpad_dataset_processed.json",
        image_folder="./images",
        default_prompt=default_prompt,
        max_images=10000,  # Process only 1 image for testing
        models=[
            # ModelConfig(
            #     name="qwen2-vl-7b-instruct-awq",
            #     url="https://clarifai.com/clarifai/vlm/models/Qwen2-VL-7B-Instruct-AWQ",
            #     timeout=200 
            # ),
            # ModelConfig(
            #     name="qwen2-vl-7b-instruct-3",
            #     url="https://clarifai.com/phatvo/text-generation/models/lmdeploy-Qwen_Qwen2-VL-7B-Instruct_3",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="internvl2-5-2b",
            #     url="https://clarifai.com/phatvo/text-generation/models/lmdeploy-internvl2_5-2b",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="llama3-11b-vision",
            #     url="https://clarifai.com/meta/Llama-3/models/llama3_2-11b-vision-instruct",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="gemini-1-5-flash",
            #     url="https://clarifai.com/gcp/generate/models/gemini-1_5-flash",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="florence2",
            #     url="https://clarifai.com/phatvo/text-generation/models/florence2",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="pixtral-12b",
            #     url="https://clarifai.com/mistralai/completion/models/pixtral-12b",
            #     timeout=200
            # ),
            ModelConfig(
                name="minicpm-o-2-6",
                url="https://clarifai.com/openbmb/miniCPM/models/minicpm-o-2_6",
                timeout=200
            ),
            # ModelConfig(
            #     name="fuyu-8b",
            #     url="https://clarifai.com/adept/fuyu/models/fuyu-8b",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="cogvlm-chat",
            #     url="https://clarifai.com/thudm/cogvlm/models/cogvlm-chat",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="qwen-vl-chat",
            #     url="https://clarifai.com/qwen/qwen-VL/models/qwen-VL-Chat",
            #     timeout=200  # Shorter timeout for faster models
            # ),
            # ModelConfig(
            #     name="llava-1-5-7b",
            #     url="https://clarifai.com/liuhaotian/llava/models/llava-1_5-7b",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="gpt-4o-mini",
            #     url="https://clarifai.com/openai/chat-completion/models/gpt-4o-mini",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="minicpm-llama3-v-2-5",
            #     url="https://clarifai.com/openbmb/miniCPM/models/miniCPM-Llama3-V-2_5",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="llava-v1-6-mistral-7b",
            #     url="https://clarifai.com/liuhaotian/llava/models/llava-v1_6-mistral-7b",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="florence-2-large",
            #     url="https://clarifai.com/microsoft/florence/models/florence-2-large",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="phi-3-vision-128k",
            #     url="https://clarifai.com/microsoft/text-generation/models/phi-3-vision-128k-instruct",
            #     timeout=200
            # ),
            ModelConfig(
                name="claude-3-sonnet",
                url="https://clarifai.com/anthropic/completion/models/claude-3-sonnet",
                timeout=200
            ),
            # ModelConfig(
            #     name="gemini-pro-vision",
            #     url="https://clarifai.com/gcp/generate/models/gemini-pro-vision",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="gemini-1-5-pro",
            #     url="https://clarifai.com/gcp/generate/models/gemini-1_5-pro",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="claude-3-5-sonnet",
            #     url="https://clarifai.com/anthropic/completion/models/claude-3_5-sonnet",
            #     timeout=200
            # ),
            ModelConfig(
                name="gpt-4o",
                url="https://clarifai.com/openai/chat-completion/models/gpt-4o",
                timeout=200
            ),
            # ModelConfig(
            #     name="claude-3-opus",
            #     url="https://clarifai.com/anthropic/completion/models/claude-3-opus",
            #     timeout=200
            # ),
            # ModelConfig(
            #     name="gpt-4-vision",
            #     url="https://clarifai.com/openai/chat-completion/models/openai-gpt-4-vision",
            #     timeout=200
            # ),
        ]
    )
    
    # Setup Clarifai
    auth, app = setup_clarifai()
    
    # Load input dataset
    with open(config.input_json, 'r') as f:
        dataset = json.load(f)
    
    # Generate a timestamp for the output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_output = f"model_results_{timestamp}.csv"
    
    # Process images and generate CSV
    process_images_to_csv(config, dataset, auth, csv_output)
    
    # Print performance report at the end
    print_performance_report()

if __name__ == "__main__":
    main()
    
