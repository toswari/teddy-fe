import os
import json
from clarifai.client.app import App
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualDetectionFeatures
from dotenv import load_dotenv


load_dotenv()
#read the environment variables
env_vars = os.environ
epat = env_vars["PAT"]
euid = env_vars["UID"]


def id_hex_generator():
    return os.urandom(12).hex()

class COCOToClarifaiDataLoader(ClarifaiDataLoader):
    def __init__(self, images_dir, coco_json_path):
        self.images_dir = images_dir
        self.coco_json_path = coco_json_path
        self.annotations = {}
        self.categories = {}
        self.load_data()
    @property
    def task(self):
        return "visual_detection"
    def load_data(self):
        with open(self.coco_json_path, 'r') as f:
            data = json.load(f)
        self.categories = {
            category['id']: ''.join(e for e in category['name'] if e.isalnum()).lower() 
            for category in data.get('categories', [])
        }

        images = {
            img['id']: {
                'file_path': os.path.join(self.images_dir, img['file_name']),
                'width': img['width'],
                'height': img['height']
            } for img in data['images']
        }
        for ann in data.get('annotations', []):
            image_id = ann['image_id']
            category_id = ann['category_id']
            bbox = ann.get('bbox', [])
            if image_id not in images:
                print(f"Warning: image_id {image_id} not found in images. Skipping annotation.")
                continue 
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
    dataloader = COCOToClarifaiDataLoader(img_dir, coco_json_path)
    user_id = config['user_id']
    pat = config['pat']
    app_id = config['app_id']
    for category_id, category_name in dataloader.categories.items():
        category_name = ''.join(e for e in category_name if e.isalnum())
        category_name = category_name.lower()
        dataset_id = f"{category_name}"
        print(f"Uploading dataset {dataset_id}...")
        app = App(user_id=user_id, pat=pat, app_id=app_id)
        try:
            dataset = app.create_dataset(dataset_id=dataset_id)
        except Exception:
            dataset = app.dataset(dataset_id=dataset_id)
        dataset.upload_dataset(dataloader=dataloader, batch_size=10, get_upload_status=True, log_warnings=False)

if __name__ == '__main__':
    config = {
        'user_id': euid,
        'pat': epat,
        'dataset_id': 'test', 
        'app_id': 'instasmile_5'
    }
    process_coco_datasets('./Impression Check', './impression_check_annotations.json', config)
