#!/usr/bin/env python
"""
Model Inspector - Determine supported classes for a PyTorch model
"""

import os
import sys
import torch
import json
import numpy as np
from PIL import Image
import cv2

# Try importing ultralytics if available
try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
    print("Ultralytics library available - will try YOLO model loading")
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    print("Ultralytics library not found - will try standard PyTorch loading")

def load_model_torch(model_path):
    """Load model using standard PyTorch methods"""
    print(f"Attempting to load model from {model_path} using PyTorch")
    
    # Check if file exists
    if not os.path.exists(model_path):
        print(f"Error: Model file not found at {model_path}")
        return None
    
    # Try loading as regular PyTorch model
    try:
        model = torch.load(model_path, map_location='cpu')
        print(f"Successfully loaded model with torch.load()")
        print(f"Model type: {type(model)}")
        return model, "torch"
    except Exception as e:
        print(f"Error loading with torch.load: {e}")
    
    # Try loading as TorchScript model
    try:
        model = torch.jit.load(model_path, map_location='cpu')
        print(f"Successfully loaded model with torch.jit.load()")
        print(f"Model type: {type(model)}")
        return model, "torchscript"
    except Exception as e:
        print(f"Error loading with torch.jit.load: {e}")
    
    print(f"Failed to load model using PyTorch methods")
    return None, None

def load_model_ultralytics(model_path):
    """Load model using ultralytics YOLO"""
    if not ULTRALYTICS_AVAILABLE:
        print("Ultralytics not available")
        return None, None
    
    print(f"Attempting to load model from {model_path} using Ultralytics YOLO")
    
    try:
        model = YOLO(model_path)
        print(f"Successfully loaded model with YOLO()")
        print(f"Model type: {type(model)}")
        return model, "ultralytics"
    except Exception as e:
        print(f"Error loading with YOLO(): {e}")
    
    print(f"Failed to load model using Ultralytics methods")
    return None, None

def get_classes_torch(model):
    """Try to determine class names from a PyTorch model"""
    classes = None
    
    # Check if model has a classes attribute directly
    if hasattr(model, 'classes'):
        classes = model.classes
        print(f"Found classes directly as model attribute")
        
    # Check if model has a names attribute (common in some models)
    elif hasattr(model, 'names'):
        classes = model.names
        print(f"Found classes as 'names' attribute")
    
    # For more complex models, try to find class names in various attributes
    elif hasattr(model, 'module') and hasattr(model.module, 'classes'):
        classes = model.module.classes
        print(f"Found classes in model.module.classes")
    
    # If no classes found, try to examine output layer
    elif hasattr(model, 'fc') and hasattr(model.fc, 'out_features'):
        num_classes = model.fc.out_features
        print(f"Found {num_classes} output classes, but no class labels")
        classes = [f"class_{i}" for i in range(num_classes)]
    
    return classes

def get_classes_ultralytics(model):
    """Get class names from an ultralytics model"""
    if hasattr(model, 'names'):
        print(f"Found class names in YOLO model")
        return model.names
    
    return None

def test_inference(model, model_type):
    """Run test inference to see outputs"""
    print("\nRunning test inference...")
    
    # Create a dummy input (assuming image input)
    dummy_input = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    
    if model_type == "ultralytics":
        # For YOLO models
        results = model(dummy_input)
        print(f"YOLO model outputs: {type(results)}")
        # Extract class info from results
        if hasattr(results, 'names'):
            print(f"Classes from results: {results.names}")
        return
    
    # For PyTorch models
    try:
        # Convert to tensor
        input_tensor = torch.FloatTensor(dummy_input).permute(2, 0, 1).unsqueeze(0) / 255.0
        
        # Run inference
        model.eval()
        with torch.no_grad():
            output = model(input_tensor)
        
        print(f"Model output type: {type(output)}")
        
        # If output is a tensor, print shape and a few elements
        if isinstance(output, torch.Tensor):
            print(f"Output tensor shape: {output.shape}")
            if len(output.shape) == 2 and output.shape[1] > 1:
                print(f"This looks like a classification model with {output.shape[1]} classes")
                # Get top class
                _, predicted = torch.max(output, 1)
                print(f"Top predicted class index: {predicted.item()}")
        
        # If output is a dict, examine keys
        elif isinstance(output, dict):
            print(f"Output keys: {list(output.keys())}")
            if 'logits' in output:
                logits = output['logits']
                print(f"Logits shape: {logits.shape}")
                if len(logits.shape) == 2:
                    print(f"This looks like a classification model with {logits.shape[1]} classes")
    
    except Exception as e:
        print(f"Error during inference: {e}")

def inspect_yolo_output(model):
    """
    Run a dummy inference and print whether the model returns boxes, keypoints, or both.
    """
    dummy_img = np.zeros((480, 640, 3), dtype=np.uint8)
    try:
        results = model(dummy_img, verbose=False)
        print("\n--- YOLO Model Output Inspector ---")
        if hasattr(results[0], 'boxes') and results[0].boxes is not None:
            print("Model returns bounding boxes.")
            print(f"boxes: {results[0].boxes}")
        if hasattr(results[0], 'keypoints') and results[0].keypoints is not None:
            print("Model returns keypoints.")
            print(f"keypoints: {results[0].keypoints}")
        print(f"Full result attributes: {dir(results[0])}")
        print("--- End YOLO Model Output Inspector ---\n")
    except Exception as e:
        print(f"Error inspecting YOLO model output: {e}")

def main():
    print("Model Inspector - Determine supported classes\n")
    
    # Determine model path
    model_paths = []
    
    # Check command line argument
    if len(sys.argv) > 1:
        model_paths.append(sys.argv[1])
    
    # Check common locations
    common_paths = [
        './model/court_keypoint_detector.pt',
    ]
    
    model_paths.extend(common_paths)
    
    # Try loading the model
    model = None
    model_type = None
    
    for path in model_paths:
        if os.path.exists(path):
            print(f"Found model at: {path}")
            
            # Try ultralytics first if available
            if ULTRALYTICS_AVAILABLE:
                model, model_type = load_model_ultralytics(path)
                
            # If ultralytics failed or not available, try torch
            if model is None:
                model, model_type = load_model_torch(path)
            
            if model is not None:
                break
    
    if model is None:
        print("Failed to load model from any location. Available paths:")
        for path in model_paths:
            exists = "exists" if os.path.exists(path) else "doesn't exist"
            print(f" - {path} ({exists})")
        return
    
    # Try to determine classes
    classes = None
    if model_type == "ultralytics":
        classes = get_classes_ultralytics(model)
        inspect_yolo_output(model)
    else:  # torch or torchscript
        classes = get_classes_torch(model)
    
    # Print detected classes
    if classes:
        print("\nDetected classes:")
        for i, class_name in enumerate(classes):
            print(f"{i}: {class_name}")
        
        # Create a config example
        config = {
            "classes": classes if isinstance(classes, list) else list(classes.values()),
            "target_class": classes[0] if isinstance(classes, list) else list(classes.values())[0],
            "model": {
                "path": model_paths[0] if model else "unknown",
                "input_size": [224, 224],
                "batch_size": 8
            },
            "video": {
                "min_clip_duration": 1.0,
                "sampling_rate": 5
            }
        }
        
        print("\nSuggested config.json:")
        print(json.dumps(config, indent=2))
        
        # Save config to file
        with open('detected_config.json', 'w') as f:
            json.dump(config, indent=2, fp=f)
        print("\nConfig saved to detected_config.json")
    else:
        print("\nCould not determine class names from model")
        
    # Run test inference
    test_inference(model, model_type)

if __name__ == "__main__":
    main() 