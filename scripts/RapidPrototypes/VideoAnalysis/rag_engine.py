import json
import traceback
from typing import Dict, List, Any
import logging
from clarifai.client import Model
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoAnalysisRAG:
    def __init__(self, model_config: Dict[str, str]):
        self.model_config = model_config
        self.model = None  # Initialize model as None
        self.model_url = "https://clarifai.com/deepseek-ai/deepseek-chat/models/DeepSeek-R1-0528-Qwen3-8B"

    def update_credentials(self, username: str, pat: str):
        """Update the model with new credentials."""
        self.model = Model(
            url=self.model_url,
            pat=pat,
            user_id=username
        )

    def _prepare_context(self, results: Dict[str, Any]) -> str:
        """Prepare context from analysis results for the RAG system."""
        context_parts = []
        
        # Extract the actual results from the analysis_results structure
        if isinstance(results, dict) and 'results' in results:
            results = results['results']
            
            # Add duration if available
            if 'duration' in results:
                context_parts.append(f"Video Duration: {results['duration']} seconds")
            
            # Add frame-by-frame analysis
            if 'frames' in results and results['frames']:
                context_parts.append("\nDetailed Frame Analysis:")
                for frame in results['frames']:
                    frame_info = []
                    if 'timestamp' in frame:
                        frame_info.append(f"At {frame['timestamp']}s:")
                    if 'animal_behavior' in frame:
                        frame_info.append(f"Animal Behavior: {frame['animal_behavior']}")
                    if 'event_type' in frame:
                        frame_info.append(f"Event Type: {frame['event_type']}")
                    if 'performance' in frame:
                        frame_info.append(f"Performance: {frame['performance']}")
                    if 'reasoning' in frame:
                        frame_info.append(f"Reasoning: {frame['reasoning']}")
                    if 'score' in frame:
                        frame_info.append(f"Score: {frame['score']}")
                    if frame_info:
                        context_parts.append(" ".join(frame_info))
                        context_parts.append("")  # Add blank line between frames
            
        return "\n".join(context_parts)

    def _create_prompt(self, question: str, context: str) -> str:
        """Create a prompt for the model using the question and context."""
        return f"""You are an AI assistant helping to analyze video content. Use the following context to answer the question.

Context:
{context}

Question: {question}

Please provide a clear and concise answer based on the analysis results. If the information is not available in the context, say so."""

    def ask_question(self, question: str, results: Dict[str, Any]):
        """Ask a question about the video analysis results."""
        if not self.model:
            raise ValueError("Model not initialized. Please provide credentials first.")
            
        context = self._prepare_context(results)
        prompt = f"""Based on the following video analysis, please answer the question.
        
Context:
{context}

Question: {question}

Please provide a clear and concise answer based on the analysis above."""

        try:
            # Get streaming response from model
            response = self.model.generate(
                prompt=prompt,
                images=[],
                audios=[],
                videos=[],
                chat_history=[],
                audio=None,
                video=None,
                image=None,
                tools=None,
                tool_choice=None,
                system_prompt="You are a helpful AI assistant that analyzes video content. Keep it short and to the point",
                max_tokens=1000,
                temperature=0.7,
                top_p=0.9,
                reasoning_effort="low"
            )
            
            # Stream response chunks
            for chunk in response:
                if isinstance(chunk, str):
                    yield chunk
                elif hasattr(chunk, 'text'):
                    yield chunk.text
                else:
                    logger.warning(f"Unexpected chunk type: {type(chunk)}")
                
        except Exception as e:
            logger.error(f"Error getting response from model: {str(e)}")
            logger.error(traceback.format_exc())
            yield "I apologize, but I encountered an error while processing your question. Please try again." 
