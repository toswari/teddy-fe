from clarifai.client.app import App
import os
from PIL import Image
import hashlib
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualClassificationFeatures

def hashid():
    return hashlib.sha1(os.urandom(20)).hexdigest()[:10]

class CustomImageDataLoader(ClarifaiDataLoader):
    def __init__(self, images_dir, concept_id=None):
        """
        Args:
            images_dir: Directory containing the images.
        """
        self.images_dir = images_dir
        self.images = [f for f in os.listdir(self.images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'))]
        self.concept_id = concept_id

    @property
    def task(self):
        return "visual_classification"

    def __getitem__(self, index: int):
        image_filename = self.images[index]
        image_path = os.path.join(self.images_dir, image_filename)
        metadata = {
            "Filename": image_filename,
            "Classification": self.concept_id
        }
        labels = [self.concept_id]
        return VisualClassificationFeatures(image_path, labels, metadata=metadata, id=hashid(), label_ids=labels)
    def __len__(self):
        return len(self.images)


app = App(app_id="APP ID", user_id="USER ID", pat="PAT HERE")
input_folder = os.path.join(os.getcwd(), "apple-final-uploads")
print(f"Input folder: {input_folder}")
taxonomy_dict = {
    "applewatch-series9": "apple-watch",
    "iMac_24_inch": "imac",
    "Mac_mini": "mac-mini",
    "Mac_Pro": "mac-pro",
    "Mac_Studio": "mac-studio",
    "MacBook_Air_13_inch": "macbook",
    "MacBook_Air_15_inch": "macbook",
    "MacBook_Pro_14_inch": "macbook",
    "MacBook_Pro_16_inch": "macbook",
    "ProXDR_Display": "pro-XDR-display",
    "Studio_Display": "studio-display"
}
subfolders = [f.name for f in os.scandir(input_folder) if f.is_dir()]
print(f"Subfolders found: {subfolders}")
for subfolder in subfolders:
    subfolder_rootname = subfolder
    if subfolder_rootname in taxonomy_dict:
        concept_id = taxonomy_dict[subfolder_rootname]
    else:
        break
    subfolder_path = os.path.join(input_folder, subfolder)
    subsubfolders = [f.name for f in os.scandir(subfolder_path) if f.is_dir()]
    for subsubfolder in subsubfolders:
        subsubfolder_path = os.path.join(subfolder_path, subsubfolder)
        dataset_id = f"{concept_id}"
        for root, dirs, files in os.walk(subsubfolder_path):
            for dirname in dirs:
                images_dir = os.path.join(root, dirname)
                image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'))]
                if not image_files:
                    print(f"No images found in {images_dir}. Skipping this directory.")
                    continue
                dname = f"{subfolder}_{subsubfolder[:5]}_{dirname[:5]}".rstrip('_')
                dataloader = None
                dataloader = CustomImageDataLoader(images_dir, concept_id=concept_id)
                if len(dataloader) == 0:
                    continue
                try:
                    dataset = app.create_dataset(dataset_id=dataset_id)
                except Exception as e:
                    datasets = app.list_datasets()
                    dataset = next((d for d in datasets if d.id == dataset_id), None)
                    if dataset:
                        print("Dataset already exists")
                    else:
                        continue
                dataset.upload_dataset(dataloader=dataloader, batch_size=10)
                dataset.create_version()
                print(f"Dataset {dataset_id} created and versioned")
                del dataloader
