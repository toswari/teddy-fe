"""
Image Processor

Handles image analysis using Clarifai's multimodal models.
"""

import base64
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.clients.clarifai_client import MultimodalClient
from src.config import get_config


logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysis:
    """Result of image analysis."""
    source: str
    description: str
    detected_elements: List[str]
    technical_notes: str
    relevance_to_project: Optional[str] = None
    metadata: Dict[str, Any] = None


class ImageProcessor:
    """
    Processes images for project analysis.
    
    Can analyze:
    - Architecture diagrams
    - UI mockups
    - Product images
    - Data flow diagrams
    - Screenshots
    """
    
    def __init__(self, client: Optional[MultimodalClient] = None):
        """
        Initialize the image processor.
        
        Args:
            client: Optional MultimodalClient for analysis.
        """
        self.client = client or MultimodalClient()
        self.config = get_config()
    
    def analyze(
        self,
        image_source: Union[str, Path],
        analysis_type: str = "general",
        project_context: Optional[str] = None,
    ) -> ImageAnalysis:
        """
        Analyze an image.
        
        Args:
            image_source: URL or path to image.
            analysis_type: Type of analysis (general, diagram, mockup, etc.).
            project_context: Context about the project for relevant analysis.
            
        Returns:
            ImageAnalysis with results.
        """
        # Build appropriate prompt based on analysis type
        prompt = self._build_analysis_prompt(analysis_type, project_context)
        
        # Determine if URL or file path
        source_str = str(image_source)
        if source_str.startswith(('http://', 'https://')):
            response = self.client.analyze_image(source_str, prompt)
        else:
            response = self.client.analyze_image_file(image_source, prompt)
        
        # Parse the response
        return self._parse_analysis_response(source_str, response.content, analysis_type)
    
    def _build_analysis_prompt(
        self,
        analysis_type: str,
        project_context: Optional[str] = None
    ) -> str:
        """Build the analysis prompt based on type."""
        
        base_prompts = {
            "general": """Analyze this image in detail. Describe:
1. What the image shows
2. Key elements and their relationships
3. Any text visible in the image
4. Technical or business implications""",
            
            "diagram": """Analyze this technical diagram. Identify:
1. Type of diagram (architecture, flow, sequence, etc.)
2. Components and systems shown
3. Data/process flows
4. Integration points
5. Any technologies or services mentioned
6. Potential implementation considerations""",
            
            "mockup": """Analyze this UI/UX mockup. Describe:
1. Type of interface (web, mobile, dashboard, etc.)
2. Key UI components and layout
3. User interactions implied
4. Data elements displayed
5. AI/ML integration opportunities
6. Technical implementation considerations""",
            
            "product": """Analyze this product image. Identify:
1. Product type and category
2. Visual features and attributes
3. Quality indicators
4. Potential use cases for AI analysis
5. Similar product detection opportunities""",
            
            "data": """Analyze this data visualization or chart. Extract:
1. Type of visualization
2. Data being represented
3. Key insights or trends
4. Data sources implied
5. Opportunities for AI-powered analytics""",
        }
        
        prompt = base_prompts.get(analysis_type, base_prompts["general"])
        
        if project_context:
            prompt += f"""

Project Context:
{project_context}

Also analyze how this image relates to the project goals and what Clarifai capabilities 
would be relevant."""
        
        return prompt
    
    def _parse_analysis_response(
        self,
        source: str,
        response_text: str,
        analysis_type: str
    ) -> ImageAnalysis:
        """Parse the AI response into structured analysis."""
        
        # Extract key elements (simple parsing)
        lines = response_text.split('\n')
        detected_elements = []
        
        for line in lines:
            if line.strip().startswith(('- ', '• ', '* ', '1.', '2.', '3.')):
                element = line.strip().lstrip('-•* 0123456789.').strip()
                if element:
                    detected_elements.append(element)
        
        return ImageAnalysis(
            source=source,
            description=response_text,
            detected_elements=detected_elements[:10],  # Top 10 elements
            technical_notes=f"Analysis type: {analysis_type}",
            metadata={"analysis_type": analysis_type},
        )
    
    def analyze_multiple(
        self,
        image_sources: List[Union[str, Path]],
        analysis_type: str = "general",
        project_context: Optional[str] = None,
    ) -> List[ImageAnalysis]:
        """
        Analyze multiple images.
        
        Args:
            image_sources: List of URLs or paths.
            analysis_type: Type of analysis.
            project_context: Project context.
            
        Returns:
            List of ImageAnalysis results.
        """
        results = []
        for source in image_sources:
            try:
                analysis = self.analyze(source, analysis_type, project_context)
                results.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing {source}: {e}")
        
        return results
    
    def compare_images(
        self,
        image1: Union[str, Path],
        image2: Union[str, Path],
        comparison_type: str = "general",
    ) -> str:
        """
        Compare two images.
        
        Args:
            image1: First image URL or path.
            image2: Second image URL or path.
            comparison_type: Type of comparison.
            
        Returns:
            Comparison analysis text.
        """
        # Analyze both images
        analysis1 = self.analyze(image1, comparison_type)
        analysis2 = self.analyze(image2, comparison_type)
        
        # Use text model to compare
        from src.clients.clarifai_client import ClarifaiClient
        text_client = ClarifaiClient()
        
        prompt = f"""Compare the following two image analyses:

## Image 1:
{analysis1.description}

## Image 2:
{analysis2.description}

Provide:
1. Key similarities
2. Key differences
3. Recommendations based on comparison
"""
        
        response = text_client.complete(prompt)
        return response.content
    
    def extract_requirements_from_diagram(
        self,
        diagram_source: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Extract technical requirements from an architecture diagram.
        
        Args:
            diagram_source: URL or path to diagram.
            
        Returns:
            Dictionary of extracted requirements.
        """
        prompt = """Analyze this architecture/technical diagram and extract:

1. **Systems/Components**: List all systems, services, or components shown
2. **Data Flows**: Describe how data moves through the system
3. **Integration Points**: Where does the system connect to external services?
4. **Technologies**: What technologies, databases, or platforms are mentioned?
5. **AI/ML Opportunities**: Where could Clarifai add value?
6. **Requirements Implied**: What functional and non-functional requirements can you infer?
7. **Questions**: What clarifying questions should we ask?

Format the response as structured sections."""
        
        source_str = str(diagram_source)
        if source_str.startswith(('http://', 'https://')):
            response = self.client.analyze_image(source_str, prompt)
        else:
            response = self.client.analyze_image_file(diagram_source, prompt)
        
        return {
            "source": source_str,
            "analysis": response.content,
            "type": "architecture_diagram",
        }
