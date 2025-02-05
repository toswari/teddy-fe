import os
import io
import json
import time
import cv2
import numpy as np
from PIL import PngImagePlugin, Image, ImageDraw, ImageFont
import pyzbar.pyzbar as pyzbar
from typing import Optional, List
from dataclasses import dataclass
from clarifai.client.app import App
from clarifai.client.auth import create_stub
from clarifai.client.auth.helper import ClarifaiAuthHelper
from clarifai.client.input import Inputs
from clarifai.client.model import Model
from PIL import ImageDraw, ImageFont
from dotenv import load_dotenv


load_dotenv()
#read the environment variables
env_vars = os.environ
epat = env_vars["PAT"]
euid = env_vars["UID"]


@dataclass
class Config:
    input_folder: str
    output_folder: str
    prompt: str
    user_id: Optional[str] = None
    user_pat: Optional[str] = None
    llvm_model_url: Optional[str] = None
    llvm_temp: float = 0.8
    llvm_max_tokens: int = 512
    llvm_top_p: float = 0.8

config = Config(
    input_folder="./Impression Check",
    output_folder="./output_folder",
    prompt = (
        f"You are evaluating dental impression trays to determine if they meet the quality standards for dental modeling. Classify impressions as **Pass** or **Fail** based on the following criteria:\n\n"

        f"**Critical Pass Criteria:**\n"
        f"- **Clarity**: The teeth should show visible and identifiable features like gum lines. **Some blurring or out-of-focus areas are acceptable if key features remain identifiable and evaluable.**\n"
        f"- **Depth**: The impression must capture enough depth to show the full contours of the front teeth.\n"
        f"- **Crispness**: The edges of the front teeth should be reasonably defined. **Minor blurring or smoothing is acceptable as long as major features are still discernible.**\n"
        f"- **Surface Texture**: There should be no major bubbles or texture defects that obscure key features. **Minor imperfections, rough textures, or small air bubbles are acceptable if they do not affect the evaluation of the impression.**\n"
        f"- **Margins**: Margins around the front teeth should be visible. **Slight inconsistencies or soft edges are acceptable unless they prevent identification of the margins entirely.**\n\n"

        f"**Fail Criteria:**\n"
        f"- **Clarity**: If extreme distortion prevents identification of key features like gum lines, the impression will fail.\n"
        f"- **Depth**: A shallow impression where the any part of the tray is visible within hte impression and obstructs the key features will fail.\n"
        f"- **Crispness**: If the edges of the front teeth are so undefined that they cannot be reasonably evaluated, the impression will fail.\n"
        f"- **Surface Texture**: Large bubbles, cracks, or texture issues that significantly obscure critical features must result in a fail.\n"
        f"- **Margins**: Margins around the front teeth must be discernible. If they are completely missing, indistinct, or overly distorted, the impression will fail.\n\n"

        f"**Ignore the Following:**\n"
        f"- Minor imperfections or bubbles in non-critical areas, such as molars or excess material, that do not affect the impression of the front teeth.\n"
        f"- **Blurring or out-of-focus areas that do not prevent the identification of critical features.**\n\n"

        f"**Output Format:**\n"
        f"Return results in strict JSON format:\n"
        f"{{\n"
        f"  \"Result\": \"Pass\", or \"Fail\"\n"
        f"  \"Reasons\": [\n"
        f"    \"Reason 1\",\n"
        f"    \"Reason 2\"\n"
        f"  ],\n"
        f"  \"Suggested Fixes\": \"Provide actionable fixes for failed impressions as well as a detailed explanation of why it failed.\"\n"
        f"}}"
    ),
    user_id=euid,
    user_pat=epat,
    llvm_model_url="https://clarifai.com/openai/chat-completion/models/gpt-4o",
)
os.environ["CLARIFAI_PAT"] = config.user_pat
auth = ClarifaiAuthHelper.from_env(validate=False)
stub = create_stub(auth)
userDataObject = auth.get_user_app_id_proto()
app = App(user_id=userDataObject.user_id, app_id=userDataObject.app_id)
def image_to_bytes(image):
    with io.BytesIO() as buffer:
        image.save(buffer, format="PNG")
        return buffer.getvalue()
def classify_image(image_bytes):
    print("Classifying image...")
    prompt = config.prompt
    llvm_class_model = Model(
        pat=auth._pat,
        url=config.llvm_model_url,
        user_id=config.user_id,
    )
    llvm_inference_params = {
        "temperature": config.llvm_temp,
        "max_tokens": config.llvm_max_tokens,
        "top_p": config.llvm_top_p,
    }
    response = llvm_class_model.predict(
        inputs=[
            Inputs.get_multimodal_input(
                input_id="",
                image_bytes=image_bytes,
                raw_text=prompt,
            )
        ],
        inference_params=llvm_inference_params,
    )
    raw_output = response.outputs[0].data.text.raw
    clean_output = raw_output.replace("```json", "").replace("```", "").strip()
    try:
        output_json = json.loads(clean_output)
        return output_json
    except json.JSONDecodeError:
        return classify_image(image_bytes)


def draw_results_on_image(image, result, reasons, suggestions):
    draw = ImageDraw.Draw(image)
    font_size = 10
    font_path = "arial.ttf" 
    image_width, image_height = image.size 
    def wrap_text(text, font, max_width):
        words = text.split(' ')
        lines = []
        current_line = ''
        for word in words:
            test_line = current_line + word + ' '
            if draw.textbbox((0, 0), test_line, font=font)[2] <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word + ' '
        lines.append(current_line)
        return "\n".join(lines)
    text = f"Result: {result}\n"
    if result == "Fail":
        text += "Reasons:\n" + "\n".join(reasons)
        text += "\nSuggested Fixes:\n" + repr(suggestions)
    while True:
        font = ImageFont.truetype(font_path, font_size)
        wrapped_text = wrap_text(text, font, image_width - 40) 
        text_bbox = draw.textbbox((0, 0), wrapped_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        if text_width <= image_width - 40 and text_height <= image_height - 40:
            break
        font_size -= 5 
    padding = 20
    background_area = [
        (10, 10), 
        (10 + text_width + padding, 10 + text_height + padding) 
    ]
    draw.rectangle(background_area, fill="white")
    draw.text((20, 20), wrapped_text, font=font, fill="black") 
    return image

def write_metadata_to_image(image, metadata, output_path):
    metadata_str = json.dumps(metadata)
    print(f"Metadata: {metadata_str}")
    png_info = PngImagePlugin.PngInfo()
    png_info.add_text("metadata", metadata_str)
    png_info.add_text("Author", "ClarifaiFieldEngineering")
    image.save(output_path, pnginfo=png_info)

def existing_metadata(image_path):
    image = Image.open(image_path)
    metadata = image.info
    metadata_str = metadata.get("metadata")
    if metadata_str:
        metadata_json = json.loads(metadata_str)
        return metadata_json
    return {}

def check_if_already_processed(image_path):
    metadata = existing_metadata(image_path)
    if metadata:
        result = metadata.get("Result")
        if result:
            return True
    return False
   
def resize_image(image, max_size=(2000, 2000)):
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    return image

def process_images(input_folder, output_folder):
    total_processing_time = 0
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    image_files = []
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.endswith(('.png', '.jpg', '.jpeg', 'JPG')):
                image_files.append(os.path.join(root, file))
    for image_path in image_files:
        image_file = os.path.basename(image_path)
        start_time = time.time()
        relative_path = os.path.relpath(image_path, input_folder)
        parent_dir = os.path.dirname(relative_path)
        pass_dir = os.path.join(output_folder, parent_dir, 'Pass')
        fail_dir = os.path.join(output_folder, parent_dir, 'Fail')
        os.makedirs(pass_dir, exist_ok=True)
        os.makedirs(fail_dir, exist_ok=True)
        image_pil = Image.open(image_path).convert("RGBA")
        image_pil = resize_image(image_pil)
        image_bytes = image_to_bytes(image_pil)
        results_json = classify_image(image_bytes)
        result = results_json.get("Result", "Unknown")
        reasons = results_json.get("Reasons", [])
        print(f"Image: {image_file}, Result: {result}, Reasons: {reasons}")
        image_pil = draw_results_on_image(image_pil, result, reasons, results_json.get("Suggested Fixes", ""))
        result_folder = pass_dir if result == "Pass" else fail_dir
        result_filename = os.path.splitext(image_file)[0] + f"_{result}.png"
        result_path = os.path.join(result_folder, result_filename)
        image_pil.save(result_path)
        end_time = time.time()
        processing_time = end_time - start_time
        total_processing_time += processing_time
        print(f"Processing of {image_path} took {processing_time:.8f} seconds")
        write_metadata_to_image(image_pil, results_json, result_path)
    print(f"Processed {len(image_files)} images in {total_processing_time:.8f} seconds. "
          f"Average time per image: {total_processing_time / len(image_files):.8f} seconds.")

if __name__ == "__main__":
    input_folder = config.input_folder
    output_folder = config.output_folder
    process_images(input_folder, output_folder)
