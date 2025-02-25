import os
from clarifai.client.app import App
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualDetectionFeatures

def id_hex_generator():
    return os.urandom(8).hex()

UPLOADED_LOG = "uploaded_images.txt"
FAILED_LOG = "failed_images.txt"

def load_logged_images(log_file):
    """Load image file names from the given log file."""
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return set(f.read().splitlines())
    return set()

def log_image(log_file, image_path):
    """Append an image file name to the log file."""
    with open(log_file, "a") as f:
        f.write(f"{image_path}\n")

class ImageDirectoryLoader(ClarifaiDataLoader):
    def __init__(self, images_dir, uploaded_images, failed_images):
        self.images_dir = images_dir
        self.uploaded_images = uploaded_images
        self.failed_images = failed_images
        self.images = []
        self.load_data()

    @property
    def task(self):
        return "visual_detection"  # Using visual detection but without annotations

    def load_data(self):
        """Load image file paths while skipping already processed ones."""
        for filename in os.listdir(self.images_dir):
            file_path = os.path.join(self.images_dir, filename)
            if file_path in self.uploaded_images or file_path in self.failed_images:
                continue  # Skip already processed images
            if os.path.isfile(file_path) and filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".gif")):
                self.images.append(file_path)

    def __getitem__(self, index: int):
        """Return an image with empty labels and bounding boxes for visual detection."""
        return VisualDetectionFeatures(
            image_path=self.images[index],
            labels=[],  # No labels
            bboxes=[],  # No bounding boxes
            id=id_hex_generator(),  # Unique ID per image
            metadata={}  # No metadata
        )

    def __len__(self):
        return len(self.images)

def process_image_directory(img_dir, config):
    uploaded_images = load_logged_images(UPLOADED_LOG)
    failed_images = load_logged_images(FAILED_LOG)

    dataloader = ImageDirectoryLoader(img_dir, uploaded_images, failed_images)

    if len(dataloader) == 0:
        print("No new images to upload.")
        return

    user_id = config["user_id"]
    pat = config["pat"]
    dataset_id = config["dataset_id"]
    app_id = config["app_id"]

    app = App(user_id=user_id, pat=pat, app_id=app_id)

    try:
        dataset = app.create_dataset(dataset_id=dataset_id)
    except Exception:
        dataset = app.dataset(dataset_id=dataset_id)

    try:
        dataset.upload_dataset(dataloader=dataloader, batch_size=20)  # Upload in batches
        for image_path in dataloader.images:
            log_image(UPLOADED_LOG, image_path)  # Log successful upload
    except Exception as e:
        print(f"Batch upload failed: {e}")
        for image_path in dataloader.images:
            log_image(FAILED_LOG, image_path)  # Log failed images



if __name__ == "__main__":
    config = {
        "user_id": "jasonhookey",
        "pat": "pat",
        "dataset_id": "sharepoint_rebuild",
        "app_id": "thermostat-detect",
    }
    process_image_directory("./SFDownload", config)
