"""
Configuration management for the Rapid Prototyping Framework.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ModelConfig(BaseModel):
    """Configuration for a single model."""
    name: str
    url: str
    version: str
    full_model_path: str
    temperature: float = 0.7
    max_tokens: int = 4096
    use_for: list[str] = Field(default_factory=list)


class APIConfig(BaseModel):
    """API configuration."""
    base_url: str = "https://api.clarifai.com/v2/ext/openai/v1"
    timeout: int = 120
    max_retries: int = 3


class AgentConfig(BaseModel):
    """Configuration for an agent."""
    system_prompt_file: str
    output_format: str = "markdown"
    include_sections: list[str] = Field(default_factory=list)
    question_categories: list[str] = Field(default_factory=list)
    architecture_components: list[str] = Field(default_factory=list)


class OutputConfig(BaseModel):
    """Output configuration."""
    format: str = "markdown"
    include_metadata: bool = True
    timestamp_outputs: bool = True
    create_subfolders: bool = True


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    clarifai_api_key: str = Field(default="", env="CLARIFAI_API_KEY")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    output_dir: str = Field(default="projects", env="OUTPUT_DIR")
    config_dir: str = Field(default="config", env="CONFIG_DIR")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class ConfigManager:
    """Manages configuration loading and access."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.settings = Settings()
        self.config_path = Path(config_path or self.settings.config_dir)
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        models_config = self.config_path / "models.yaml"
        if models_config.exists():
            with open(models_config, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        else:
            self._config = self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "api": {
                "base_url": "https://api.clarifai.com/v2/ext/openai/v1",
                "timeout": 120,
                "max_retries": 3
            },
            "models": {
                "primary_llm": {
                    "name": "GPT-OSS-120B",
                    "url": "https://clarifai.com/openai/chat-completion/models/gpt-oss-120b",
                    "version": "1d3ee440e48c4e7a94af6acac7d7cdfc",
                    "full_model_path": "https://clarifai.com/openai/chat-completion/models/gpt-oss-120b/versions/1d3ee440e48c4e7a94af6acac7d7cdfc",
                    "temperature": 0.7,
                    "max_tokens": 4096
                },
                "multimodal": {
                    "name": "MM-Poly-8B",
                    "url": "https://clarifai.com/clarifai/main/models/mm-poly-8b",
                    "version": "c9d0ddac75fa4ec8af25502c4384383a",
                    "full_model_path": "https://clarifai.com/clarifai/main/models/mm-poly-8b/versions/c9d0ddac75fa4ec8af25502c4384383a",
                    "temperature": 0.7,
                    "max_tokens": 2048
                }
            }
        }
    
    @property
    def api_config(self) -> APIConfig:
        """Get API configuration."""
        return APIConfig(**self._config.get("api", {}))
    
    @property
    def primary_llm(self) -> ModelConfig:
        """Get primary LLM configuration."""
        return ModelConfig(**self._config["models"]["primary_llm"])
    
    @property
    def multimodal_model(self) -> ModelConfig:
        """Get multimodal model configuration."""
        return ModelConfig(**self._config["models"]["multimodal"])
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent."""
        agents = self._config.get("agents", {})
        if agent_name in agents:
            return AgentConfig(**agents[agent_name])
        return None
    
    def get_system_prompt(self, prompt_file: str) -> str:
        """Load a system prompt from file."""
        prompt_path = self.config_path / prompt_file
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
        return ""
    
    @property
    def output_config(self) -> OutputConfig:
        """Get output configuration."""
        return OutputConfig(**self._config.get("output", {}))


# Global configuration instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def init_config(config_path: Optional[str] = None) -> ConfigManager:
    """Initialize configuration with optional custom path."""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager
