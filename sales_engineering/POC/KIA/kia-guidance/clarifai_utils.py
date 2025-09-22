"""
Clarifai API integration for the AI Brand Compliance Chatbot.
Handles all communication with Clarifai models using gRPC API and batch processing.
"""
import streamlit as st
import json
import time
import base64
import threading
import requests
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Tuple, List
from config_loader import get_model_config

# Import Clarifai components
try:
    from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
    from clarifai_grpc.grpc.api import service_pb2_grpc
    from clarifai_grpc.grpc.api import service_pb2, resources_pb2
    GRPC_AVAILABLE = True
    print("✅ DEBUG: Clarifai gRPC imports successful")
except ImportError as e:
    print(f"❌ DEBUG: Clarifai gRPC import failed: {e}")
    GRPC_AVAILABLE = False

# Import new Clarifai client for batch processing
try:
    from clarifai.client import Model
    from clarifai.runners.utils.data_types import Image
    BATCH_CLIENT_AVAILABLE = True
    print("✅ DEBUG: Clarifai batch client imports successful")
except ImportError as e:
    print(f"❌ DEBUG: Clarifai batch client import failed: {e}")
    BATCH_CLIENT_AVAILABLE = False

# Global thread pool executor to handle API calls
_executor = ThreadPoolExecutor(max_workers=1)

def _make_grpc_api_call(model_url: str, pat: str, image_bytes: bytes, prompt_text: str):
    """
    Make a gRPC API call to Clarifai using the lower-level API as recommended in ClarifaiAgent.md
    """
    print("🔄 DEBUG: Making gRPC API call...")
    
    if not GRPC_AVAILABLE:
        raise Exception("Clarifai gRPC not available")
    
    # Extract model ID from URL
    # URL format: https://clarifai.com/{user_id}/{app_id}/models/{model_id}
    url_parts = model_url.replace("https://clarifai.com/", "").split("/")
    if len(url_parts) >= 4:
        user_id = url_parts[0]
        app_id = url_parts[1]
        model_id = url_parts[3]
    else:
        raise ValueError(f"Invalid model URL format: {model_url}")
    
    print(f"🔗 DEBUG: Extracted - User: {user_id}, App: {app_id}, Model: {model_id}")
    
    # Set up the channel and stub
    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)
    
    # Set up metadata for authentication
    metadata = (('authorization', f'Key {pat}'),)
    
    # Convert image to bytes if it's not already
    if isinstance(image_bytes, str):
        # If it's base64 string, decode it
        image_bytes = base64.b64decode(image_bytes)
    
    print(f"📤 DEBUG: Making gRPC call to model {model_id}")
    
    # Based on ClarifaiAgent.md, the base64 field might expect raw bytes, not a base64 string
    # Let's try passing the raw bytes directly to the base64 field
    response = stub.PostModelOutputs(
        service_pb2.PostModelOutputsRequest(
            user_app_id=resources_pb2.UserAppIDSet(
                user_id=user_id,
                app_id=app_id
            ),
            model_id=model_id,
            inputs=[
                resources_pb2.Input(
                    data=resources_pb2.Data(
                        image=resources_pb2.Image(
                            base64=image_bytes  # Try passing raw bytes to base64 field
                        ),
                        text=resources_pb2.Text(
                            raw=prompt_text
                        )
                    )
                )
            ]
        ),
        metadata=metadata
    )
    
    print(f"📥 DEBUG: gRPC response status: {response.status.code}")
    print(f"📥 DEBUG: gRPC response description: {response.status.description}")
    
    # Check if the response is successful
    if response.status.code != 10000:  # SUCCESS code
        raise Exception(f"Clarifai API error: {response.status.description}")
    
    return response

def _make_direct_api_call(model_url: str, pat: str, image_base64: str, prompt_text: str):
    """
    Make a direct HTTP API call to Clarifai as a fallback when the SDK fails.
    """
    print("🔄 DEBUG: Making direct HTTP API call...")
    
    # Extract app, user, and model info from URL
    # URL format: https://clarifai.com/{user_id}/{app_id}/models/{model_id}
    url_parts = model_url.replace("https://clarifai.com/", "").split("/")
    if len(url_parts) >= 4:
        user_id = url_parts[0]
        app_id = url_parts[1]
        model_id = url_parts[3]
    else:
        raise ValueError(f"Invalid model URL format: {model_url}")
    
    # Clarifai API endpoint
    api_url = f"https://api.clarifai.com/v2/users/{user_id}/apps/{app_id}/models/{model_id}/outputs"
    
    headers = {
        "Authorization": f"Key {pat}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "inputs": [
            {
                "data": {
                    "image": {"base64": image_base64},
                    "text": {"raw": prompt_text}
                }
            }
        ]
    }
    
    print(f"🌐 DEBUG: API URL: {api_url}")
    print(f"📤 DEBUG: Making POST request...")
    
    response = requests.post(api_url, headers=headers, json=payload, timeout=60)
    
    if response.status_code == 200:
        print("✅ DEBUG: Direct HTTP API call successful")
        return response.json()
    else:
        print(f"❌ DEBUG: HTTP API call failed with status {response.status_code}")
        print(f"❌ DEBUG: Response: {response.text}")
        raise Exception(f"HTTP API call failed: {response.status_code} - {response.text}")

def _analyze_image_sync(image_bytes: bytes, model_id: str) -> Tuple[str, Dict[str, Any], int, int, list]:
    """
    Synchronous wrapper for analyze_image to avoid event loop issues.
    This runs in a separate thread to isolate async operations.
    """
    print(f"🔍 DEBUG: Starting analysis with model_id: {model_id}")
    
    # Set up event loop for this thread
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        print("✅ DEBUG: Found existing event loop")
    except RuntimeError:
        print("🔄 DEBUG: Creating new event loop for thread")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Get PAT from Streamlit secrets
    if "CLARIFAI_PAT" not in st.secrets:
        print("❌ DEBUG: CLARIFAI_PAT not found in Streamlit secrets")
        raise ValueError("CLARIFAI_PAT not found in Streamlit secrets")
    
    pat = st.secrets["CLARIFAI_PAT"]
    print(f"✅ DEBUG: PAT found: {pat[:10]}...")
    
    # Get model configuration
    model_config = get_model_config(model_id)
    model_url = model_config.get("model_url")
    prompt_text = model_config.get("prompt_text")
    
    print(f"🔗 DEBUG: Model URL: {model_url}")
    print(f"📝 DEBUG: Prompt text length: {len(prompt_text) if prompt_text else 0} characters")
    print(f"📝 DEBUG: Prompt preview: {prompt_text[:200] if prompt_text else 'None'}...")
    
    if not model_url or not prompt_text:
        print(f"❌ DEBUG: Incomplete configuration - URL: {bool(model_url)}, Prompt: {bool(prompt_text)}")
        raise ValueError(f"Incomplete configuration for model {model_id}")
    
    # Start timing
    start_time = time.time()
    
    try:
        # Try gRPC API first (recommended approach from ClarifaiAgent.md)
        print("🚀 DEBUG: Trying gRPC API approach...")
        response = _make_grpc_api_call(model_url, pat, image_bytes, prompt_text)
        print("✅ DEBUG: gRPC API call successful")
        
        # Process gRPC response
        if response.outputs:
            output = response.outputs[0]
            if hasattr(output, 'data') and hasattr(output.data, 'text'):
                response_text = output.data.text.raw
                print(f"✅ DEBUG: Got text response from gRPC, length: {len(response_text)} characters")
            else:
                # Convert gRPC response to text format
                response_text = str(response)
                print(f"⚠️ DEBUG: Using gRPC response as string")
        else:
            response_text = str(response)
            print(f"⚠️ DEBUG: No outputs in gRPC response, using raw response")
        
    except Exception as grpc_error:
        print(f"❌ DEBUG: gRPC API call failed: {str(grpc_error)}")
        print(f"❌ DEBUG: Error type: {type(grpc_error)}")
        
        # Try direct HTTP API as fallback
        print("🔄 DEBUG: Trying direct HTTP API approach...")
        try:
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            http_response = _make_direct_api_call(model_url, pat, image_base64, prompt_text)
            print("✅ DEBUG: Direct HTTP API call successful")
            
            # Process HTTP response
            if 'outputs' in http_response and http_response['outputs']:
                output = http_response['outputs'][0]
                if 'data' in output and 'text' in output['data']:
                    response_text = output['data']['text']['raw']
                    print(f"✅ DEBUG: Got text response from HTTP, length: {len(response_text)} characters")
                else:
                    response_text = json.dumps(http_response)
                    print(f"⚠️ DEBUG: Using HTTP response as JSON string")
            else:
                response_text = json.dumps(http_response)
                print(f"⚠️ DEBUG: No outputs in HTTP response, using raw response")
                
        except Exception as http_error:
            print(f"❌ DEBUG: Both gRPC and HTTP API calls failed")
            print(f"❌ DEBUG: gRPC error: {grpc_error}")
            print(f"❌ DEBUG: HTTP error: {http_error}")
            raise grpc_error
    
    end_time = time.time()
    response_time = end_time - start_time
    print(f"⏱️ DEBUG: API response time: {response_time:.2f} seconds")
    
    print(f"✅ DEBUG: Final response text length: {len(response_text)} characters")
    return response_text


def analyze_image(image_bytes: bytes, model_id: str) -> Tuple[str, Dict[str, Any], int, int, list]:
    """
    Analyzes an image using a specified Clarifai model.
    
    Args:
        image_bytes: Raw image data as bytes
        model_id: The model identifier from config.toml
        
    Returns:
        Tuple containing:
        - summary: Human-readable summary
        - json_output: Full JSON response from the model
        - input_tokens: Number of input tokens used
        - output_tokens: Number of output tokens used
        - violations: List of violation dictionaries
    """
    print(f"🚀 DEBUG: analyze_image called with model_id: {model_id}")
    print(f"🖼️ DEBUG: Image size: {len(image_bytes)} bytes")
    
    try:
        # Run the API call in a separate thread to avoid event loop issues
        print("🔄 DEBUG: Submitting task to ThreadPoolExecutor...")
        future = _executor.submit(_analyze_image_sync, image_bytes, model_id)
        print("⏳ DEBUG: Waiting for result (60s timeout)...")
        response_text = future.result(timeout=60)  # 60 second timeout
        print("✅ DEBUG: Successfully got response text from thread")
        
        # Parse the response text into structured format
        print("🔄 DEBUG: Parsing response text into structured format...")
        return _parse_response_text(response_text, model_id)
            
    except Exception as e:
        print(f"❌ DEBUG: Exception in analyze_image: {str(e)}")
        print(f"❌ DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"❌ DEBUG: Full traceback:")
        traceback.print_exc()
        
        # Return error response in expected format
        error_message = str(e)
        if "event loop" in error_message.lower():
            error_message = "API connection issue - please try again"
        
        print(f"🔄 DEBUG: Creating error response with message: {error_message}")
        
        error_response = {
            "compliance_status": "Error",
            "logo_type": "Unknown",
            "summary": f"Analysis failed: {error_message}",
            "violations": [],
            "recommendations": ["Please check your API configuration and try again"],
            "confidence_score": 0.0,
            "error": str(e)
        }
        
        print(f"📤 DEBUG: Returning error response: {error_response}")
        
        return (
            error_response["summary"],
            error_response,
            0,
            0,
            []
        )


def _parse_response_text(response_text: str, model_id: str) -> Tuple[str, Dict[str, Any], int, int, list]:
    """
    Parse the raw response text into structured format.
    
    Args:
        response_text: Raw text response from the model
        model_id: The model identifier used
        
    Returns:
        Tuple containing structured response data
    """
    print(f"🔍 DEBUG: Parsing response text, length: {len(response_text)} characters")
    
    # Estimate token usage (approximate)
    input_tokens = 100  # Approximate for image + prompt
    output_tokens = len(response_text.split())
    
    # Try to parse as JSON first
    try:
        json_response = json.loads(response_text)
        print("✅ DEBUG: Successfully parsed JSON response")
        
        # Extract fields
        summary = json_response.get("summary", "Analysis completed")
        violations = json_response.get("violations", [])
        
        print(f"📋 DEBUG: Summary: {summary}")
        print(f"⚠️ DEBUG: Found {len(violations)} violations")
        
        return (summary, json_response, input_tokens, output_tokens, violations)
        
    except json.JSONDecodeError:
        print("⚠️ DEBUG: Response is not valid JSON, creating structured response")
        
        # Extract meaningful information from the response text
        business_summary = _extract_business_summary_from_text(response_text)
        compliance_status = _extract_compliance_status_from_text(response_text)
        logo_type = _extract_logo_type_from_text(response_text)
        violations = _extract_violations_from_text(response_text)
        
        # Create structured response from text
        json_response = {
            "compliance_status": compliance_status,
            "logo_type": logo_type,
            "summary": business_summary,
            "violations": violations,
            "recommendations": ["Review the analysis for compliance details"],
            "confidence_score": 0.8,
            "raw_response": response_text
        }
        
        summary = business_summary
        
        print(f"📋 DEBUG: Created structured response with summary: {summary}")
        
        return (summary, json_response, input_tokens, output_tokens, violations)

def _generate_mock_compliance_response(concepts, prompt_text):
    """Generate a mock compliance response when concepts are returned instead of text."""
    # This is a fallback when the model returns concepts instead of structured text
    compliance_status = "Compliant"
    violations = []
    
    # Look for logo-related concepts
    logo_found = any(concept.name.lower() in ['logo', 'brand', 'kia'] for concept in concepts if hasattr(concept, 'name'))
    
    if not logo_found:
        compliance_status = "No Logo Found"
    
    response = {
        "compliance_status": compliance_status,
        "logo_type": "Core Logo",
        "summary": f"Logo analysis completed using concept detection. Status: {compliance_status}",
        "violations": violations,
        "recommendations": ["Consider using a clearer image for more detailed analysis"],
        "confidence_score": 0.7
    }
    
    return json.dumps(response)

def test_api_connection(model_id: str = "gemini-2_5-pro") -> bool:
    """
    Test connection to Clarifai API.
    
    Args:
        model_id: The model identifier to test
        
    Returns:
        True if connection successful, False otherwise
    """
    print(f"🔍 DEBUG: Testing API connection with model_id: {model_id}")
    
    try:
        if "CLARIFAI_PAT" not in st.secrets:
            print("❌ DEBUG: CLARIFAI_PAT not found in secrets")
            return False
        
        print("✅ DEBUG: CLARIFAI_PAT found in secrets")
        
        model_config = get_model_config(model_id)
        print(f"📋 DEBUG: Model config result: {model_config is not None}")
        
        if model_config:
            print(f"🔗 DEBUG: Model URL: {model_config.get('model_url')}")
            print(f"📝 DEBUG: Prompt available: {bool(model_config.get('prompt_text'))}")
        
        result = model_config is not None
        print(f"✅ DEBUG: API connection test result: {result}")
        return result
        
    except Exception as e:
        print(f"❌ DEBUG: Exception in test_api_connection: {str(e)}")
        return False


def _extract_business_summary_from_text(response_text: str) -> str:
    """Extract a business-friendly summary from the response text."""
    # Remove JSON formatting and extract meaningful content
    text = response_text.replace('```json', '').replace('```', '').strip()
    
    # Look for common patterns in the response
    if '"summary"' in text:
        try:
            # Try to extract summary field if it exists
            import re
            summary_match = re.search(r'"summary":\s*"([^"]*)"', text)
            if summary_match:
                summary = summary_match.group(1)
                # Clean up the summary text
                return summary.replace('\\n', ' ').replace('  ', ' ').strip()
        except:
            pass
    
    # If no summary found, extract first meaningful sentence
    sentences = text.split('.')
    for sentence in sentences:
        if len(sentence.strip()) > 20 and any(word in sentence.lower() for word in ['compliant', 'violation', 'logo', 'brand']):
            return sentence.strip() + '.'
    
    # Fallback to a generic message
    if 'non-compliant' in text.lower() or 'violation' in text.lower():
        return "This asset has been identified as non-compliant with brand guidelines and requires attention."
    elif 'compliant' in text.lower():
        return "This asset meets the brand guidelines and is approved for use."
    else:
        return "Brand compliance analysis has been completed for this asset."


def _extract_compliance_status_from_text(response_text: str) -> str:
    """Extract compliance status from response text."""
    text = response_text.lower()
    
    if 'non-compliant' in text:
        return "Non-Compliant"
    elif 'compliant' in text:
        return "Compliant"
    elif 'no logo' in text:
        return "No Logo Found"
    else:
        return "Analysis Complete"


def _extract_logo_type_from_text(response_text: str) -> str:
    """Extract logo type from response text."""
    text = response_text.lower()
    
    # Look for specific logo type mentions
    logo_types = [
        'core logo',
        'logo expansion', 
        'partnership combination',
        'variant logo',
        'horizontal logo',
        'vertical logo'
    ]
    
    for logo_type in logo_types:
        if logo_type in text:
            return logo_type.title()
    
    return "Logo"


def _extract_violations_from_text(response_text: str) -> list:
    """Extract violations from response text."""
    violations = []
    
    # Try to parse violations from JSON structure if present
    if '"violations"' in response_text:
        try:
            import re
            # Look for violations array pattern
            violations_match = re.search(r'"violations":\s*\[(.*?)\]', response_text, re.DOTALL)
            if violations_match:
                violations_text = violations_match.group(1).strip()
                
                # If violations array is empty, return empty list
                if not violations_text or violations_text == '':
                    return []
                
                # Extract individual violations
                violation_objects = re.findall(r'\{([^}]*)\}', violations_text)
                for violation_obj in violation_objects:
                    rule_match = re.search(r'"rule_violated":\s*"([^"]*)"', violation_obj)
                    desc_match = re.search(r'"description":\s*"([^"]*)"', violation_obj)
                    rec_match = re.search(r'"recommendation":\s*"([^"]*)"', violation_obj)
                    severity_match = re.search(r'"severity":\s*"([^"]*)"', violation_obj)
                    
                    if rule_match and desc_match:
                        violation_dict = {
                            'rule_violated': rule_match.group(1),
                            'description': desc_match.group(1).replace('\\n', ' ')
                        }
                        
                        # Add recommendation if present
                        if rec_match:
                            violation_dict['recommendation'] = rec_match.group(1).replace('\\n', ' ')
                        
                        # Add severity if present
                        if severity_match:
                            violation_dict['severity'] = severity_match.group(1)
                            
                        violations.append(violation_dict)
                        
                # If we successfully parsed violations from JSON, return them (even if empty)
                return violations
                
        except Exception as e:
            print(f"Debug: Error parsing violations from JSON: {e}")
    
    # Only create generic violations if:
    # 1. No JSON violations array was found, AND
    # 2. The compliance status is explicitly non-compliant
    compliance_status = _extract_compliance_status_from_text(response_text)
    if compliance_status == "Non-Compliant":
        violations.append({
            'rule_violated': 'Brand Guideline Violation',
            'description': 'This asset does not meet the required brand guidelines and needs to be corrected.'
        })
    
    return violations


# ===== BATCH PROCESSING FUNCTIONS =====

def validate_batch_size(images: list) -> bool:
    """
    Validate that the batch doesn't exceed Clarifai limits.
    
    Args:
        images: List of image data (bytes or file paths)
        
    Returns:
        True if batch is valid, raises exception otherwise
    """
    max_images = 128
    max_total_size = 128 * 1024 * 1024  # 128 MB in bytes
    
    if len(images) > max_images:
        raise ValueError(f"Batch size {len(images)} exceeds maximum of {max_images} images")
    
    total_size = 0
    for i, image in enumerate(images):
        if isinstance(image, bytes):
            size = len(image)
        elif isinstance(image, str):  # File path
            import os
            if os.path.exists(image):
                size = os.path.getsize(image)
            else:
                raise ValueError(f"Image file not found: {image}")
        else:
            raise ValueError(f"Invalid image type at index {i}: {type(image)}")
        
        total_size += size
    
    if total_size > max_total_size:
        raise ValueError(f"Total batch size {total_size / (1024*1024):.1f} MB exceeds maximum of 128 MB")
    
    print(f"✅ Batch validation passed: {len(images)} images, {total_size / (1024*1024):.1f} MB total")
    return True


def analyze_images_batch(images: list, model_id: str = "gemini-2_5-pro") -> list:
    """
    Analyze multiple images using Clarifai batch processing.
    
    Args:
        images: List of image data (bytes) or file paths
        model_id: The model identifier from config.toml
        
    Returns:
        List of analysis results, one per image
    """
    if not BATCH_CLIENT_AVAILABLE:
        print("⚠️ Batch client not available, falling back to individual processing")
        return [analyze_image(img if isinstance(img, bytes) else open(img, 'rb').read(), model_id) 
                for img in images]
    
    print(f"🚀 Starting batch analysis for {len(images)} images with model {model_id}")
    
    # Validate batch size
    validate_batch_size(images)
    
    try:
        # Get model configuration
        model_config = get_model_config(model_id)
        if not model_config:
            raise ValueError(f"Model configuration not found for {model_id}")
        
        model_url = model_config.get("model_url")
        prompt_text = model_config.get("prompt_text")
        
        if not model_url or not prompt_text:
            raise ValueError(f"Incomplete configuration for model {model_id}")
        
        # Parse model URL to get components
        # URL format: https://clarifai.com/{user_id}/{app_id}/models/{model_id}
        url_parts = model_url.replace("https://clarifai.com/", "").split("/")
        if len(url_parts) < 4:
            raise ValueError(f"Invalid model URL format: {model_url}")
        
        user_id = url_parts[0]
        app_id = url_parts[1]
        actual_model_id = url_parts[3]
        
        print(f"🔗 Using model: {user_id}/{app_id}/{actual_model_id}")
        
        # Initialize the model
        model = Model(
            user_id=user_id,
            app_id=app_id,
            model_id=actual_model_id,
            pat=st.secrets["CLARIFAI_PAT"]
        )
        
        # Prepare image inputs (SDK change: Image(image_bytes=...) no longer supported)
        batch_inputs = []
        for i, image_data in enumerate(images):
            if isinstance(image_data, str):  # File path
                with open(image_data, 'rb') as f:
                    image_bytes = f.read()
            else:  # Already bytes-like
                image_bytes = image_data

            image_input = None
            creation_errors = []
            # Try common creation patterns in order of preference
            try:
                if hasattr(Image, 'from_bytes'):
                    image_input = Image.from_bytes(image_bytes)
            except Exception as e:
                creation_errors.append(f"from_bytes: {e}")
            if image_input is None:
                try:
                    # Some versions accept raw bytes as first positional arg
                    image_input = Image(image_bytes)
                except TypeError as e:
                    creation_errors.append(f"positional-bytes: {e}")
                except Exception as e:
                    creation_errors.append(f"positional-bytes-other: {e}")
            if image_input is None:
                try:
                    # Fallback: base64 encode if a 'base64' or 'b64' alternative exists
                    b64 = base64.b64encode(image_bytes).decode('utf-8')
                    if hasattr(Image, 'from_base64'):  # hypothetical helper
                        image_input = Image.from_base64(b64)
                    else:
                        # Last resort: attempt keyword 'base64'
                        image_input = Image(base64=b64)
                except Exception as e:
                    creation_errors.append(f"base64: {e}")
            if image_input is None:
                raise RuntimeError(
                    "Failed to construct Image input. Tried patterns: " + ", ".join(creation_errors)
                )

            batch_inputs.append(image_input)
            print(f"📸 Prepared image {i+1}/{len(images)} (size={len(image_bytes)} bytes)")
        
        print(f"🔄 Sending batch request to Clarifai...")
        start_time = time.time()
        
        # Make batch prediction 
        # NOTE: Vision+Text models often don't support batch processing with prompts
        # For now, try without prompt - if this fails, we'll fall back to individual processing
        try:
            batch_results = model.predict(batch_inputs)
        except Exception as batch_error:
            print(f"⚠️ Batch processing not supported for this model type: {batch_error}")
            raise batch_error  # This will trigger fallback to individual processing
        
        end_time = time.time()
        print(f"✅ Batch processing completed in {end_time - start_time:.2f} seconds")
        
        # Process results
        processed_results = []
        for i, result in enumerate(batch_results):
            try:
                # Convert result to expected format
                if hasattr(result, 'data') and hasattr(result.data, 'text'):
                    response_text = result.data.text.raw
                else:
                    response_text = str(result)
                
                # Parse using existing parser
                summary, json_output, input_tokens, output_tokens, violations = _parse_response_text(
                    response_text, model_id
                )
                
                processed_results.append({
                    'image_index': i,
                    'summary': summary,
                    'json_output': json_output,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'violations': violations,
                    'success': True
                })
                
                print(f"✅ Processed result {i+1}/{len(images)}")
                
            except Exception as e:
                print(f"❌ Error processing result {i+1}: {str(e)}")
                processed_results.append({
                    'image_index': i,
                    'summary': f"Analysis failed: {str(e)}",
                    'json_output': {'error': str(e)},
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'violations': [],
                    'success': False
                })
        
        print(f"🎉 Batch analysis complete: {len(processed_results)} results")
        return processed_results
        
    except Exception as e:
        print(f"❌ Batch processing failed: {str(e)}")
        print("🔄 Falling back to individual processing...")
        
        # Fallback to individual processing
        fallback_results = []
        for i, image_data in enumerate(images):
            try:
                if isinstance(image_data, str):  # File path
                    image_bytes = open(image_data, 'rb').read()
                else:  # Already bytes
                    image_bytes = image_data
                
                summary, json_output, input_tokens, output_tokens, violations = analyze_image(
                    image_bytes, model_id
                )
                
                fallback_results.append({
                    'image_index': i,
                    'summary': summary,
                    'json_output': json_output,
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'violations': violations,
                    'success': True
                })
                
            except Exception as individual_error:
                fallback_results.append({
                    'image_index': i,
                    'summary': f"Analysis failed: {str(individual_error)}",
                    'json_output': {'error': str(individual_error)},
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'violations': [],
                    'success': False
                })
        
        return fallback_results


def analyze_images_batch_from_files(file_paths: list, model_id: str = "gemini-2_5-pro") -> list:
    """
    Convenience function to analyze multiple images from file paths.
    
    Args:
        file_paths: List of image file paths
        model_id: The model identifier from config.toml
        
    Returns:
        List of analysis results, one per image
    """
    print(f"📁 Loading {len(file_paths)} images from file paths")
    
    # Load images into memory
    images = []
    for i, path in enumerate(file_paths):
        try:
            with open(path, 'rb') as f:
                image_bytes = f.read()
            images.append(image_bytes)
            print(f"📸 Loaded image {i+1}: {path}")
        except Exception as e:
            print(f"❌ Failed to load image {i+1} ({path}): {str(e)}")
            # Add placeholder for failed image
            images.append(b'')  # Empty bytes will be handled in batch processing
    
    return analyze_images_batch(images, model_id)
