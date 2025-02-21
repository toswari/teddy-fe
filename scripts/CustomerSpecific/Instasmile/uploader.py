import os
import json
from clarifai.client.app import App
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualDetectionFeatures

def id_hex_generator():
    return os.urandom(12).hex()

class COCOToClarifaiDataLoader(ClarifaiDataLoader):
    def __init__(self, images_dir, coco_json_path):
        self.images_dir = os.path.abspath(images_dir)
        self.coco_json_path = coco_json_path
        self.annotations = {}
        self.categories = {}
        self.load_data()

    def _find_image_file(self, file_name):
        # Normalize the file_name to use correct directory structure
        file_parts = file_name.replace('\\', '/').split('/')
        
        # Try different path combinations
        possible_paths = [
            # Path with Impression Check folder (this should be first as it's the correct structure)
            os.path.join(self.images_dir, "Impression Check", file_name),
            # Original path
            os.path.join(self.images_dir, file_name),
            # Just filename in root
            os.path.join(self.images_dir, os.path.basename(file_name)),
        ]
        
        # Print debugging info for first file
        if not hasattr(self, '_debug_printed'):
            print("\n=== Path Debug Info ===")
            print(f"Base directory: {self.images_dir}")
            print(f"Looking for file: {file_name}")
            print("Trying paths:")
            for path in possible_paths:
                print(f"  {path}")
                print(f"    Exists: {os.path.exists(path)}")
                parent = os.path.dirname(path)
                print(f"    Parent dir exists: {os.path.exists(parent)}")
                if os.path.exists(parent):
                    print(f"    Parent contents: {os.listdir(parent)[:5]}")
            self._debug_printed = True
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        return None

    @property
    def task(self):
        return "visual_detection"
    def load_data(self):
        with open(self.coco_json_path, 'r') as f:
            data = json.load(f)
        
        print("\n=== Loading Data ===")
        print(f"Images directory: {self.images_dir}")
        print(f"COCO JSON path: {self.coco_json_path}")
        print(f"Number of images in JSON: {len(data.get('images', []))}")
        print(f"Number of annotations in JSON: {len(data.get('annotations', []))}")
        
        self.categories = {
            category['id']: ''.join(e for e in category['name'] if e.isalnum()).lower() 
            for category in data.get('categories', [])
        }
        
        # Create images dictionary with normalized paths
        images = {}
        for img in data['images']:
            file_path = self._find_image_file(img['file_name'])
            if not file_path:
                print(f"\nImage not found:")
                print(f"  ID: {img['id']}")
                print(f"  Original filename: {img['file_name']}")
                continue
            
            images[img['id']] = {
                'file_path': file_path,
                'width': img['width'],
                'height': img['height']
            }
        
        print(f"\n=== Image Loading Summary ===")
        print(f"Total images in JSON: {len(data['images'])}")
        print(f"Successfully loaded images: {len(images)}")
        
        # Print first few image IDs from annotations
        print("\n=== First few annotation image IDs ===")
        for ann in data.get('annotations', [])[:5]:
            print(f"Annotation references image ID: {ann.get('image_id')}")

        for ann in data.get('annotations', []):
            image_id = ann['image_id']
            if image_id not in images:
                #print(f"Warning: image_id {image_id} not found in images. Skipping annotation.")
                continue
            
            bbox = ann.get('bbox', [0, 0, 0, 0])  # Get bbox with default value
            category_id = ann.get('category_id')  # Add this line
            
            image_width = images[image_id]['width']
            image_height = images[image_id]['height']
            left = max(0.0, min(1.0, bbox[0] / image_width))
            top = max(0.0, min(1.0, bbox[1] / image_height))
            right = max(0.0, min(1.0, (bbox[0] + bbox[2]) / image_width))
            bottom = max(0.0, min(1.0, (bbox[1] + bbox[3]) / image_height))
            attributes = []
            if 'attributes' in ann:
                for attr_key, attr_val in ann['attributes'].items():
                    if attr_val:
                        attributes.append({attr_key: attr_val})
            if category_id == 1 or category_id == 3:  
                reason = ann.get('attributes', {}).get('reason', 'Unknown')
                #print(f"Reason: {reason}")  
                attributes.append({'reason': reason})
            concept_id = self.categories.get(category_id, "Unknown")
            if image_id not in self.annotations:
                self.annotations[image_id] = {
                    'image_path': images[image_id]['file_path'],
                    'concept_ids': [],
                    'bboxes': [],
                    'id': id_hex_generator(),
                    'metadata': {}
                }
            self.annotations[image_id]['metadata'] = {
                "attributes": attributes
            }
            self.annotations[image_id]['concept_ids'].append(concept_id)
            self.annotations[image_id]['bboxes'].append([left, top, right, bottom])

    def __getitem__(self, index: int):
        image_data = list(self.annotations.values())[index]
        return VisualDetectionFeatures(
            image_path=image_data['image_path'],
            labels=image_data['concept_ids'],
            bboxes=image_data['bboxes'],
            id=image_data['id'],
            metadata=image_data['metadata'] 
        )

    def __len__(self):
        return len(self.annotations)

def process_coco_datasets(img_dir, coco_json_path, config):
    # Print directory structure before processing
    print("\n=== Directory Structure ===")
    for root, dirs, files in os.walk(img_dir):
        level = root.replace(img_dir, '').count(os.sep)
        indent = '  ' * level
        print(f"{indent}Directory: {os.path.basename(root)}/")
        if level < 2:  # Only show files for first two levels
            for f in files[:3]:  # Show first 3 files
                print(f"{indent}  File: {f}")
    
    print("\n=== JSON Contents ===")
    with open(coco_json_path, 'r') as f:
        data = json.load(f)
    print("First few image paths in JSON:")
    for img in data['images'][:5]:
        print(f"  {img['file_name']}")
    
    # Convert paths to absolute paths
    img_dir = os.path.abspath(img_dir)
    coco_json_path = os.path.abspath(coco_json_path)
    
    print(f"\nLoading dataset from:\nImages: {img_dir}\nAnnotations: {coco_json_path}")
    
    dataloader = COCOToClarifaiDataLoader(img_dir, coco_json_path)
    print(f"Total images: {len(dataloader)}")
    user_id = config['user_id']
    pat = config['pat']
    app_id = config['app_id']

    # Create a mapping of category_id to images
    category_images = {}
    for idx in range(len(dataloader)):
        item = dataloader[idx]
        for label in item.labels:
            if label not in category_images:
                category_images[label] = []
            category_images[label].append(idx)

    # Upload images for each category separately
    for category_name, image_indices in category_images.items():
        dataset_id = f"{category_name}_v3"
        print(f"Uploading dataset {dataset_id} with {len(image_indices)} images...")
        
        # Create a filtered dataloader for this category
        filtered_dataloader = FilteredDataLoader(dataloader, image_indices)
        
        app = App(user_id=user_id, pat=pat, app_id=app_id)
        try:
            dataset = app.create_dataset(dataset_id=dataset_id)
        except Exception:
            dataset = app.dataset(dataset_id=dataset_id)
        
        dataset.upload_dataset(
            dataloader=filtered_dataloader, 
            batch_size=10, 
            get_upload_status=True, 
            log_warnings=False
        )

class FilteredDataLoader:
    def __init__(self, original_dataloader, indices):
        self.original_dataloader = original_dataloader
        self.indices = indices

    def __getitem__(self, idx):
        return self.original_dataloader[self.indices[idx]]

    def __len__(self):
        return len(self.indices)

    @property
    def task(self):
        return self.original_dataloader.task

if __name__ == '__main__':
    config = {
        'user_id': 'insta-smile-uk',
        'pat': '<pat>',
        'dataset_id': 'test', 
        'app_id': 'InstaSmile-DentalTray'
    }
    # Use the parent directory that contains "Impression Check"
    base_dir = r'E:\InstaSmile\New_Images\Impression Check-20250131T183407Z-001'
    process_coco_datasets(base_dir, './impression_check_annotations.json', config)
