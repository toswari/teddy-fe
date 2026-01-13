"""
Base Agent class for all specialized agents.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.clients.clarifai_client import ClarifaiClient, MultimodalClient, Message, ChatResponse
from src.config import get_config, ConfigManager


logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Context information for agent operations."""
    customer_name: Optional[str] = None
    project_name: Optional[str] = None
    industry: Optional[str] = None
    documents: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Message] = field(default_factory=list)


@dataclass
class AgentOutput:
    """Structured output from an agent."""
    content: str
    agent_type: str
    timestamp: datetime
    context: AgentContext
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def save(self, output_dir: str) -> Path:
        """Save output to a file."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = self.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{self.agent_type}_{timestamp_str}.md"
        filepath = output_path / filename
        
        # Add metadata header
        header = f"""---
agent: {self.agent_type}
timestamp: {self.timestamp.isoformat()}
customer: {self.context.customer_name or 'Unknown'}
project: {self.context.project_name or 'Unknown'}
industry: {self.context.industry or 'Unknown'}
---

"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(header + self.content)
        
        logger.info(f"Saved output to {filepath}")
        return filepath


class BaseAgent(ABC):
    """
    Base class for all specialized agents.
    
    Agents are responsible for specific tasks in the proposal generation
    pipeline, such as generating proposals, discovery questions, or
    solution architectures.
    """
    
    def __init__(
        self,
        config: Optional[ConfigManager] = None,
        client: Optional[ClarifaiClient] = None,
        multimodal_client: Optional[MultimodalClient] = None,
    ):
        """
        Initialize the base agent.
        
        Args:
            config: Configuration manager instance.
            client: Text LLM client.
            multimodal_client: Multimodal client for images/video.
        """
        self.config = config or get_config()
        self.client = client or ClarifaiClient(config=self.config)
        self.multimodal_client = multimodal_client
        
        self.agent_name = self.__class__.__name__
        self.system_prompt = self._load_system_prompt()
        
        logger.info(f"Initialized {self.agent_name}")
    
    @abstractmethod
    def _get_prompt_file(self) -> str:
        """Return the path to the system prompt file."""
        pass
    
    def _load_system_prompt(self) -> str:
        """Load the system prompt for this agent."""
        prompt_file = self._get_prompt_file()
        return self.config.get_system_prompt(prompt_file)
    
    def _build_messages(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        include_history: bool = True,
    ) -> List[Message]:
        """
        Build the message list for a request.
        
        Args:
            prompt: User prompt.
            context: Optional context information.
            include_history: Whether to include conversation history.
            
        Returns:
            List of Message objects.
        """
        messages = []
        
        # Add system prompt
        if self.system_prompt:
            messages.append(Message(role="system", content=self.system_prompt))
        
        # Add conversation history
        if include_history and context and context.conversation_history:
            messages.extend(context.conversation_history)
        
        # Add context if provided
        if context:
            context_str = self._format_context(context)
            if context_str:
                messages.append(Message(
                    role="user",
                    content=f"Here is the context for this request:\n\n{context_str}"
                ))
                messages.append(Message(
                    role="assistant",
                    content="I understand the context. Please provide your request."
                ))
        
        # Add the main prompt
        messages.append(Message(role="user", content=prompt))
        
        return messages
    
    def _format_context(self, context: AgentContext) -> str:
        """Format context information as a string."""
        parts = []
        
        if context.customer_name:
            parts.append(f"**Customer:** {context.customer_name}")
        
        if context.project_name:
            parts.append(f"**Project:** {context.project_name}")
        
        if context.industry:
            parts.append(f"**Industry:** {context.industry}")
        
        if context.goals:
            parts.append("**Goals:**")
            for goal in context.goals:
                parts.append(f"- {goal}")
        
        if context.constraints:
            parts.append("**Constraints:**")
            for constraint in context.constraints:
                parts.append(f"- {constraint}")
        
        if context.documents:
            parts.append("**Documents Provided:**")
            for doc in context.documents:
                parts.append(f"- {doc}")
        
        if context.metadata:
            parts.append("**Additional Information:**")
            for key, value in context.metadata.items():
                parts.append(f"- {key}: {value}")
        
        return "\n".join(parts)
    
    def generate(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Generate output for the given prompt.
        
        Args:
            prompt: User prompt.
            context: Optional context information.
            **kwargs: Additional arguments for the LLM.
            
        Returns:
            AgentOutput with generated content.
        """
        messages = self._build_messages(prompt, context)
        
        response = self.client.chat(messages, **kwargs)
        
        # Update conversation history
        if context:
            context.conversation_history.append(Message(role="user", content=prompt))
            context.conversation_history.append(Message(role="assistant", content=response.content))
        
        return AgentOutput(
            content=response.content,
            agent_type=self.agent_name,
            timestamp=datetime.now(),
            context=context or AgentContext(),
            metadata={
                "usage": response.usage,
                "model": response.model,
                "finish_reason": response.finish_reason,
            }
        )
    
    def stream_generate(
        self,
        prompt: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ):
        """
        Stream generate output for the given prompt.
        
        Args:
            prompt: User prompt.
            context: Optional context information.
            **kwargs: Additional arguments for the LLM.
            
        Yields:
            Content chunks as they are generated.
        """
        messages = self._build_messages(prompt, context)
        
        for chunk in self.client.chat(messages, stream=True, **kwargs):
            yield chunk
