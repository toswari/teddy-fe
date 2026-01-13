"""
Clarifai API Client Wrapper

Provides a unified interface for interacting with Clarifai's AI models,
supporting both text-based LLMs and multimodal models.
"""

import os
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

from openai import OpenAI

from src.config import get_config, ConfigManager


logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported model types."""
    TEXT = "text"
    MULTIMODAL = "multimodal"


@dataclass
class Message:
    """Chat message structure."""
    role: str  # "system", "user", or "assistant"
    content: Union[str, List[Dict[str, Any]]]


@dataclass
class ChatResponse:
    """Structured chat response."""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    raw_response: Any = None


class ClarifaiClient:
    """
    Client for interacting with Clarifai's text-based LLM models.
    Uses OpenAI-compatible API endpoint.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[ConfigManager] = None
    ):
        """
        Initialize the Clarifai client.
        
        Args:
            api_key: Clarifai API key (PAT). If not provided, uses CLARIFAI_API_KEY env var.
            config: Optional ConfigManager instance.
        """
        self.config = config or get_config()
        self.api_key = api_key or os.getenv("CLARIFAI_API_KEY", self.config.settings.clarifai_api_key)
        
        if not self.api_key:
            raise ValueError(
                "Clarifai API key is required. Set CLARIFAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(
            base_url=self.config.api_config.base_url,
            api_key=self.api_key,
        )
        
        self.model_config = self.config.primary_llm
        logger.info(f"Initialized ClarifaiClient with model: {self.model_config.name}")
    
    def chat(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Union[ChatResponse, Generator[str, None, None]]:
        """
        Send a chat completion request.
        
        Args:
            messages: List of Message objects for the conversation.
            temperature: Sampling temperature (0-2). Defaults to model config.
            max_tokens: Maximum tokens in response. Defaults to model config.
            stream: Whether to stream the response.
            
        Returns:
            ChatResponse object or generator if streaming.
        """
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        params = {
            "model": self.model_config.full_model_path,
            "messages": formatted_messages,
            "temperature": temperature or self.model_config.temperature,
            "max_tokens": max_tokens or self.model_config.max_tokens,
            "stream": stream,
        }
        
        logger.debug(f"Sending chat request with {len(messages)} messages")
        
        if stream:
            return self._stream_response(params)
        
        response = self.client.chat.completions.create(**params)
        
        return ChatResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            raw_response=response,
        )
    
    def _stream_response(self, params: Dict[str, Any]) -> Generator[str, None, None]:
        """Stream response chunks."""
        response = self.client.chat.completions.create(**params)
        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Simple completion interface.
        
        Args:
            prompt: User prompt.
            system_prompt: Optional system prompt.
            **kwargs: Additional arguments passed to chat().
            
        Returns:
            ChatResponse object.
        """
        messages = []
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))
        messages.append(Message(role="user", content=prompt))
        
        return self.chat(messages, **kwargs)
    
    def generate_with_context(
        self,
        prompt: str,
        context: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Generate response with additional context.
        
        Args:
            prompt: User prompt.
            context: Context information to include.
            system_prompt: Optional system prompt.
            **kwargs: Additional arguments passed to chat().
            
        Returns:
            ChatResponse object.
        """
        full_prompt = f"Context:\n{context}\n\n---\n\nRequest:\n{prompt}"
        return self.complete(full_prompt, system_prompt, **kwargs)


class MultimodalClient:
    """
    Client for interacting with Clarifai's multimodal models (MM-Poly-8B).
    Supports text, images, video, and audio inputs.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[ConfigManager] = None
    ):
        """
        Initialize the multimodal client.
        
        Args:
            api_key: Clarifai API key (PAT).
            config: Optional ConfigManager instance.
        """
        self.config = config or get_config()
        self.api_key = api_key or os.getenv("CLARIFAI_API_KEY", self.config.settings.clarifai_api_key)
        
        if not self.api_key:
            raise ValueError("Clarifai API key is required.")
        
        self.client = OpenAI(
            base_url=self.config.api_config.base_url,
            api_key=self.api_key,
        )
        
        self.model_config = self.config.multimodal_model
        logger.info(f"Initialized MultimodalClient with model: {self.model_config.name}")
    
    def analyze_image(
        self,
        image_source: str,
        prompt: str = "Describe this image in detail.",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """
        Analyze an image with the multimodal model.
        
        Args:
            image_source: URL or base64 encoded image data.
            prompt: Analysis prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            
        Returns:
            ChatResponse with analysis.
        """
        # Determine if URL or base64
        if image_source.startswith(('http://', 'https://')):
            image_content = {"type": "image_url", "image_url": {"url": image_source}}
        else:
            image_content = {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_source}"}
            }
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_content,
                ],
            }
        ]
        
        response = self.client.chat.completions.create(
            model=self.model_config.full_model_path,
            messages=messages,
            temperature=temperature or self.model_config.temperature,
            max_tokens=max_tokens or self.model_config.max_tokens,
        )
        
        return ChatResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            raw_response=response,
        )
    
    def analyze_image_file(
        self,
        image_path: Union[str, Path],
        prompt: str = "Describe this image in detail.",
        **kwargs
    ) -> ChatResponse:
        """
        Analyze an image from a local file.
        
        Args:
            image_path: Path to the image file.
            prompt: Analysis prompt.
            **kwargs: Additional arguments.
            
        Returns:
            ChatResponse with analysis.
        """
        import base64
        
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        with open(path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return self.analyze_image(image_data, prompt, **kwargs)
    
    def chat(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> ChatResponse:
        """
        Send a chat completion request to the multimodal model.
        
        Args:
            messages: List of Message objects.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.
            
        Returns:
            ChatResponse object.
        """
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        response = self.client.chat.completions.create(
            model=self.model_config.full_model_path,
            messages=formatted_messages,
            temperature=temperature or self.model_config.temperature,
            max_tokens=max_tokens or self.model_config.max_tokens,
        )
        
        return ChatResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
            raw_response=response,
        )


class ClarifaiSDKClient:
    """
    Alternative client using the native Clarifai SDK.
    Provides additional capabilities like video and audio processing.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Clarifai SDK."""
        try:
            from clarifai.client import Model
            from clarifai.runners.utils.data_types import Image, Video, Audio
            
            self.Model = Model
            self.Image = Image
            self.Video = Video
            self.Audio = Audio
            self._sdk_available = True
        except ImportError:
            logger.warning("Clarifai SDK not available. Install with: pip install clarifai")
            self._sdk_available = False
        
        self.api_key = api_key or os.getenv("CLARIFAI_API_KEY")
        if self.api_key:
            os.environ["CLARIFAI_PAT"] = self.api_key
        
        self.config = get_config()
    
    def analyze_video(
        self,
        video_source: str,
        prompt: str = "Describe in detail what is in the video.",
        max_tokens: int = 1024,
    ) -> str:
        """
        Analyze a video using the multimodal model.
        
        Args:
            video_source: URL to the video.
            prompt: Analysis prompt.
            max_tokens: Maximum response tokens.
            
        Returns:
            Analysis text.
        """
        if not self._sdk_available:
            raise RuntimeError("Clarifai SDK required for video analysis")
        
        model = self.Model(url=self.config.multimodal_model.url)
        video_obj = self.Video(url=video_source)
        
        result = model.predict(
            prompt=prompt,
            video=video_obj,
            max_tokens=max_tokens,
        )
        
        return str(result)
    
    def analyze_audio(
        self,
        audio_source: str,
        prompt: str = "Describe in detail what is in the audio.",
        max_tokens: int = 1024,
    ) -> str:
        """
        Analyze audio using the multimodal model.
        
        Args:
            audio_source: URL to the audio file.
            prompt: Analysis prompt.
            max_tokens: Maximum response tokens.
            
        Returns:
            Analysis text.
        """
        if not self._sdk_available:
            raise RuntimeError("Clarifai SDK required for audio analysis")
        
        model = self.Model(url=self.config.multimodal_model.url)
        audio_obj = self.Audio(url=audio_source)
        
        result = model.predict(
            prompt=prompt,
            audio=audio_obj,
            max_tokens=max_tokens,
        )
        
        return str(result)
