import os
import json
import tempfile
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import ffmpeg
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import aiofiles

from clarifai.utils.logging import logger
from pydantic import Field, BaseModel

class VideoProcessingInput(BaseModel):
    video_url: str = Field(description="URL of the video to process")
    s3_bucket: str = Field(description="S3 bucket name for uploading results")
    aws_access_key_id: str = Field(description="AWS access key ID")
    aws_secret_access_key: str = Field(description="AWS secret access key")
    aws_region: str = Field(description="AWS region", default="us-east-1")
    output_prefix: str = Field(description="S3 prefix for output files", default="processed_videos/")

class VideoMetadata(BaseModel):
    filename: str
    duration: float
    width: int
    height: int
    fps: float
    bitrate: int
    format: str
    codec: str
    audio_codec: str
    audio_bitrate: int
    audio_sample_rate: int
    audio_channels: int
    file_size: int
    creation_time: Optional[str] = None
    processed_at: str
    streams: list

async def download_video(url: str, temp_dir: str) -> str:
    """Download video from URL to temporary directory"""
    try:
        import httpx
        filename = url.split('/')[-1]
        if not filename or '.' not in filename:
            filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        
        local_path = os.path.join(temp_dir, filename)
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            logger.info(f"Downloading video from {url}")
            response = await client.get(url)
            response.raise_for_status()
            
            async with aiofiles.open(local_path, 'wb') as f:
                await f.write(response.content)
        
        logger.info(f"Video downloaded to {local_path}")
        return local_path
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise

def extract_video_metadata(video_path: str) -> VideoMetadata:
    """Extract comprehensive metadata from video using ffmpeg"""
    try:
        # Get video info using ffmpeg probe
        probe = ffmpeg.probe(video_path)
        
        # Get video stream
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if not video_stream:
            raise ValueError("No video stream found in file")
        
        # Get audio stream
        audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
        
        # Extract format information
        format_info = probe.get('format', {})
        
        # Calculate duration
        duration = float(format_info.get('duration', 0))
        
        # Extract video metadata
        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        
        # Calculate FPS
        fps_str = video_stream.get('r_frame_rate', '0/1')
        if '/' in fps_str:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den != 0 else 0
        else:
            fps = float(fps_str)
        
        # Extract bitrates
        bitrate = int(format_info.get('bit_rate', 0))
        
        # Audio metadata
        audio_codec = audio_stream.get('codec_name', 'unknown') if audio_stream else 'none'
        audio_bitrate = int(audio_stream.get('bit_rate', 0)) if audio_stream else 0
        audio_sample_rate = int(audio_stream.get('sample_rate', 0)) if audio_stream else 0
        audio_channels = int(audio_stream.get('channels', 0)) if audio_stream else 0
        
        # File size
        file_size = int(format_info.get('size', 0))
        if file_size == 0:
            file_size = os.path.getsize(video_path)
        
        # Creation time
        creation_time = format_info.get('tags', {}).get('creation_time')
        
        metadata = VideoMetadata(
            filename=os.path.basename(video_path),
            duration=duration,
            width=width,
            height=height,
            fps=fps,
            bitrate=bitrate,
            format=format_info.get('format_name', 'unknown'),
            codec=video_stream.get('codec_name', 'unknown'),
            audio_codec=audio_codec,
            audio_bitrate=audio_bitrate,
            audio_sample_rate=audio_sample_rate,
            audio_channels=audio_channels,
            file_size=file_size,
            creation_time=creation_time,
            processed_at=datetime.now().isoformat(),
            streams=probe['streams']
        )
        
        logger.info(f"Extracted metadata for {os.path.basename(video_path)}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting metadata: {e}")
        raise

async def upload_to_s3(file_path: str, bucket: str, key: str, aws_access_key_id: str, 
                      aws_secret_access_key: str, aws_region: str) -> str:
    """Upload file to S3 and return the S3 URL"""
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        
        # Upload file
        logger.info(f"Uploading {file_path} to s3://{bucket}/{key}")
        s3_client.upload_file(file_path, bucket, key)
        
        # Return S3 URL
        s3_url = f"https://{bucket}.s3.{aws_region}.amazonaws.com/{key}"
        logger.info(f"Successfully uploaded to {s3_url}")
        return s3_url
        
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        raise
    except ClientError as e:
        logger.error(f"AWS S3 error: {e}")
        raise
    except Exception as e:
        logger.error(f"Error uploading to S3: {e}")
        raise

async def process_video(input_data: str) -> Dict[str, Any]:
    """
    Process a video file by downloading it, extracting metadata with ffmpeg, and uploading to S3.
    
    Args:
        input_data: JSON string with keys: video_url, s3_bucket, aws_access_key_id, 
                   aws_secret_access_key, aws_region (optional), output_prefix (optional)
    
    Returns:
        Dictionary containing processing results and S3 URLs
    """
    try:
        # Parse input JSON
        try:
            input_json = json.loads(input_data)
            processing_input = VideoProcessingInput(**input_json)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON input: {e}"}
        except Exception as e:
            return {"error": f"Invalid input format: {e}"}
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = await download_video(processing_input.video_url, temp_dir)
            
            # Extract metadata
            metadata = extract_video_metadata(video_path)
            
            # Prepare filenames
            base_filename = os.path.splitext(metadata.filename)[0]
            video_key = f"{processing_input.output_prefix}{metadata.filename}"
            metadata_key = f"{processing_input.output_prefix}{base_filename}_metadata.json"
            
            # Upload video to S3
            video_s3_url = await upload_to_s3(
                video_path, 
                processing_input.s3_bucket, 
                video_key,
                processing_input.aws_access_key_id,
                processing_input.aws_secret_access_key,
                processing_input.aws_region
            )
            
            # Create metadata JSON file
            metadata_path = os.path.join(temp_dir, f"{base_filename}_metadata.json")
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(metadata.model_dump_json(indent=2))
            
            # Upload metadata to S3
            metadata_s3_url = await upload_to_s3(
                metadata_path,
                processing_input.s3_bucket,
                metadata_key,
                processing_input.aws_access_key_id,
                processing_input.aws_secret_access_key,
                processing_input.aws_region
            )
            
            # Return results
            result = {
                "status": "success",
                "video_url": video_s3_url,
                "metadata_url": metadata_s3_url,
                "metadata": metadata.model_dump(),
                "processing_time": datetime.now().isoformat()
            }
            
            logger.info(f"Successfully processed video: {metadata.filename}")
            return result
            
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        return {"error": f"Processing failed: {str(e)}"}

async def get_video_info(video_url: str) -> Dict[str, Any]:
    """
    Get basic video information without full processing.
    
    Args:
        video_url: URL of the video to analyze
    
    Returns:
        Dictionary containing basic video information
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download video
            video_path = await download_video(video_url, temp_dir)
            
            # Extract metadata
            metadata = extract_video_metadata(video_path)
            
            # Return basic info
            return {
                "status": "success",
                "filename": metadata.filename,
                "duration": metadata.duration,
                "resolution": f"{metadata.width}x{metadata.height}",
                "fps": metadata.fps,
                "format": metadata.format,
                "codec": metadata.codec,
                "file_size": metadata.file_size,
                "audio_codec": metadata.audio_codec
            }
            
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return {"error": f"Failed to get video info: {str(e)}"}

# Clarifai hosting boilerplate
from clarifai.runners.models.model_class import ModelClass
from clarifai.runners.utils.data_utils import Param
from typing import Iterator

class MyModelClass(ModelClass):
    """Video processing model that extracts metadata and uploads to S3."""

    def load_model(self):
        """Nothing to load for this model."""
        pass

    @ModelClass.method
    def predict(self, prompt: str, process_type: str = Param(default="basic", description="type of processing to perform")) -> str:
        """
        Main prediction method that processes video and uploads to S3.
        
        Args:
            prompt: JSON string containing video_url and optional parameters
            process_type: Type of processing to perform
            
        Returns:
            JSON string containing processing results after completion
        """
        import asyncio
        
        try:
            # Parse input to extract video URL
            input_json = json.loads(prompt)
            video_url = input_json.get("video_url", "unknown")
            
            # Build full input with environment variables
            full_input = {
                "video_url": video_url,
                "s3_bucket": os.getenv("DEFAULT_S3_BUCKET", "default-bucket"),
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", ""),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                "output_prefix": input_json.get("output_prefix", "processed_videos/")
            }
            
            # Run the actual video processing synchronously
            result = asyncio.run(process_video(json.dumps(full_input)))
            
            # Add endpoint identification and process_type to the result
            if isinstance(result, dict):
                result["endpoint"] = "predict"
                result["process_type"] = process_type
                result["video_url"] = video_url
            
            return json.dumps(result)
            
        except json.JSONDecodeError:
            return json.dumps({
                "endpoint": "predict",
                "status": "error", 
                "message": "Invalid JSON input. Please provide a valid JSON string.",
                "example": {
                    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                    "output_prefix": "my_videos/"
                },
                "note": "AWS credentials are loaded from environment variables"
            })
        except Exception as e:
            return json.dumps({
                "endpoint": "predict",
                "status": "error",
                "message": f"Error processing video: {str(e)}"
            })
    
    @ModelClass.method
    def generate(self, prompt: str = "", iterations: int = Param(default=10, description="number of frames to analyze")) -> Iterator[str]:
        """
        Generate frame-by-frame video analysis results.
        
        Args:
            prompt: JSON string containing video_url and optional parameters
            iterations: Number of frames to analyze (default 10)
            
        Yields:
            JSON strings with frame-by-frame analysis results
        """
        import asyncio
        import tempfile
        import cv2
        import numpy as np
        
        try:
            # Parse input to extract video URL
            input_json = json.loads(prompt) if prompt else {}
            video_url = input_json.get("video_url", "unknown")
            
            # Download video to temporary location
            with tempfile.TemporaryDirectory() as temp_dir:
                video_path = asyncio.run(download_video(video_url, temp_dir))
                
                # Open video with OpenCV
                cap = cv2.VideoCapture(video_path)
                
                # Get video properties
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                # Calculate frame interval based on iterations
                frame_interval = max(1, total_frames // iterations) if iterations > 0 else 1
                
                frame_count = 0
                analyzed_frames = 0
                
                while cap.isOpened() and analyzed_frames < iterations:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    # Only analyze every nth frame
                    if frame_count % frame_interval == 0:
                        # Calculate frame timestamp
                        timestamp = frame_count / fps
                        
                        # Analyze frame properties
                        frame_size = frame.nbytes
                        frame_mean = np.mean(frame)
                        frame_std = np.std(frame)
                        
                        # Color channel analysis
                        b_mean = np.mean(frame[:,:,0])
                        g_mean = np.mean(frame[:,:,1])
                        r_mean = np.mean(frame[:,:,2])
                        
                        # Detect edges (complexity measure)
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        edges = cv2.Canny(gray, 50, 150)
                        edge_density = np.sum(edges > 0) / (width * height)
                        
                        # Brightness analysis
                        brightness = np.mean(gray)
                        
                        frame_result = {
                            "endpoint": "generate",
                            "status": "analyzing",
                            "video_url": video_url,
                            "frame_number": frame_count,
                            "frame_index": analyzed_frames + 1,
                            "total_frames": total_frames,
                            "timestamp": round(timestamp, 3),
                            "frame_properties": {
                                "width": width,
                                "height": height,
                                "size_bytes": frame_size,
                                "brightness": round(brightness, 2),
                                "complexity": round(edge_density, 4),
                                "color_analysis": {
                                    "mean_intensity": round(frame_mean, 2),
                                    "std_intensity": round(frame_std, 2),
                                    "red_mean": round(r_mean, 2),
                                    "green_mean": round(g_mean, 2),
                                    "blue_mean": round(b_mean, 2)
                                }
                            },
                            "video_info": {
                                "fps": fps,
                                "duration": round(total_frames / fps, 2),
                                "total_frames": total_frames
                            }
                        }
                        
                        yield json.dumps(frame_result)
                        analyzed_frames += 1
                    
                    frame_count += 1
                
                cap.release()
                
                # Final summary
                summary_result = {
                    "endpoint": "generate",
                    "status": "complete",
                    "video_url": video_url,
                    "summary": {
                        "total_frames_analyzed": analyzed_frames,
                        "total_frames_in_video": total_frames,
                        "video_duration": round(total_frames / fps, 2),
                        "analysis_complete": True
                    }
                }
                yield json.dumps(summary_result)
                
        except json.JSONDecodeError:
            yield json.dumps({
                "endpoint": "generate",
                "status": "error",
                "message": "Invalid JSON input. Please provide a valid JSON string.",
                "example": {
                    "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                    "output_prefix": "my_videos/"
                },
                "note": "AWS credentials are loaded from environment variables"
            })
        except Exception as e:
            yield json.dumps({
                "endpoint": "generate",
                "status": "error", 
                "message": f"Error analyzing video frames: {str(e)}"
            })
    
    @ModelClass.method
    def s(self, input_iterator: Iterator[str], batch_size: int = Param(default=1, description="batch processing size")) -> Iterator[str]:
        """
        Stream processing method that processes each video in the iterator.
        
        Args:
            input_iterator: Iterator of JSON strings containing video_url and optional parameters
            batch_size: Size of processing batches (ignored, kept for compatibility)
            
        Yields:
            JSON strings with complete processing results for each video
        """
        import asyncio
        
        for i, prompt in enumerate(input_iterator):
            try:
                # Parse input to extract video URL
                input_json = json.loads(prompt) if prompt else {}
                video_url = input_json.get("video_url", "unknown")
                
                # Build full input with environment variables
                full_input = {
                    "video_url": video_url,
                    "s3_bucket": os.getenv("DEFAULT_S3_BUCKET", "default-bucket"),
                    "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID", ""),
                    "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                    "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
                    "output_prefix": input_json.get("output_prefix", "processed_videos/")
                }
                
                # Run the actual video processing synchronously
                result = asyncio.run(process_video(json.dumps(full_input)))
                
                # Add endpoint identification and batch info to the result
                if isinstance(result, dict):
                    result["endpoint"] = "s"
                    result["batch_index"] = i
                    result["video_url"] = video_url
                
                yield json.dumps(result)
                
            except json.JSONDecodeError:
                yield json.dumps({
                    "endpoint": "s",
                    "status": "error",
                    "batch_index": i,
                    "message": "Invalid JSON input. Please provide a valid JSON string.",
                    "example": {
                        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
                        "output_prefix": "my_videos/"
                    },
                    "note": "AWS credentials are loaded from environment variables"
                })
            except Exception as e:
                yield json.dumps({
                    "endpoint": "s",
                    "status": "error",
                    "batch_index": i,
                    "message": f"Error processing video: {str(e)}"
                })

def test_predict() -> None:
    """Test the predict method of MyModelClass by printing its output."""
    model = MyModelClass()
    model.load_model()
    print("Testing predict method:")
    test_input = {
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "output_prefix": "bigbuckbunny_test/"
    }
    output = model.predict(json.dumps(test_input), process_type="full")
    print(output)

def test_generate() -> None:
    """Test the generate method of MyModelClass by printing its outputs."""
    model = MyModelClass()
    model.load_model()
    print("Testing generate method:")
    test_input = {
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "output_prefix": "bigbuckbunny_test/"
    }
    for output in model.generate(json.dumps(test_input), iterations=4):
        print(output)

def test_stream() -> None:
    """Test the stream method of MyModelClass by printing its outputs."""
    model = MyModelClass()
    model.load_model()
    print("Testing stream method:")
    test_input = {
        "video_url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "output_prefix": "bigbuckbunny_test/"
    }
    # Test with one video input
    test_inputs = [json.dumps(test_input)]
    for output in model.s(iter(test_inputs)):
        print(output)

def test_error_handling() -> None:
    """Test error handling with invalid JSON input."""
    model = MyModelClass()
    model.load_model()
    print("Testing error handling with invalid JSON:")
    
    # Test with invalid JSON
    invalid_input = "this is not json"
    output = model.predict(invalid_input, process_type="full")
    print(f"Invalid JSON Response: {output}")
    
    # Test with empty string
    empty_input = ""
    output = model.predict(empty_input, process_type="full")
    print(f"Empty Input Response: {output}")

if __name__ == "__main__":
    test_predict()
    print()
    test_generate()
    print()
    test_stream()
    print()
    test_error_handling()