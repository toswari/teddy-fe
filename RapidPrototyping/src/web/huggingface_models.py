"""
Hugging Face Model Discovery

Query Hugging Face Hub for trending and popular open-source models
to recommend during the solution design process.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ModelTask(Enum):
    """Hugging Face model task types."""
    # Text
    TEXT_GENERATION = "text-generation"
    TEXT2TEXT_GENERATION = "text2text-generation"
    TEXT_CLASSIFICATION = "text-classification"
    TOKEN_CLASSIFICATION = "token-classification"
    QUESTION_ANSWERING = "question-answering"
    SUMMARIZATION = "summarization"
    TRANSLATION = "translation"
    FILL_MASK = "fill-mask"
    FEATURE_EXTRACTION = "feature-extraction"
    
    # Vision
    IMAGE_CLASSIFICATION = "image-classification"
    OBJECT_DETECTION = "object-detection"
    IMAGE_SEGMENTATION = "image-segmentation"
    IMAGE_TO_TEXT = "image-to-text"
    TEXT_TO_IMAGE = "text-to-image"
    ZERO_SHOT_IMAGE_CLASSIFICATION = "zero-shot-image-classification"
    
    # Multi-modal
    VISUAL_QUESTION_ANSWERING = "visual-question-answering"
    IMAGE_TEXT_TO_TEXT = "image-text-to-text"
    
    # Audio
    AUTOMATIC_SPEECH_RECOGNITION = "automatic-speech-recognition"
    TEXT_TO_SPEECH = "text-to-speech"
    AUDIO_CLASSIFICATION = "audio-classification"
    
    # Other
    SENTENCE_SIMILARITY = "sentence-similarity"
    ZERO_SHOT_CLASSIFICATION = "zero-shot-classification"


@dataclass
class HuggingFaceModel:
    """Represents a Hugging Face model."""
    model_id: str
    task: str
    downloads: int
    likes: int
    parameters: Optional[str]  # e.g., "7B", "13B", "70B"
    license: Optional[str]
    tags: List[str]
    recommended_gpu: Optional[str] = None
    
    @property
    def clarifai_url(self) -> str:
        """Generate potential Clarifai URL for this model."""
        # Many HF models are available on Clarifai
        return f"https://clarifai.com/explore/models?query={self.model_id.split('/')[-1]}"


# Curated list of popular models by category with their specs
# This serves as a fallback and quick reference when API is unavailable
CURATED_MODELS = {
    ModelTask.TEXT_GENERATION: [
        HuggingFaceModel(
            model_id="meta-llama/Llama-3.1-8B-Instruct",
            task="text-generation",
            downloads=5000000,
            likes=15000,
            parameters="8B",
            license="llama3.1",
            tags=["llama", "meta", "instruct"],
            recommended_gpu="Entry (16GB) or Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="meta-llama/Llama-3.1-70B-Instruct",
            task="text-generation",
            downloads=3000000,
            likes=12000,
            parameters="70B",
            license="llama3.1",
            tags=["llama", "meta", "instruct"],
            recommended_gpu="Enterprise (80GB) or Multi-GPU"
        ),
        HuggingFaceModel(
            model_id="mistralai/Mistral-7B-Instruct-v0.3",
            task="text-generation",
            downloads=4000000,
            likes=10000,
            parameters="7B",
            license="apache-2.0",
            tags=["mistral", "instruct"],
            recommended_gpu="Entry (16GB) or Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="mistralai/Mixtral-8x7B-Instruct-v0.1",
            task="text-generation",
            downloads=2000000,
            likes=8000,
            parameters="47B (MoE)",
            license="apache-2.0",
            tags=["mixtral", "moe", "instruct"],
            recommended_gpu="Performance (48GB) or Enterprise (80GB)"
        ),
        HuggingFaceModel(
            model_id="Qwen/Qwen2.5-7B-Instruct",
            task="text-generation",
            downloads=1500000,
            likes=5000,
            parameters="7B",
            license="apache-2.0",
            tags=["qwen", "instruct"],
            recommended_gpu="Entry (16GB) or Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="Qwen/Qwen2.5-72B-Instruct",
            task="text-generation",
            downloads=800000,
            likes=4000,
            parameters="72B",
            license="apache-2.0",
            tags=["qwen", "instruct"],
            recommended_gpu="Enterprise (80GB) or Multi-GPU"
        ),
        HuggingFaceModel(
            model_id="google/gemma-2-9b-it",
            task="text-generation",
            downloads=1200000,
            likes=6000,
            parameters="9B",
            license="gemma",
            tags=["gemma", "google", "instruct"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="microsoft/Phi-3-mini-4k-instruct",
            task="text-generation",
            downloads=2000000,
            likes=7000,
            parameters="3.8B",
            license="mit",
            tags=["phi", "microsoft", "small"],
            recommended_gpu="Entry (16GB)"
        ),
    ],
    ModelTask.IMAGE_TEXT_TO_TEXT: [
        HuggingFaceModel(
            model_id="clarifai/mm-poly-8b",
            task="image-text-to-text",
            downloads=0,  # Clarifai model
            likes=0,
            parameters="8B",
            license="clarifai",
            tags=["clarifai", "multimodal", "vision-language", "vlm", "recommended"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="llava-hf/llava-1.5-7b-hf",
            task="image-text-to-text",
            downloads=800000,
            likes=3000,
            parameters="7B",
            license="llama2",
            tags=["llava", "vision-language", "vlm"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="llava-hf/llava-v1.6-mistral-7b-hf",
            task="image-text-to-text",
            downloads=600000,
            likes=2500,
            parameters="7B",
            license="apache-2.0",
            tags=["llava", "mistral", "vlm"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="Qwen/Qwen2-VL-7B-Instruct",
            task="image-text-to-text",
            downloads=500000,
            likes=2000,
            parameters="7B",
            license="apache-2.0",
            tags=["qwen", "vision-language", "vlm"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="microsoft/Phi-3-vision-128k-instruct",
            task="image-text-to-text",
            downloads=400000,
            likes=1800,
            parameters="4.2B",
            license="mit",
            tags=["phi", "microsoft", "vision"],
            recommended_gpu="Entry (16GB)"
        ),
        HuggingFaceModel(
            model_id="meta-llama/Llama-3.2-11B-Vision-Instruct",
            task="image-text-to-text",
            downloads=700000,
            likes=3500,
            parameters="11B",
            license="llama3.2",
            tags=["llama", "meta", "vision"],
            recommended_gpu="Standard (24GB) or Performance (48GB)"
        ),
    ],
    ModelTask.OBJECT_DETECTION: [
        HuggingFaceModel(
            model_id="facebook/detr-resnet-50",
            task="object-detection",
            downloads=500000,
            likes=2000,
            parameters="41M",
            license="apache-2.0",
            tags=["detr", "transformer", "detection"],
            recommended_gpu="Entry (16GB)"
        ),
        HuggingFaceModel(
            model_id="hustvl/yolos-tiny",
            task="object-detection",
            downloads=300000,
            likes=1500,
            parameters="6M",
            license="apache-2.0",
            tags=["yolos", "tiny", "fast"],
            recommended_gpu="Entry (16GB) or CPU"
        ),
        HuggingFaceModel(
            model_id="facebook/detr-resnet-101",
            task="object-detection",
            downloads=200000,
            likes=1000,
            parameters="60M",
            license="apache-2.0",
            tags=["detr", "resnet101"],
            recommended_gpu="Entry (16GB)"
        ),
    ],
    ModelTask.IMAGE_SEGMENTATION: [
        HuggingFaceModel(
            model_id="facebook/sam-vit-huge",
            task="image-segmentation",
            downloads=600000,
            likes=4000,
            parameters="636M",
            license="apache-2.0",
            tags=["sam", "segment-anything", "meta"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="facebook/sam-vit-base",
            task="image-segmentation",
            downloads=400000,
            likes=2500,
            parameters="91M",
            license="apache-2.0",
            tags=["sam", "segment-anything", "base"],
            recommended_gpu="Entry (16GB)"
        ),
        HuggingFaceModel(
            model_id="nvidia/segformer-b0-finetuned-ade-512-512",
            task="image-segmentation",
            downloads=200000,
            likes=1000,
            parameters="3.7M",
            license="other",
            tags=["segformer", "nvidia", "semantic"],
            recommended_gpu="Entry (16GB) or CPU"
        ),
    ],
    ModelTask.FEATURE_EXTRACTION: [
        HuggingFaceModel(
            model_id="sentence-transformers/all-MiniLM-L6-v2",
            task="feature-extraction",
            downloads=10000000,
            likes=5000,
            parameters="22M",
            license="apache-2.0",
            tags=["sentence-transformers", "embeddings", "fast"],
            recommended_gpu="Entry (16GB) or CPU"
        ),
        HuggingFaceModel(
            model_id="BAAI/bge-large-en-v1.5",
            task="feature-extraction",
            downloads=5000000,
            likes=3000,
            parameters="335M",
            license="mit",
            tags=["bge", "embeddings", "rag"],
            recommended_gpu="Entry (16GB)"
        ),
        HuggingFaceModel(
            model_id="intfloat/e5-large-v2",
            task="feature-extraction",
            downloads=3000000,
            likes=2000,
            parameters="335M",
            license="mit",
            tags=["e5", "embeddings"],
            recommended_gpu="Entry (16GB)"
        ),
        HuggingFaceModel(
            model_id="Alibaba-NLP/gte-large-en-v1.5",
            task="feature-extraction",
            downloads=1500000,
            likes=1500,
            parameters="434M",
            license="apache-2.0",
            tags=["gte", "embeddings", "alibaba"],
            recommended_gpu="Entry (16GB)"
        ),
    ],
    ModelTask.AUTOMATIC_SPEECH_RECOGNITION: [
        HuggingFaceModel(
            model_id="openai/whisper-large-v3",
            task="automatic-speech-recognition",
            downloads=3000000,
            likes=5000,
            parameters="1.5B",
            license="apache-2.0",
            tags=["whisper", "openai", "speech"],
            recommended_gpu="Entry (16GB)"
        ),
        HuggingFaceModel(
            model_id="openai/whisper-medium",
            task="automatic-speech-recognition",
            downloads=2000000,
            likes=3000,
            parameters="769M",
            license="apache-2.0",
            tags=["whisper", "openai", "medium"],
            recommended_gpu="Entry (16GB) or CPU"
        ),
    ],
    ModelTask.TEXT_TO_IMAGE: [
        HuggingFaceModel(
            model_id="stabilityai/stable-diffusion-xl-base-1.0",
            task="text-to-image",
            downloads=5000000,
            likes=10000,
            parameters="3.5B",
            license="openrail++",
            tags=["sdxl", "stable-diffusion", "image-gen"],
            recommended_gpu="Standard (24GB)"
        ),
        HuggingFaceModel(
            model_id="black-forest-labs/FLUX.1-schnell",
            task="text-to-image",
            downloads=2000000,
            likes=8000,
            parameters="12B",
            license="apache-2.0",
            tags=["flux", "fast", "image-gen"],
            recommended_gpu="Performance (48GB)"
        ),
    ],
}


# Map use case descriptions to model tasks
USE_CASE_TO_TASKS = {
    "visual understanding": [ModelTask.IMAGE_TEXT_TO_TEXT, ModelTask.VISUAL_QUESTION_ANSWERING],
    "image analysis": [ModelTask.IMAGE_TEXT_TO_TEXT, ModelTask.IMAGE_CLASSIFICATION],
    "document analysis": [ModelTask.IMAGE_TEXT_TO_TEXT, ModelTask.TEXT_GENERATION],
    "ocr": [ModelTask.IMAGE_TO_TEXT],
    "text generation": [ModelTask.TEXT_GENERATION],
    "chatbot": [ModelTask.TEXT_GENERATION],
    "summarization": [ModelTask.SUMMARIZATION, ModelTask.TEXT_GENERATION],
    "translation": [ModelTask.TRANSLATION, ModelTask.TEXT_GENERATION],
    "object detection": [ModelTask.OBJECT_DETECTION],
    "segmentation": [ModelTask.IMAGE_SEGMENTATION],
    "embeddings": [ModelTask.FEATURE_EXTRACTION],
    "rag": [ModelTask.FEATURE_EXTRACTION, ModelTask.TEXT_GENERATION],
    "search": [ModelTask.FEATURE_EXTRACTION],
    "speech to text": [ModelTask.AUTOMATIC_SPEECH_RECOGNITION],
    "transcription": [ModelTask.AUTOMATIC_SPEECH_RECOGNITION],
    "image generation": [ModelTask.TEXT_TO_IMAGE],
    "vlm": [ModelTask.IMAGE_TEXT_TO_TEXT],
    "vision language": [ModelTask.IMAGE_TEXT_TO_TEXT],
    "multimodal": [ModelTask.IMAGE_TEXT_TO_TEXT, ModelTask.VISUAL_QUESTION_ANSWERING],
    "classification": [ModelTask.IMAGE_CLASSIFICATION, ModelTask.TEXT_CLASSIFICATION],
    "question answering": [ModelTask.QUESTION_ANSWERING, ModelTask.TEXT_GENERATION],
}


def get_model_size_category(parameters: Optional[str]) -> str:
    """Determine model size category from parameter string."""
    if not parameters:
        return "unknown"
    
    params_lower = parameters.lower()
    
    # Extract number
    import re
    match = re.search(r'(\d+\.?\d*)', params_lower)
    if not match:
        return "small"
    
    num = float(match.group(1))
    
    if 'b' in params_lower:
        if num < 3:
            return "1-3B"
        elif num < 10:
            return "7-8B"
        elif num < 20:
            return "13-14B"
        elif num < 50:
            return "30-34B"
        elif num < 80:
            return "70B"
        else:
            return "100B+"
    elif 'm' in params_lower:
        return "small (<1B)"
    
    return "unknown"


def recommend_gpu_for_model(parameters: Optional[str]) -> str:
    """Recommend GPU tier based on model parameters."""
    size = get_model_size_category(parameters)
    
    gpu_recommendations = {
        "small (<1B)": "Entry (16GB) or CPU",
        "1-3B": "Entry (16GB)",
        "7-8B": "Entry (16GB) or Standard (24GB)",
        "13-14B": "Standard (24GB) or Performance (48GB)",
        "30-34B": "Performance (48GB) or Enterprise (80GB)",
        "70B": "Enterprise (80GB) or Multi-GPU",
        "100B+": "Multi-GPU (2-8x H100)",
        "unknown": "Standard (24GB) - verify requirements",
    }
    
    return gpu_recommendations.get(size, "Standard (24GB)")


def get_models_for_use_case(use_case: str, max_results: int = 5) -> List[HuggingFaceModel]:
    """
    Get recommended models for a specific use case.
    
    Args:
        use_case: Description of the use case (e.g., "visual understanding", "chatbot")
        max_results: Maximum number of models to return
        
    Returns:
        List of recommended HuggingFaceModel objects
    """
    use_case_lower = use_case.lower()
    
    # Find matching tasks
    matching_tasks = []
    for keyword, tasks in USE_CASE_TO_TASKS.items():
        if keyword in use_case_lower:
            matching_tasks.extend(tasks)
    
    # Default to VLM if no match and seems visual
    if not matching_tasks:
        if any(word in use_case_lower for word in ["image", "visual", "picture", "photo", "video"]):
            matching_tasks = [ModelTask.IMAGE_TEXT_TO_TEXT]
        else:
            matching_tasks = [ModelTask.TEXT_GENERATION]
    
    # Collect models from matching tasks
    models = []
    seen_ids = set()
    
    for task in matching_tasks:
        if task in CURATED_MODELS:
            for model in CURATED_MODELS[task]:
                if model.model_id not in seen_ids:
                    models.append(model)
                    seen_ids.add(model.model_id)
    
    # Sort: Clarifai models first, then by downloads (popularity)
    def sort_key(m):
        is_clarifai = 1 if "clarifai" in m.model_id.lower() or "clarifai" in m.tags else 0
        return (-is_clarifai, -m.downloads)  # Negative for descending
    
    models.sort(key=sort_key)
    
    return models[:max_results]


def get_models_by_task(task: ModelTask, max_results: int = 5) -> List[HuggingFaceModel]:
    """Get models for a specific task type."""
    if task in CURATED_MODELS:
        return CURATED_MODELS[task][:max_results]
    return []


def get_all_vlm_models() -> List[HuggingFaceModel]:
    """Get all vision-language models."""
    return CURATED_MODELS.get(ModelTask.IMAGE_TEXT_TO_TEXT, [])


def get_all_llm_models() -> List[HuggingFaceModel]:
    """Get all text generation LLM models."""
    return CURATED_MODELS.get(ModelTask.TEXT_GENERATION, [])


def get_embedding_models() -> List[HuggingFaceModel]:
    """Get embedding models for RAG/search."""
    return CURATED_MODELS.get(ModelTask.FEATURE_EXTRACTION, [])


def format_model_recommendations(models: List[HuggingFaceModel], title: str = "Recommended Open-Source Models") -> str:
    """Format model recommendations as markdown."""
    if not models:
        return ""
    
    lines = [
        f"\n### {title}\n",
        "| Model | Parameters | License | GPU Requirement | Link |",
        "|-------|------------|---------|-----------------|------|",
    ]
    
    for model in models:
        is_clarifai = "clarifai" in model.model_id.lower() or "clarifai" in model.tags
        
        if is_clarifai:
            # Clarifai models link to Clarifai platform
            link = f"[{model.model_id.split('/')[-1]}](https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b) ⭐"
            model_name = f"**{model.model_id.split('/')[-1]}** *(Clarifai)*"
        else:
            link = f"[{model.model_id.split('/')[-1]}](https://huggingface.co/{model.model_id})"
            model_name = model.model_id.split('/')[-1]
        
        gpu_req = model.recommended_gpu or recommend_gpu_for_model(model.parameters)
        lines.append(f"| {model_name} | {model.parameters or 'N/A'} | {model.license or 'N/A'} | {gpu_req} | {link} |")
    
    lines.append("")
    lines.append("*⭐ = Recommended Clarifai model, ready to use. Check all models at [clarifai.com/explore](https://clarifai.com/explore)*")
    
    return "\n".join(lines)


def get_model_recommendations_for_project(goals: List[str], industry: str) -> Dict[str, Any]:
    """
    Generate model recommendations based on project goals and industry.
    
    Returns structured recommendations with models and GPU requirements.
    """
    recommendations = {
        "primary_models": [],
        "embedding_models": [],
        "alternative_models": [],
        "gpu_summary": {},
    }
    
    # Analyze goals to determine model needs
    goals_text = " ".join(goals).lower()
    
    # Get primary models based on goals
    primary_models = get_models_for_use_case(goals_text, max_results=3)
    recommendations["primary_models"] = primary_models
    
    # Always recommend embedding models for RAG capability
    recommendations["embedding_models"] = get_embedding_models()[:2]
    
    # Get alternatives (different model families)
    all_vlms = get_all_vlm_models()
    all_llms = get_all_llm_models()
    
    # Filter out already recommended
    primary_ids = {m.model_id for m in primary_models}
    alternatives = [m for m in (all_vlms + all_llms) if m.model_id not in primary_ids][:3]
    recommendations["alternative_models"] = alternatives
    
    # Summarize GPU requirements
    all_models = primary_models + recommendations["embedding_models"] + alternatives
    gpu_tiers = {}
    for model in all_models:
        gpu = model.recommended_gpu or recommend_gpu_for_model(model.parameters)
        if gpu not in gpu_tiers:
            gpu_tiers[gpu] = []
        gpu_tiers[gpu].append(model.model_id.split("/")[-1])
    
    recommendations["gpu_summary"] = gpu_tiers
    
    return recommendations


def generate_model_section_for_proposal(goals: List[str], industry: str) -> str:
    """Generate the model recommendations section for a proposal."""
    recs = get_model_recommendations_for_project(goals, industry)
    
    sections = []
    
    # Primary recommendations
    if recs["primary_models"]:
        sections.append(format_model_recommendations(
            recs["primary_models"], 
            "Recommended Primary Models (Based on Your Use Case)"
        ))
    
    # Embedding models for RAG
    if recs["embedding_models"]:
        sections.append(format_model_recommendations(
            recs["embedding_models"],
            "Embedding Models (For RAG/Search)"
        ))
    
    # Alternative options
    if recs["alternative_models"]:
        sections.append(format_model_recommendations(
            recs["alternative_models"],
            "Alternative Model Options"
        ))
    
    # GPU summary
    if recs["gpu_summary"]:
        sections.append("\n### GPU Requirements Summary\n")
        sections.append("Based on the recommended models:\n")
        for gpu_tier, models in recs["gpu_summary"].items():
            sections.append(f"- **{gpu_tier}**: {', '.join(models)}")
    
    return "\n".join(sections)
