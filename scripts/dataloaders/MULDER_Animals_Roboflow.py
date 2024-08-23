import os
from PIL import Image
from clarifai.client.app import App
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualDetectionFeatures
from pycocotools.coco import COCO


# Dataloader for Roboflow dataset : https://universe.roboflow.com/machine-train-ur3hn/animals-detection-bsbbi

class CustomCOCODetectionDataLoader(ClarifaiDataLoader):
    def __init__(self, images_dir, label_filepath):
        """
        Args:
            images_dir: Directory containing the images.
            label_filepath: Path to the COCO annotation file.
        """
        self.images_dir = images_dir
        self.label_filepath = label_filepath
        self.map_ids = {}
        self.load_data()

    @property
    def task(self):
        return "visual_detection"

    def load_data(self) -> None:
        self.coco = COCO(self.label_filepath)
        self.map_ids = {i: img_id for i, img_id in enumerate(list(self.coco.imgs.keys()))}

    def __getitem__(self, index: int):
        value = self.coco.imgs[self.map_ids[index]]
        image_path = os.path.join(self.images_dir, value['file_name'])
        annots = []  # Bounding boxes
        concept_ids = []

        input_ann_ids = self.coco.getAnnIds(imgIds=[value['id']])
        input_anns = self.coco.loadAnns(input_ann_ids)

        for ann in input_anns:
            concept_name = self.coco.cats[ann['category_id']]['name']
            concept_id = concept_name.lower().replace(' ', '-')

            coco_bbox = ann['bbox']
            clarifai_bbox = {
                'left_col': max(0, coco_bbox[0] / value['width']),
                'top_row': max(0, coco_bbox[1] / value['height']),
                'right_col': min(1, (coco_bbox[0] + coco_bbox[2]) / value['width']),
                'bottom_row': min(1, (coco_bbox[1] + coco_bbox[3]) / value['height'])
            }

            if (clarifai_bbox['left_col'] >= clarifai_bbox['right_col']) or \
               (clarifai_bbox['top_row'] >= clarifai_bbox['bottom_row']):
                continue

            annots.append([
                clarifai_bbox['left_col'], clarifai_bbox['top_row'], 
                clarifai_bbox['right_col'], clarifai_bbox['bottom_row']
            ])
            concept_ids.append(concept_id)

        assert len(concept_ids) == len(annots), (
            f"Num concepts must match num bbox annotations for a single image. "
            f"Found {len(concept_ids)} concepts and {len(annots)} bboxes."
        )

        return VisualDetectionFeatures(image_path, concept_ids, annots, id=str(value['id']))

    def __len__(self):
        return len(self.coco.imgs)

# Initialize the Clarifai App
app = App(app_id="Animal_Detection", user_id="mulder", pat="PAT HERE")

# Define the path to the dataset directory
current_working_dir = os.getcwd()
archive_folder = os.path.join(current_working_dir, 'animal_dataset')
print(f"Archive folder: {archive_folder}")

# Iterate through each folder in the dataset directory
for folder in os.listdir(archive_folder):
    folder_path = os.path.join(archive_folder, folder)
    if not os.path.isdir(folder_path):
        continue
    
    print(f"Processing folder: {folder_path}")
    
    label_filepath = os.path.join(folder_path, "_annotations.coco.json")
    dataloader = CustomCOCODetectionDataLoader(folder_path, label_filepath)
    
    if len(dataloader) == 0:
        print(f"No data found in {folder_path}. Skipping...")
        continue

    try:
        dataset = app.create_dataset(dataset_id=folder)
        print(f"Created new dataset: {folder}")
    except Exception as e:
        print(f"Error creating dataset: {e}")
        datasets = app.list_datasets()
        dataset = next((d for d in datasets if d.id == folder), None)
        if dataset:
            print(f"Dataset {folder} already exists")

    # Upload the dataset and create a version
    dataset.upload_dataset(dataloader=dataloader, batch_size=20, get_upload_status=True, log_warnings=True)
    dataset.create_version()
    print(f"Dataset and version created for {folder}")
