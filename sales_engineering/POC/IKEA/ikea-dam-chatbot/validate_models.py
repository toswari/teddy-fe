#!/usr/bin/env python3
"""
IKEA DAM Chatbot Model Validation Script

This script tests each multimodal model defined in the chatbot to ensure they work properly.
It validates:
1. Model accessibility via Clarifai API
2. Response generation with test images
3. Response quality and format
4. Error handling

Usage:
    python validate_models.py

Requirements:
    - CLARIFAI_PAT environment variable or .streamlit/secrets.toml
    - clarifai>=11.6.0
    - toml>=0.10.2
"""

import os
import sys
import time
import traceback
from datetime import datetime

try:
    from clarifai.client.model import Model
    from clarifai.client.input import Inputs
except ImportError:
    print("❌ Error: clarifai package not found. Please install with: pip install clarifai>=11.6.0")
    sys.exit(1)

try:
    import toml
except ImportError:
    print("❌ Error: toml package not found. Please install with: pip install toml>=0.10.2")
    sys.exit(1)

# Available multimodal models from the chatbot - Updated with working URLs
MULTIMODAL_MODELS = {
    "MiniCPM-o-2.6 (Recommended)": "https://clarifai.com/openbmb/miniCPM/models/MiniCPM-o-2_6-language",
    "GPT-4o": "https://clarifai.com/openai/chat-completion/models/gpt-4o",
    "GPT-4o Mini": "https://clarifai.com/openai/chat-completion/models/gpt-4o-mini",
    "Claude-3.5 Sonnet": "https://clarifai.com/anthropic/completion/models/claude-3_5-sonnet",
    "Gemini 1.5 Pro": "https://clarifai.com/gcp/generate/models/gemini-1_5-pro",
    "CogVLM-Chat": "https://clarifai.com/thudm/cogvlm/models/cogvlm-chat",
}

# Test images for validation
TEST_IMAGES = {
    "Living Room": "https://samples.clarifai.com/metro-north.jpg",
    "Outdoor Scene": "https://samples.clarifai.com/wedding.jpg",
    "Travel Image": "https://samples.clarifai.com/travel.jpg"
}

# Test prompts for IKEA DAM validation
TEST_PROMPTS = [
    "What room type do you see in this image?",
    "Describe the furniture and decor elements visible.",
    "What design style is represented here?",
    "What IKEA product categories would be relevant?"
]

def load_api_key():
    """Load Clarifai API key from secrets or environment"""
    # Try to load from Streamlit secrets first
    try:
        with open('.streamlit/secrets.toml', 'r') as f:
            secrets = toml.load(f)
            pat = secrets.get("clarifai", {}).get("PAT")
            if pat and pat != "your_clarifai_api_key_here" and not pat.startswith("CLARIFAI_PAT="):
                return pat
            elif pat and pat.startswith("CLARIFAI_PAT="):
                # Handle the case where PAT has the prefix
                return pat.replace("CLARIFAI_PAT=", "")
    except (FileNotFoundError, KeyError, toml.TomlDecodeError):
        pass
    
    # Fallback to environment variable
    pat = os.getenv('CLARIFAI_PAT')
    if pat:
        return pat
    
    return None

def test_model(model_name, model_url, pat, test_image_url, test_prompt):
    """Test a single model with a given image and prompt"""
    try:
        print(f"  📝 Testing with prompt: '{test_prompt[:50]}...'")
        
        # Create multimodal input
        multi_inputs = Inputs.get_multimodal_input(
            input_id="",
            image_url=test_image_url,
            raw_text=test_prompt
        )
        
        # Initialize model and make prediction
        start_time = time.time()
        model = Model(url=model_url, pat=pat)
        prediction = model.predict(inputs=[multi_inputs])
        response_time = time.time() - start_time
        
        # Check if we got a valid response
        if prediction.outputs and prediction.outputs[0].data.text:
            response = prediction.outputs[0].data.text.raw
            response_length = len(response)
            
            print(f"    ✅ Success! Response time: {response_time:.2f}s, Length: {response_length} chars")
            print(f"    📄 Response preview: {response[:100]}...")
            
            return {
                "success": True,
                "response_time": response_time,
                "response_length": response_length,
                "response_preview": response[:200],
                "error": None
            }
        else:
            print(f"    ❌ No valid response received")
            return {
                "success": False,
                "response_time": response_time,
                "response_length": 0,
                "response_preview": "",
                "error": "No valid response in prediction output"
            }
            
    except Exception as e:
        print(f"    ❌ Error: {str(e)}")
        return {
            "success": False,
            "response_time": 0,
            "response_length": 0,
            "response_preview": "",
            "error": str(e)
        }

def validate_all_models():
    """Validate all multimodal models"""
    print("🤖 IKEA DAM Chatbot Model Validation")
    print("=" * 50)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load API key
    pat = load_api_key()
    if not pat:
        print("❌ No Clarifai API key found!")
        print("Please set one of the following:")
        print("1. Edit .streamlit/secrets.toml and add your API key")
        print("2. Set CLARIFAI_PAT environment variable")
        print("3. Export CLARIFAI_PAT='your_key_here'")
        return False
    
    print(f"🔑 API key loaded successfully (length: {len(pat)} chars)")
    print()
    
    # Test results storage
    results = {}
    
    # Test each model
    for model_name, model_url in MULTIMODAL_MODELS.items():
        print(f"🧠 Testing model: {model_name}")
        print(f"🔗 URL: {model_url}")
        
        model_results = []
        
        # Test with different images and prompts
        for image_name, image_url in TEST_IMAGES.items():
            print(f"  🖼️ Testing with image: {image_name}")
            
            for i, prompt in enumerate(TEST_PROMPTS[:2]):  # Test first 2 prompts to save time
                result = test_model(model_name, model_url, pat, image_url, prompt)
                model_results.append(result)
                
                if not result["success"]:
                    print(f"    ⚠️ Skipping remaining tests for this image due to error")
                    break
                
                # Small delay between requests
                time.sleep(1)
        
        # Calculate model statistics
        successful_tests = [r for r in model_results if r["success"]]
        total_tests = len(model_results)
        success_rate = len(successful_tests) / total_tests if total_tests > 0 else 0
        
        if successful_tests:
            avg_response_time = sum(r["response_time"] for r in successful_tests) / len(successful_tests)
            avg_response_length = sum(r["response_length"] for r in successful_tests) / len(successful_tests)
        else:
            avg_response_time = 0
            avg_response_length = 0
        
        results[model_name] = {
            "success_rate": success_rate,
            "total_tests": total_tests,
            "successful_tests": len(successful_tests),
            "avg_response_time": avg_response_time,
            "avg_response_length": avg_response_length,
            "errors": [r["error"] for r in model_results if r["error"]]
        }
        
        # Print model summary
        print(f"  📊 Model Summary:")
        print(f"    Success Rate: {success_rate:.1%} ({len(successful_tests)}/{total_tests})")
        if successful_tests:
            print(f"    Avg Response Time: {avg_response_time:.2f}s")
            print(f"    Avg Response Length: {avg_response_length:.0f} chars")
        
        if results[model_name]["errors"]:
            print(f"    ⚠️ Errors encountered: {len(results[model_name]['errors'])}")
            for error in set(results[model_name]["errors"]):
                print(f"      - {error}")
        
        print()
    
    # Generate final report
    print("=" * 50)
    print("📋 FINAL VALIDATION REPORT")
    print("=" * 50)
    
    working_models = []
    problematic_models = []
    
    for model_name, stats in results.items():
        status = "✅ WORKING" if stats["success_rate"] >= 0.5 else "❌ ISSUES"
        print(f"{status} {model_name}")
        print(f"   Success Rate: {stats['success_rate']:.1%}")
        
        if stats["success_rate"] >= 0.5:
            working_models.append(model_name)
            if stats["avg_response_time"] > 0:
                print(f"   Avg Response Time: {stats['avg_response_time']:.2f}s")
                print(f"   Avg Response Length: {stats['avg_response_length']:.0f} chars")
        else:
            problematic_models.append(model_name)
            if stats["errors"]:
                print(f"   Main Errors: {', '.join(list(set(stats['errors']))[:2])}")
        print()
    
    # Summary
    print("📈 SUMMARY:")
    print(f"✅ Working models: {len(working_models)}/{len(MULTIMODAL_MODELS)}")
    print(f"❌ Problematic models: {len(problematic_models)}/{len(MULTIMODAL_MODELS)}")
    
    if working_models:
        print(f"\n🎉 Recommended models for production:")
        for model in working_models:
            print(f"   - {model}")
    
    if problematic_models:
        print(f"\n⚠️ Models needing attention:")
        for model in problematic_models:
            print(f"   - {model}")
            if results[model]["errors"]:
                print(f"     Issues: {', '.join(set(results[model]['errors'])[:2])}")
    
    print(f"\n📅 Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return len(working_models) > 0

if __name__ == "__main__":
    try:
        success = validate_all_models()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error during validation: {e}")
        print("Stack trace:")
        traceback.print_exc()
        sys.exit(1)
