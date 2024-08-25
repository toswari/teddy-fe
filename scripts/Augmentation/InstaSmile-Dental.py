import os
from PIL import Image
import numpy as np
import random
import hashlib
import traceback
from sklearn.model_selection import train_test_split
from clarifai.client.app import App
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualClassificationFeatures
import concurrent.futures
import os
from PIL import Image
import numpy as np
import random
import hashlib
import traceback
import imgaug.augmenters as iaa
import imgaug.augmenters.arithmetic as arithmetic
import imgaug.augmenters.artistic as artistic
import imgaug.augmenters.blur as blur
import imgaug.augmenters.color as color
import imgaug.augmenters.convolutional as convolutional
import imgaug.augmenters.pooling as pooling
import imgaug.augmenters.imgcorruptlike as imgcorruptlike
import imgaug.augmenters.contrast as iaa_contrast
import imgaug.augmenters.pillike as pillike
from clarifai.client.app import App
from clarifai.datasets.upload.base import ClarifaiDataLoader
from clarifai.datasets.upload.features import VisualClassificationFeatures
import concurrent.futures

def hashid():
    return str(random.getrandbits(64))

def resize_image(image, max_size=800):
    """Resize image so that its longest side is under max_size pixels while maintaining aspect ratio."""
    width, height = image.size
    if width > height:
        new_width = max_size
        new_height = int((max_size / width) * height)
    else:
        new_height = max_size
        new_width = int((max_size / height) * width)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

def augment_image(image):
    augmentations = []
    augmenters = [
        (iaa.GaussianBlur(sigma=random.uniform(0.1, 0.9)), 'blur'),
        #(iaa.Multiply(random.uniform(0.98, 1.2)), 'multiply'),
        (iaa.AddToBrightness(random.uniform(-3, 3)), 'brightness'),
        (iaa.LinearContrast(alpha=random.uniform(0.95, 1.05)), 'contrast'),
        (iaa.AddToHueAndSaturation(int(random.uniform(-3, 3))), 'hue_saturation'),
        (iaa.ElasticTransformation(alpha=random.uniform(0.5, 1.0), sigma=random.uniform(0.25, 0.5)), 'elastic'),
        #(iaa.MotionBlur(k=random.randint(3, 4), angle=random.uniform(-1, 1)), 'motion_blur'),
        (blur.AverageBlur(k=random.randint(3, 4)), 'average_blur'),
        #(imgcorruptlike.GaussianNoise(severity=random.randint(1,2)), 'imgcorruptlike_gaussian_noise'),
        (color.AddToHueAndSaturation(int(random.uniform(-5, 5))), 'add_to_hue_and_saturation'),
        (convolutional.Sharpen(alpha=random.uniform(0.5, 0.55), lightness=random.uniform(0.95, 1.05)), 'sharpen'),
        (pillike.EnhanceSharpness(factor=random.uniform(0.5, 0.8)), 'pillike_sharpness'),
        (pooling.AveragePooling(kernel_size=random.randint(2, 2)), 'average_pooling'),
    ]
    random.shuffle(augmenters)
    for aug, _ in augmenters:
        image = aug.augment_image(image)
        augmentations.append(_)
    rotval = random.randint(0, 3)
    if rotval > 0:
        desc = f"rotated_{rotval * 90}_degrees"
        image = np.rot90(image, rotval)
        augmentations.append(desc)
    return image, augmentations

def process_image(image_file, input_folder, output_folder, concept_id, num_augmentations):
    image_path = os.path.join(input_folder, image_file)
    augmented_images = []
    try:
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                img = img.convert("RGB")
            img = resize_image(img)
            image = np.array(img)
            original_image_filename = f"{os.path.splitext(image_file)[0]}_orig.png"
            img.save(os.path.join(output_folder, original_image_filename))
            for i in range(num_augmentations):
                try:
                    augmented_image, augmentations = augment_image(image.copy())
                    augmented_image_pil = Image.fromarray(augmented_image)
                    hash = hashid()
                    augmented_image_filename = f"{os.path.splitext(image_file)[0]}_aug_{i}_{hash}.png"
                    augmented_image_pil.save(os.path.join(output_folder, augmented_image_filename))
                    augmented_images.append((os.path.join(output_folder, augmented_image_filename), concept_id, augmentations))
                except Exception as e:
                    print(f"Error augmenting image {image_file}: {e}")
                    print(traceback.format_exc())
            print(f"Augmented {image_file} {num_augmentations} times")
    except Exception as e:
        print(f"Error processing image {image_file}: {e}")
        print(traceback.format_exc())
    return augmented_images

def augment_images_in_folder(input_folder, output_folder, num_augmentations):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    image_files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'))]
    print(f"Found {len(image_files)} images in {input_folder}")
    if not image_files:
        print("No images found. Exiting.")
        return []
    concept_id = os.path.basename(input_folder)
    augmented_images = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_image, img_file, input_folder, output_folder, concept_id, num_augmentations) for img_file in image_files]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result:
                    augmented_images.extend(result)
            except Exception as e:
                print(f"Error processing image: {e}")
                print(traceback.format_exc())
    return augmented_images

def create_and_upload_dataset(app, dataset_id, images_with_concepts):
    dataloader = CustomImageDataLoader(images_with_concepts)
    try:
        dataset = app.create_dataset(dataset_id=dataset_id)
    except Exception as e:
        datasets = app.list_datasets()
        dataset = next((d for d in datasets if d.id == dataset_id), None)
        if dataset:
            print(f"Dataset '{dataset_id}' already exists.")
        else:
            print(f"Failed to create or find dataset '{dataset_id}': {e}")
            return
    dataset.upload_dataset(dataloader=dataloader, batch_size=3)
    dataset.create_version()
    print(f"Dataset '{dataset_id}' created and versioned.")

class CustomImageDataLoader(ClarifaiDataLoader):
    def __init__(self, images_with_concepts):
        self.images_with_concepts = images_with_concepts
    @property
    def task(self):
        return "visual_classification"

    def __getitem__(self, index: int):
        image_path, concept_id, augmentations = self.images_with_concepts[index]
        metadata = {
            "Filename": os.path.basename(image_path),
            "Classification": concept_id,
            "AugmentationApplied": augmentations,
        }
        labels = [concept_id]
        return VisualClassificationFeatures(image_path, labels, metadata=metadata, id=hashid(), label_ids=labels)

    def __len__(self):
        return len(self.images_with_concepts)

app = App(app_id="APP HERE", user_id="USER HERE", pat="PAT HERE")
input_folder = os.path.join(os.getcwd(), "images")
output_folder = os.path.join(os.getcwd(), "augmented-images")
print(f"Input folder: {input_folder}")
print(f"Output folder: {output_folder}")
all_images = []
for folder in ["passes", "fails"]:
    folder_path = os.path.join(input_folder, folder)
    augmented_folder_path = os.path.join(output_folder, folder)
    if not os.path.isdir(folder_path):
        print(f"Folder {folder} not found. Skipping.")
        continue
    augmented_images = augment_images_in_folder(folder_path, augmented_folder_path, num_augmentations=160)
    all_images.extend(augmented_images)
print(f"Found {len(all_images)} augmented images.")
train_images, val_images = train_test_split(all_images, test_size=0.2, random_state=42)
train_dir = os.path.join(output_folder, "train")
val_dir = os.path.join(output_folder, "validation")
os.makedirs(train_dir, exist_ok=True)
os.makedirs(val_dir, exist_ok=True)
train_images_with_concepts = []
val_images_with_concepts = []
for image_path, concept_id, augmentations in train_images:
    try:
        new_path = os.path.join(train_dir, os.path.basename(image_path))
        os.rename(image_path, new_path)
    except Exception as e:
        suffix = random.randint(1, 1000)
        new_path = os.path.join(train_dir, f"{os.path.basename(image_path)}_{suffix}")
        os.rename(image_path, new_path)
    train_images_with_concepts.append((new_path, concept_id, augmentations))
for image_path, concept_id, augmentations in val_images:
    try:
        new_path = os.path.join(val_dir, os.path.basename(image_path))
        os.rename(image_path, new_path)
    except Exception as e:
        suffix = random.randint(1, 1000)
        new_path = os.path.join(val_dir, f"{os.path.basename(image_path)}_{suffix}")
        os.rename(image_path, new_path)
    val_images_with_concepts.append((new_path, concept_id, augmentations))

create_and_upload_dataset(app, "train", train_images_with_concepts)
create_and_upload_dataset(app, "validation", val_images_with_concepts)

print("Datasets created and uploaded.")
