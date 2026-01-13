"""
Video Processor

Handles video analysis using Clarifai's multimodal models.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.clients.clarifai_client import ClarifaiSDKClient
from src.config import get_config


logger = logging.getLogger(__name__)


@dataclass
class VideoAnalysis:
    """Result of video analysis."""
    source: str
    description: str
    key_moments: List[Dict[str, Any]]
    detected_elements: List[str]
    technical_notes: str
    duration_estimate: Optional[str] = None
    metadata: Dict[str, Any] = None


class VideoProcessor:
    """
    Processes videos for project analysis.
    
    Can analyze:
    - Product demos
    - Process recordings
    - Customer-provided video content
    - Training materials
    """
    
    def __init__(self, client: Optional[ClarifaiSDKClient] = None):
        """
        Initialize the video processor.
        
        Args:
            client: Optional ClarifaiSDKClient for analysis.
        """
        self.client = client or ClarifaiSDKClient()
        self.config = get_config()
    
    def analyze(
        self,
        video_source: str,
        analysis_type: str = "general",
        project_context: Optional[str] = None,
    ) -> VideoAnalysis:
        """
        Analyze a video.
        
        Args:
            video_source: URL to the video.
            analysis_type: Type of analysis (general, demo, process, etc.).
            project_context: Context about the project.
            
        Returns:
            VideoAnalysis with results.
        """
        prompt = self._build_analysis_prompt(analysis_type, project_context)
        
        try:
            response = self.client.analyze_video(video_source, prompt)
            return self._parse_analysis_response(video_source, response, analysis_type)
        except Exception as e:
            logger.error(f"Error analyzing video: {e}")
            return VideoAnalysis(
                source=video_source,
                description=f"Error analyzing video: {str(e)}",
                key_moments=[],
                detected_elements=[],
                technical_notes="Analysis failed",
                metadata={"error": str(e)},
            )
    
    def _build_analysis_prompt(
        self,
        analysis_type: str,
        project_context: Optional[str] = None
    ) -> str:
        """Build the analysis prompt based on type."""
        
        base_prompts = {
            "general": """Analyze this video in detail. Describe:
1. Main content and subject matter
2. Key scenes or moments
3. Any text, labels, or UI elements visible
4. Audio content if relevant
5. Technical or business implications""",
            
            "demo": """Analyze this product/software demo video. Identify:
1. Product or service being demonstrated
2. Key features shown
3. User interactions demonstrated
4. Pain points addressed
5. Integration opportunities with Clarifai""",
            
            "process": """Analyze this process/workflow video. Extract:
1. Steps in the process
2. Tools or systems used
3. Manual vs automated steps
4. Bottlenecks or inefficiencies
5. Opportunities for AI automation""",
            
            "training": """Analyze this training or educational video. Identify:
1. Subject matter being taught
2. Key concepts explained
3. Examples or demonstrations shown
4. Learning objectives
5. How AI could enhance or supplement""",
            
            "inspection": """Analyze this inspection or quality control video. Identify:
1. What is being inspected
2. Inspection criteria shown
3. Defects or issues visible
4. Current inspection process
5. Computer vision opportunities""",
        }
        
        prompt = base_prompts.get(analysis_type, base_prompts["general"])
        
        if project_context:
            prompt += f"""

Project Context:
{project_context}

Also analyze how this video content relates to the project goals and what Clarifai 
capabilities would be most relevant."""
        
        return prompt
    
    def _parse_analysis_response(
        self,
        source: str,
        response_text: str,
        analysis_type: str
    ) -> VideoAnalysis:
        """Parse the AI response into structured analysis."""
        
        # Extract key elements
        lines = response_text.split('\n')
        detected_elements = []
        key_moments = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('- ', '• ', '* ')):
                element = stripped.lstrip('-•* ').strip()
                if element:
                    detected_elements.append(element)
            # Look for timestamp patterns
            if any(char.isdigit() for char in stripped) and ':' in stripped:
                key_moments.append({"description": stripped})
        
        return VideoAnalysis(
            source=source,
            description=response_text,
            key_moments=key_moments[:5],
            detected_elements=detected_elements[:10],
            technical_notes=f"Analysis type: {analysis_type}",
            metadata={"analysis_type": analysis_type},
        )
    
    def extract_requirements(
        self,
        video_source: str,
    ) -> Dict[str, Any]:
        """
        Extract requirements from a video (e.g., process recording).
        
        Args:
            video_source: URL to the video.
            
        Returns:
            Dictionary of extracted requirements.
        """
        prompt = """Analyze this video and extract requirements for an AI solution:

1. **Current Process**: What process or workflow is shown?
2. **Manual Steps**: What steps require human intervention?
3. **Data Inputs**: What data is being processed or analyzed?
4. **Decision Points**: Where are decisions being made?
5. **Output/Results**: What outputs are being generated?
6. **Pain Points**: What inefficiencies or challenges are visible?
7. **AI Opportunities**: Where could AI automation add value?
8. **Technical Requirements**: What technical capabilities would be needed?
9. **Integration Needs**: What systems would need to be integrated?
10. **Questions**: What clarifying questions should we ask?

Provide structured, actionable insights."""
        
        try:
            response = self.client.analyze_video(video_source, prompt)
            return {
                "source": video_source,
                "analysis": response,
                "type": "requirements_extraction",
            }
        except Exception as e:
            return {
                "source": video_source,
                "error": str(e),
                "type": "requirements_extraction",
            }
    
    def summarize_for_proposal(
        self,
        video_source: str,
        customer_name: Optional[str] = None,
    ) -> str:
        """
        Generate a proposal-ready summary of video content.
        
        Args:
            video_source: URL to the video.
            customer_name: Optional customer name for context.
            
        Returns:
            Summary text suitable for inclusion in a proposal.
        """
        context = f"for {customer_name}" if customer_name else ""
        
        prompt = f"""Analyze this video and generate a summary suitable for a technical proposal {context}.

The summary should:
1. Describe the current state or process shown
2. Identify key challenges or opportunities
3. Suggest how Clarifai's AI capabilities could help
4. Be professional and concise
5. Be 2-3 paragraphs maximum

Focus on business value and technical feasibility."""
        
        try:
            response = self.client.analyze_video(video_source, prompt)
            return response
        except Exception as e:
            logger.error(f"Error summarizing video: {e}")
            return f"Unable to analyze video: {str(e)}"
