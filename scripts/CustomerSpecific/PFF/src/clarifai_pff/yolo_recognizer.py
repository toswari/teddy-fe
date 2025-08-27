#!/usr/bin/env python3
"""
YOLOv7 Recognizer for player number recognition
Provides same interface as EasyOCRRecognizer
"""

import os
import sys
import cv2
import tempfile
import subprocess
import glob
import shutil
from pathlib import Path
import yaml


class YOLORecognizer:
    """
    YOLOv7-based recognizer that matches EasyOCRRecognizer interface
    """
    
    def __init__(self, **kwargs):
        """
        Initialize YOLOv7 recognizer
        
        Args:
            model_path: Path to YOLOv7 model weights (.pt file)
            yolov7_dir: Path to YOLOv7 repository directory
            confidence_threshold: Minimum confidence threshold for detections
            device: Device to run inference on ('cpu' or '0' for GPU)
        """
        ##self.model_path = kwargs.get('model_path', "/Users/bingqingyu/Code/Personal/yolov7/yolov7_training.pt")
        self.model_path = kwargs.get('model_path', "/Users/bingqingyu/Downloads/weights/best.pt")
        self.yolov7_dir = kwargs.get('yolov7_dir', "/Users/bingqingyu/Code/Personal/yolov7")
        self.confidence_threshold = kwargs.get('confidence_threshold', 0.3)
        self.device = kwargs.get('device', 'cpu')
        
        # Validate paths
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model weights not found: {self.model_path}")
        if not os.path.exists(self.yolov7_dir):
            raise FileNotFoundError(f"YOLOv7 directory not found: {self.yolov7_dir}")
        
        # Create temp directory for inference
        self.temp_dir = Path(tempfile.mkdtemp(prefix='yolo_recognizer_'))
        self._setup_temp_workspace()
        
    
    def _get_default_yolov7_dir(self):
        """Get default path to YOLOv7 directory"""
        # Navigate to scripts/PlayerID/yolov7 from src/clarifai_pff/
        current_dir = Path(__file__).parent
        yolov7_dir = current_dir.parent.parent / "scripts" / "PlayerID" / "yolov7"
        
        if yolov7_dir.exists():
            return str(yolov7_dir)
        
        raise FileNotFoundError("YOLOv7 directory not found. Please specify yolov7_dir.")
    
    def _setup_temp_workspace(self):
        """Setup temporary workspace for inference"""
        # Create directory structure for single image inference
        self.temp_images_dir = self.temp_dir / "images"
        self.temp_labels_dir = self.temp_dir / "labels"
        self.temp_images_dir.mkdir(parents=True, exist_ok=True)
        
        # Create minimal data.yaml for single image inference
        self.data_yaml_path = self.temp_dir / "data.yaml"
        self.class_names = ['0', '1', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '2', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '3', '30', '31', '32', '33', '34', '35', '36', '37', '38', '39', '4', '40', '41', '42', '43', '44', '45', '46', '47', '48', '49', '5', '50', '51', '52', '53', '54', '55', '56', '57', '58', '59', '6', '60', '61', '62', '63', '64', '65', '66', '67', '68', '69', '7', '70', '71', '72', '73', '74', '75', '76', '77', '78', '79', '8', '80', '81', '82', '83', '84', '85', '86', '87', '88', '89', '9', '90', '91', '92', '93', '94', '95', '96', '97', '98', '99']
        data_config = {
            'test': str(self.temp_images_dir),
            'nc': 100,  # 10 classes for digits 0-9
            'names': self.class_names}
        
        with open(self.data_yaml_path, 'w') as f:
            yaml.dump(data_config, f)
    
    def recognize(self, player_crop):
        """
        Recognize player number from crop using YOLOv7
        
        Args:
            player_crop: numpy array (BGR format from OpenCV)
            
        Returns:
            tuple: (number, confidence) where:
                - number: int, detected number (0-99) or -1 if no detection
                - confidence: float, detection confidence (0.0-1.0)
        """
        
        # Save crop as temporary image
        temp_image_path = self.temp_images_dir / "temp_crop.jpg"
        cv2.imwrite(str(temp_image_path), player_crop)
        
        try:
            # Run YOLOv7 inference
            predictions = self._run_yolo_inference()
            
            # Parse results
            number, confidence = self._parse_predictions(predictions)
            
            return number, confidence
            
        except Exception as e:
            print(f"YOLOv7 inference failed: {e}")
            return -1, 0.0
        finally:
            # Clean up temp image
            if temp_image_path.exists():
                temp_image_path.unlink()
    
    def _run_yolo_inference(self):
        """Run YOLOv7 test.py on the temporary image"""
        # Prepare command similar to pipeline_step.py
        python_exe = sys.executable
        test_cmd = [
            str(python_exe), "test.py",
            "--weights", str(self.model_path),
            "--data", str(self.data_yaml_path),
            "--task", "test",
            "--save-txt", "--save-conf",
            "--project", str(self.temp_dir / "runs" / "test"),
            "--name", "inference",
            "--device", self.device,
            "--conf-thres", str(self.confidence_threshold),
            "--exist-ok"  # Overwrite existing results
        ]
        
        # Run inference in YOLOv7 directory
        result = subprocess.run(
            test_cmd, 
            cwd=self.yolov7_dir, 
            capture_output=True, 
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        if result.returncode != 0:
            print(f"YOLOv7 test.py failed: {result.stderr}")
            return []
        
        # Read prediction results
        predictions_dir = self.temp_dir / "runs" / "test" / "inference" / "labels"
        
        if not predictions_dir.exists():
            return []
        
        # Read predictions from txt file
        label_file = predictions_dir / "temp_crop.txt"
        if not label_file.exists():
            return []
        
        predictions = []
        with open(label_file, 'r') as f:
            for line in f.readlines():
                parts = line.strip().split()
                if len(parts) == 6:  # class_id, x, y, w, h, confidence
                    class_id = int(parts[0])
                    confidence = float(parts[5])
                    predictions.append((class_id, confidence))
        
        return predictions
    
    def _parse_predictions(self, predictions):
        """Parse YOLOv7 predictions to extract number and confidence"""
        if not predictions:
            return -1, 0.0
        
        # Filter predictions by confidence threshold
        valid_predictions = [(cls, conf) for cls, conf in predictions if conf >= self.confidence_threshold]
        
        if not valid_predictions:
            return -1, 0.0
        
        # Sort by confidence and take the best prediction
        valid_predictions.sort(key=lambda x: x[1], reverse=True)
        best_class, best_confidence = valid_predictions[0]

        # map the best_class to number using class_names in data.yaml
        if best_class < len(self.class_names):
            detected_number = self.class_names[best_class]
            return detected_number, best_confidence
        else:
            return -1, 0.0
        
    
    def __del__(self):
        """Cleanup temporary directory"""
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception:
            pass  # Ignore cleanup errors


def test_yolo_recognizer():
    """Test function for YOLORecognizer"""
    try:
        recognizer = YOLORecognizer()
        
        # Test with a dummy image
        test_image = cv2.imread("/Users/bingqingyu/Downloads/images.jpeg")  # Replace with actual test image
        # test_image = cv2.imread("/Users/bingqingyu/Projects/2025_pff/data/JerseyDetection-7_mini/train_mini/images/-11-_jpg.rf.f958d784a9df6dfcc5f11b368dfaee74.jpg")  # Replace with actual test image
        test_image = cv2.imread("/Users/bingqingyu/Projects/2025_pff/data/JerseyDetection-7_mini/valid_mini/images/-10-_jpg.rf.16b643667f8162d26e73553943bec5e7.jpg")  # Replace with actual test image
        if test_image is not None:
            number, confidence = recognizer.recognize(test_image)
            print(f"Detected number: {number}, confidence: {confidence:.3f}")
        else:
            print("Test image not found - create test_player_crop.jpg for testing")
            
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    test_yolo_recognizer()