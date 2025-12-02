"""
Get model configuration from models.yaml
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
import yaml
from pathlib import Path


@dataclass
class ModelConfig:
    """Configuration for a model to track"""

    model_slug: str
    display_name: str
    slack_channel: Optional[str] = None


def load_models() -> List[Dict]:
    """Load models from models.yaml"""
    config_file = Path(__file__).parent / "models.yaml"

    if not config_file.exists():
        raise FileNotFoundError(f"models.yaml not found at {config_file}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    return config.get("models", [])


def get_model_by_slug(slug: str) -> Optional[Dict]:
    """Get model config by slug"""
    models = load_models()
    for model in models:
        if model["slug"] == slug:
            return model
    return None


def get_all_model_slugs() -> List[str]:
    """Get all model slugs"""
    models = load_models()
    return [model["slug"] for model in models]


def get_model_config(model_slug: str) -> ModelConfig:
    """Get config for a model from models.yaml, or create default."""
    model_data = get_model_by_slug(model_slug)

    if model_data:
        return ModelConfig(
            model_slug=model_slug,
            display_name=model_data.get("display_name", model_slug),
            slack_channel=model_data.get(
                "channel", f"#{model_slug.split('/')[0]}-stats"
            ),
        )

    # Generate default config for unknown models
    org, name = model_slug.split("/") if "/" in model_slug else (model_slug, model_slug)
    return ModelConfig(
        model_slug=model_slug,
        display_name=name.replace("-", " ").title(),
        slack_channel=f"#{org.lower()}-stats",
    )
