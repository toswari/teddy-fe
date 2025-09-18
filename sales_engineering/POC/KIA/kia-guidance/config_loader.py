"""
Configuration loader for the AI Brand Compliance Chatbot.
Reads and parses the config.toml file.
"""
import toml
import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.toml file.
    
    Returns:
        Dict containing all configuration settings
    """
    config_path = os.path.join(os.path.dirname(__file__), 'config.toml')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = toml.load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    except toml.TomlDecodeError as e:
        raise ValueError(f"Invalid TOML configuration: {e}")

def get_available_models() -> Dict[str, str]:
    """
    Get available models from configuration.
    
    Returns:
        Dict mapping model_id to user-friendly model_name
    """
    config = load_config()
    models = {}
    
    if 'prompts' in config:
        for model_id, model_config in config['prompts'].items():
            if 'model_name' in model_config:
                models[model_id] = model_config['model_name']
    
    return models

def get_model_config(model_id: str) -> Dict[str, str]:
    """
    Get configuration for a specific model.
    
    Args:
        model_id: The model identifier
        
    Returns:
        Dict containing model configuration
    """
    config = load_config()
    
    if 'prompts' not in config or model_id not in config['prompts']:
        raise ValueError(f"Model '{model_id}' not found in configuration")
    
    model_config = config['prompts'][model_id].copy()
    
    return model_config

def get_clarifai_config() -> Dict[str, str]:
    """
    Get Clarifai-specific configuration.
    
    Returns:
        Dict containing Clarifai settings
    """
    config = load_config()
    
    if 'clarifai' not in config:
        raise ValueError("Clarifai configuration not found")
    
    return config['clarifai']

if __name__ == "__main__":
    # Test the configuration loader
    try:
        config = load_config()
        print("✓ Configuration loaded successfully")
        
        models = get_available_models()
        print(f"✓ Available models: {list(models.keys())}")
        
        clarifai_config = get_clarifai_config()
        print(f"✓ Clarifai config loaded: {clarifai_config}")
        
    except Exception as e:
        print(f"✗ Configuration error: {e}")
