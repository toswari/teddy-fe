from typing import Iterator, List
import logging
import requests

# Clarifai imports
from clarifai.runners.utils.data_utils import Video, Image, Audio, Param
from clarifai.runners.utils.data_types import Text
from clarifai.runners.models.model_class import ModelClass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MyModelClass(ModelClass):

    def load_model(self):
        logger.info("Any-to-any model loaded successfully")

    @ModelClass.method
    def predict(
        self, 
        video: Video = None,
        image: Image = None,
        text: str = None,
        audio: str = None,
        output_type: str = Param(default="image", description="Output type: 'video', 'image', 'text', 'audio'"),
        operation: str = Param(default="process", description="Operation to perform: 'process', 'describe', 'analyze'")
    ) -> Image:
        try:
            input_type = None
            input_content = None
            
            if video is not None:
                input_type = "video"
                input_content = video
            elif image is not None:
                input_type = "image"  
                input_content = image
            elif text is not None:
                input_type = "text"
                input_content = text
            elif audio is not None:
                input_type = "audio"
                input_content = audio
            else:
                raise ValueError("At least one input (video, image, text, or audio) is required")
            
            logger.info(f"Processing {input_type} input with operation: {operation}, returning {output_type}")
            
            if input_type == "image":
                if hasattr(input_content, 'url') and input_content.url:
                    image_bytes = self._download_from_url(input_content.url)
                    return Image(bytes=image_bytes)
                elif hasattr(input_content, 'bytes') and input_content.bytes:
                    return Image(bytes=input_content.bytes)
                else:
                    sample_image_bytes = self._download_from_url("https://samples.clarifai.com/metro-north.jpg")
                    return Image(bytes=sample_image_bytes)
            
            elif input_type == "video":
                sample_image_bytes = self._download_from_url("https://samples.clarifai.com/metro-north.jpg")
                return Image(bytes=sample_image_bytes)
            
            elif input_type == "text":
                sample_image_bytes = self._download_from_url("https://samples.clarifai.com/metro-north.jpg")
                return Image(bytes=sample_image_bytes)
                
            elif input_type == "audio":
                sample_image_bytes = self._download_from_url("https://samples.clarifai.com/metro-north.jpg")
                return Image(bytes=sample_image_bytes)
                
        except Exception as e:
            logger.error(f"Error in predict: {e}")
            raise e

    def _download_from_url(self, url):
        try:
            logger.info(f"Downloading from URL: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to download from URL {url}: {e}")
            raise e

    @ModelClass.method
    def batch_predict(
        self,
        videos: List[Video] = None,
        images: List[Image] = None,
        texts: List[str] = None,
        audios: List[str] = None,
        output_type: str = Param(default="image", description="Output type: 'video', 'image', 'text', 'audio'"),
        operation: str = Param(default="process", description="Operation to perform: 'process', 'describe', 'analyze'")
    ) -> List[Image]:

        # Determine input source and type
        inputs = []
        
        if videos is not None:
            inputs = [(video, "video") for video in videos]
        elif images is not None:
            inputs = [(image, "image") for image in images]
        elif texts is not None:
            inputs = [(text, "text") for text in texts]
        elif audios is not None:
            inputs = [(audio, "audio") for audio in audios]
        else:
            raise ValueError("At least one input list is required")
            
        if not inputs:
            return []
        
        results = []
        for i, (input_item, item_type) in enumerate(inputs):
            try:
                predict_params = {"output_type": output_type, "operation": operation}
                
                if item_type == "video":
                    predict_params["video"] = input_item
                elif item_type == "image":
                    predict_params["image"] = input_item
                elif item_type == "text":
                    predict_params["text"] = input_item
                elif item_type == "audio":
                    predict_params["audio"] = input_item
                
                result = self.predict(**predict_params)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in batch_predict item {i}: {e}")
                # Return placeholder image for failed items
                sample_image_bytes = self._download_from_url("https://samples.clarifai.com/metro-north.jpg")
                results.append(Image(bytes=sample_image_bytes))
        
        return results

    @ModelClass.method
    def generate(
        self,
        video: Video = None,
        image: Image = None,
        text: str = None,
        audio: str = None,
        output_type: str = Param(default="image", description="Output type: 'video', 'image', 'text', 'audio'"),
        operation: str = Param(default="process", description="Operation to perform"),
        steps: int = Param(default=3, description="Number of processing steps to yield")
    ) -> Iterator[str]:

        try:
            # Determine input type
            input_type = "unknown"
            if video is not None:
                input_type = "video"
            elif image is not None:
                input_type = "image"
            elif text is not None:
                input_type = "text"
            elif audio is not None:
                input_type = "audio"
            else:
                yield "Error: At least one input required"
                return
            
            # Step 1: Validate input
            yield f"Step 1/{steps}: Validating {input_type} input"
            
            # Step 2: Processing
            if steps > 1:
                yield f"Step 2/{steps}: Processing {input_type} with operation: {operation}"
            
            # Step 3: Final result
            if steps > 2:
                yield f"Step {steps-1}/{steps}: Preparing {output_type} output"
            
            # Final result
            yield f"Step {steps}/{steps}: Processing complete"
                
        except Exception as e:
            logger.error(f"Error in generate: {e}")
            yield f"Error in generate: {str(e)}"

    @ModelClass.method  
    def stream(
        self,
        input_iterator: Iterator[dict],
        batch_size: int = Param(default=1, description="Batch size for processing inputs")
    ) -> Iterator[str]:

        try:
            all_inputs = list(input_iterator)
            
            if not all_inputs:
                yield "Error: No inputs provided"
                return
            
            logger.info(f"Processing {len(all_inputs)} inputs in stream mode")
            
            for i in range(0, len(all_inputs), batch_size):
                batch = all_inputs[i:i + batch_size]
                
                for j, input_data in enumerate(batch):
                    try:
                        if not isinstance(input_data, dict):
                            yield f"Error at index {i + j}: Input must be a dict"
                            continue
                        
                        yield f"Processing input {i + j + 1}/{len(all_inputs)}"
                            
                    except Exception as e:
                        yield f"Error at index {i + j}: {str(e)}"
                        
        except Exception as e:
            logger.error(f"Error in stream: {e}")
            yield f"Error in stream: {str(e)}"