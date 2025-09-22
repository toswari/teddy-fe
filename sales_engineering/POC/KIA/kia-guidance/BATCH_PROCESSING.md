# Clarifai Batch Processing Documentation

## Overview

The Clarifai batch processing feature allows you to analyze multiple images efficiently in a single API call, supporting up to **128 images** with a maximum total size of **128 MB**.

## Key Features

### 🚀 Performance Benefits
- **Bulk Processing**: Analyze up to 128 images in one request
- **Faster Throughput**: Reduced API overhead compared to individual calls
- **Cost Efficient**: Optimized token usage for large batches
- **Automatic Fallback**: Falls back to individual processing if batch fails

### 🛡️ Safety & Validation
- **Size Limits**: Automatic validation of batch size and total MB
- **Error Handling**: Graceful handling of failed images in batch
- **Backward Compatibility**: Works alongside existing single-image processing
- **Progress Tracking**: Built-in progress monitoring for large batches

## API Reference

### `validate_batch_size(images: list) -> bool`

Validates that a batch meets Clarifai's limits.

**Parameters:**
- `images`: List of image data (bytes or file paths)

**Returns:**
- `True` if valid, raises `ValueError` if limits exceeded

**Limits:**
- Maximum 128 images per batch
- Maximum 128 MB total size

**Example:**
```python
from clarifai_utils import validate_batch_size

# Validate a batch of images
try:
    validate_batch_size(image_list)
    print("✅ Batch is valid")
except ValueError as e:
    print(f"❌ Batch validation failed: {e}")
```

### `analyze_images_batch(images: list, model_id: str = "gemini-2_5-pro") -> list`

Analyze multiple images using Clarifai batch processing.

**Parameters:**
- `images`: List of image data as bytes
- `model_id`: Model identifier from config.toml (default: "gemini-2_5-pro")

**Returns:**
List of dictionaries, each containing:
```python
{
    'image_index': int,          # Index in original batch
    'summary': str,              # Human-readable summary
    'json_output': dict,         # Full structured response
    'input_tokens': int,         # Tokens used for input
    'output_tokens': int,        # Tokens used for output
    'violations': list,          # List of violations found
    'success': bool              # Whether analysis succeeded
}
```

**Example:**
```python
from clarifai_utils import analyze_images_batch

# Load images
images = []
for path in image_paths:
    with open(path, 'rb') as f:
        images.append(f.read())

# Analyze batch
results = analyze_images_batch(images, "gemini-2_5-pro")

# Process results
for result in results:
    print(f"Image {result['image_index']}: {result['summary']}")
    if result['violations']:
        print(f"  ⚠️ {len(result['violations'])} violations found")
```

### `analyze_images_batch_from_files(file_paths: list, model_id: str = "gemini-2_5-pro") -> list`

Convenience function to analyze images directly from file paths.

**Parameters:**
- `file_paths`: List of image file paths
- `model_id`: Model identifier from config.toml

**Returns:**
Same format as `analyze_images_batch()`

**Example:**
```python
from clarifai_utils import analyze_images_batch_from_files

# Analyze images from file paths
image_paths = ['logo1.png', 'logo2.jpg', 'logo3.png']
results = analyze_images_batch_from_files(image_paths)

# Count violations across all images
total_violations = sum(len(r['violations']) for r in results)
print(f"Found {total_violations} total violations across {len(results)} images")
```

## Usage Examples

### Basic Batch Processing

```python
import streamlit as st
from clarifai_utils import analyze_images_batch

# Upload multiple files in Streamlit
uploaded_files = st.file_uploader(
    "Choose images", 
    accept_multiple_files=True,
    type=['png', 'jpg', 'jpeg']
)

if uploaded_files:
    # Convert to bytes
    images = [file.read() for file in uploaded_files]
    
    # Validate batch
    if len(images) <= 128:
        # Process batch
        results = analyze_images_batch(images)
        
        # Display results
        for i, result in enumerate(results):
            st.write(f"**Image {i+1}:** {result['summary']}")
            if result['violations']:
                st.error(f"⚠️ {len(result['violations'])} violations")
```

### Advanced Error Handling

```python
from clarifai_utils import analyze_images_batch, validate_batch_size

def safe_batch_analysis(images, model_id="gemini-2_5-pro"):
    try:
        # Validate batch first
        validate_batch_size(images)
        
        # Process batch
        results = analyze_images_batch(images, model_id)
        
        # Separate successful and failed results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"✅ {len(successful)} succeeded, ❌ {len(failed)} failed")
        
        return successful, failed
        
    except ValueError as e:
        print(f"❌ Batch validation failed: {e}")
        return [], []
    except Exception as e:
        print(f"❌ Batch processing failed: {e}")
        return [], []
```

### Progress Tracking in Streamlit

```python
import streamlit as st
import time
from clarifai_utils import analyze_images_batch

def batch_with_progress(images):
    # Show progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("🔄 Starting batch analysis...")
        progress_bar.progress(0.1)
        
        # Run batch analysis
        start_time = time.time()
        results = analyze_images_batch(images)
        end_time = time.time()
        
        progress_bar.progress(1.0)
        
        # Show completion
        processing_time = end_time - start_time
        status_text.success(f"✅ Completed in {processing_time:.1f}s")
        
        return results
        
    except Exception as e:
        status_text.error(f"❌ Failed: {e}")
        return []
    finally:
        # Clean up UI elements
        time.sleep(1)
        progress_bar.empty()
        status_text.empty()
```

## Performance Considerations

### Batch Size Optimization

- **Small batches (1-10 images)**: Use individual processing for better responsiveness
- **Medium batches (10-50 images)**: Optimal for batch processing
- **Large batches (50-128 images)**: Maximum efficiency but longer wait times

### Memory Management

- **Image Size**: Larger images consume more memory and bandwidth
- **Total Size**: Keep total batch under 128 MB for best performance
- **Format**: Use compressed formats (JPEG) for large batches when possible

### Error Recovery

The batch processor includes automatic fallback:

1. **Primary**: Uses new Clarifai batch client for optimal performance
2. **Fallback**: Falls back to individual processing if batch fails
3. **Partial Success**: Handles cases where some images succeed and others fail

## Integration with Existing Code

The batch processing functions work alongside existing code:

```python
# Existing single-image processing
result = analyze_image(image_bytes, "gemini-2_5-pro")

# New batch processing
results = analyze_images_batch([image_bytes], "gemini-2_5-pro")
# results[0] has the same structure as the single result
```

## Configuration

Batch processing uses the same model configuration as individual processing:

```toml
# config.toml
[gemini-2_5-pro]
model_url = "https://clarifai.com/user/app/models/model-id"
prompt_text = "Analyze this image for brand compliance..."
```

## Troubleshooting

### Common Issues

1. **Batch size exceeded**: Reduce number of images or total size
2. **Import errors**: Ensure `clarifai` package is installed with batch support
3. **API errors**: Check PAT and model configuration
4. **Memory issues**: Process smaller batches or optimize image sizes

### Debug Mode

Enable debug output to see detailed processing information:

```python
# Debug output is automatically enabled in the functions
# Look for "🔍 DEBUG:" messages in console output
```

## Migration Guide

### From Individual to Batch Processing

**Before:**
```python
results = []
for image in images:
    result = analyze_image(image, model_id)
    results.append(result)
```

**After:**
```python
# Convert single results to batch format if needed
batch_results = analyze_images_batch(images, model_id)
results = [(r['summary'], r['json_output'], r['input_tokens'], 
           r['output_tokens'], r['violations']) for r in batch_results]
```

This maintains compatibility while gaining performance benefits of batch processing.
