import json
import traceback
from typing import Dict, List, Any
import logging
from clarifai.client import Model
import os
import time

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

        max_retries = 5
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                # Get streaming response from model
                response = self.model.predict_by_bytes(
                    input_bytes=prompt.encode('utf-8'),
                    input_type="text",
                    inference_params={
                        "max_tokens": 1000,
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                )
                
                # Stream response chunks
                for chunk in response:
                    if isinstance(chunk, str):
                        yield chunk
                    elif hasattr(chunk, 'text'):
                        yield chunk.text
                    else:
                        logger.warning(f"Unexpected chunk type: {type(chunk)}")
                
                # If we get here, prediction was successful
                break
                        
            except Exception as e:
                error_msg = str(e)
                
                # Check if model is still loading
                if "MODEL_LOADING" in error_msg or "Model is deploying" in error_msg:
                    if attempt < max_retries - 1:
                        logger.warning(f"Model is loading, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error("Model failed to load after maximum retries")
                        yield "The AI model is currently loading. Please wait a moment and try again."
                else:
                    # For other errors, log and return error message
                    logger.error(f"Error getting response from model: {error_msg}")
                    logger.error(traceback.format_exc())
            yield "I apologize, but I encountered an error while processing your question. Please try again." 