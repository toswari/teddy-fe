#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Warmup script to verify model is responding before starting load tests.
"""

import os
import sys
import time

from clarifai.client import Model


def warmup_model():
    """Make a single call to verify the model is responding."""
    model_url = os.environ.get('CLARIFAI_MODEL_URL')
    api_base = os.environ.get('CLARIFAI_API_BASE')

    if not model_url:
        print("ERROR: CLARIFAI_MODEL_URL not set")
        return False

    print(f"Warming up model: {model_url}")
    if api_base:
        print(f"API Base: {api_base}")
    print(f"Making initial test call to verify model is responding...")
 
    try:
        # Initialize model with base_url if specified
        model_kwargs = {
            "url": model_url,
            "deployment_id": os.environ.get("CLARIFAI_DEPLOYMENT_ID"),
            "deployment_user_id": os.environ.get("CLARIFAI_DEPLOYMENT_USER_ID"),
        }

        if api_base:
            model_kwargs["base_url"] = api_base

        model = Model(**model_kwargs)

        # Make a simple prediction
        start_time = time.time()
        result = model.predict(
            prompt="Test",
        )
        duration = time.time() - start_time

        print(f"✓ Model responded successfully in {duration:.2f} seconds")
        print(f"✓ Response preview: {str(result)[:100]}...")
        return True

    except Exception as e:
        print(f"✗ Model warmup failed: {e}")
        print(f"✗ Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = warmup_model()
    sys.exit(0 if success else 1)
