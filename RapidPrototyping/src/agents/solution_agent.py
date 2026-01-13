"""
Solution Architecture Agent

Designs technical solution architectures for Clarifai implementations.
"""

import logging
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent, AgentContext, AgentOutput


logger = logging.getLogger(__name__)


# Clarifai capabilities reference (https://docs.clarifai.com/)
CLARIFAI_CAPABILITIES = {
    "models": {
        "frontier_multimodal": [
            "Vision-Language Models (VLMs) - Complex reasoning, detailed image analysis",
            "Large Multi-modal Models (LMMs) - Nuanced understanding, multi-step reasoning",
            "Open-source VLMs - Cost-effective for high-volume tasks",
        ],
        "text_models": [
            "Text Generation (text-to-text) - LLMs for completion, chat",
            "Text Embedders - Vector embeddings for RAG/search",
            "Text Classification - Categorization tasks",
            "RAG Prompter - Built-in retrieval augmented generation",
        ],
        "vision_models": [
            "Visual Classifier - Image classification",
            "Visual Detector - Object detection with bounding boxes",
            "Visual Segmenter - Semantic/instance segmentation",
            "Visual Embedder - Image embeddings for visual search",
            "Zero-shot Classifier - Classification without training",
            "OCR - Optical character recognition",
        ],
        "audio_models": [
            "Audio-to-Text - Speech recognition",
            "Text-to-Audio - Speech synthesis",
            "Audio Embedder - Audio embeddings",
        ],
        "custom": [
            "Custom Model Training (only when VLMs cannot meet requirements)",
            "Transfer Learning - Build on existing models",
            "Deep Fine-tuning - Train from scratch",
        ],
    },
    "model_size_to_gpu": {
        "description": "Model parameter count determines minimum GPU VRAM required",
        "sizing_guide": {
            "1-3B": {"vram_fp16": "6-8GB", "vram_int8": "3-4GB", "gpu_tier": "Entry (16GB)", "examples": "Small VLMs, embedders"},
            "7-8B": {"vram_fp16": "14-16GB", "vram_int8": "7-8GB", "gpu_tier": "Entry (16GB) or Standard (24GB)", "examples": "Llama 3.1 8B, Mistral 7B"},
            "13-14B": {"vram_fp16": "26-28GB", "vram_int8": "13-14GB", "gpu_tier": "Standard (24GB) or Performance (48GB)", "examples": "Llama 2 13B"},
            "30-34B": {"vram_fp16": "60-70GB", "vram_int8": "30-35GB", "gpu_tier": "Performance (48GB) or Enterprise (80GB)", "examples": "CodeLlama 34B"},
            "70B": {"vram_fp16": "140GB", "vram_int8": "70GB", "gpu_tier": "Enterprise (80GB) or Multi-GPU", "examples": "Llama 3.1 70B"},
            "100B+": {"vram_fp16": "200GB+", "vram_int8": "100GB+", "gpu_tier": "Multi-GPU (2-8x H100)", "examples": "Large proprietary models"},
        },
        "notes": [
            "FP16 (half precision) is standard for quality inference",
            "INT8 quantization reduces VRAM ~50% with minimal quality loss",
            "Add 20-30% overhead for KV cache during inference",
            "Batch processing increases VRAM requirements",
            "Consider GPU fractioning for smaller models on larger GPUs",
        ],
    },
    "workflows": {
        "description": "Combine multiple models in pipelines (https://docs.clarifai.com/create/workflows/)",
        "features": [
            "Sequential processing",
            "Parallel branching",
            "Conditional logic",
            "Agent system operators",
            "RAG with vector search",
        ],
    },
    "agents": {
        "description": "Build autonomous AI agents (https://docs.clarifai.com/compute/agents/)",
        "features": [
            "Multi-step reasoning",
            "Tool calling and usage",
            "MCP (Model Context Protocol) support",
            "Web search, code execution, image generation tools",
        ],
    },
    "pipelines": {
        "description": "Async, long-running workflows (https://docs.clarifai.com/compute/pipelines/)",
        "features": [
            "MLOps automation",
            "Batch processing",
            "Model fine-tuning jobs",
            "Multi-step AI agent orchestration",
        ],
    },
    "vector_search": {
        "description": "Semantic search and RAG (https://docs.clarifai.com/create/search/)",
        "features": [
            "Text and image embeddings",
            "Similarity search",
            "Filter and rank results",
            "Native vector database",
        ],
    },
    "inference_options": {
        "sdks": [
            "Python SDK: pip install clarifai (RECOMMENDED)",
            "Node.js SDK: npm install clarifai",
            "OpenAI-compatible: https://api.clarifai.com/v2/ext/openai/v1",
            "LiteLLM integration",
            "Vercel AI SDK",
            "REST API (gRPC also available)",
        ],
        "docs": "https://docs.clarifai.com/compute/inference/",
    },
    "compute_orchestration": {
        "description": "Deploy models anywhere (https://docs.clarifai.com/compute/overview)",
        "deployment_options": [
            "Shared SaaS (Serverless) - For Clarifai models",
            "Dedicated SaaS - Managed isolated nodes",
            "Self-Managed VPC - Your cloud, Clarifai orchestration",
            "Self-Managed On-Premises - Your hardware",
            "Multi-Site Deployment - Multiple environments",
            "Full Platform Deployment - Air-gapped/compliance",
        ],
        "benefits": [
            "Autoscaling (scale to zero)",
            "GPU fractioning - multiple models per GPU",
            "Model packing - up to 3.7x efficiency",
            "60-90% cost savings possible",
        ],
    },
    "model_selection_guidance": {
        "default": "Recommend VLMs (starting with mm-poly-8b) over legacy CV models for visual understanding",
        "recommended_vlms": [
            "mm-poly-8b (Clarifai) - 8B params, Standard GPU, recommended first choice",
            "Llama 3.2 Vision - 11B params, Standard GPU, document analysis",
            "Qwen2-VL - 7-72B params, various tiers, high accuracy",
            "LLaVA 1.6 - 7-34B params, well-balanced performance",
            "Phi-3 Vision - 4.2B params, Entry GPU, cost-effective",
        ],
        "custom_training_triggers": [
            "VLMs cannot achieve required accuracy after prompt optimization",
            "Latency requirement < 20ms per image",
            "Throughput requirement > 500 images/second",
            "Offline/edge deployment mandatory",
            "Cost optimization at massive scale (after validation)",
        ],
    },
}


class SolutionAgent(BaseAgent):
    """
    Agent for designing solution architectures.
    
    Creates technical architectures leveraging Clarifai's
    platform capabilities for customer solutions.
    """
    
    def _get_prompt_file(self) -> str:
        return "prompts/solution.md"
    
    def design_architecture(
        self,
        requirements: str,
        constraints: Optional[List[str]] = None,
        existing_infrastructure: Optional[str] = None,
        scale_requirements: Optional[str] = None,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Design a complete solution architecture.
        
        Args:
            requirements: Detailed requirements.
            constraints: Technical constraints.
            existing_infrastructure: Current infrastructure description.
            scale_requirements: Scale and performance needs.
            context: Optional context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with architecture design.
        """
        prompt_parts = [
            "Design a comprehensive solution architecture for the following requirements.",
            f"\n## Requirements:\n{requirements}",
        ]
        
        if constraints:
            prompt_parts.append("\n## Constraints:")
            for c in constraints:
                prompt_parts.append(f"- {c}")
        
        if existing_infrastructure:
            prompt_parts.append(f"\n## Existing Infrastructure:\n{existing_infrastructure}")
        
        if scale_requirements:
            prompt_parts.append(f"\n## Scale Requirements:\n{scale_requirements}")
        
        # Add Clarifai capabilities reference
        prompt_parts.append("\n## Available Clarifai Capabilities:")
        for category, items in CLARIFAI_CAPABILITIES["models"].items():
            prompt_parts.append(f"\n**{category.upper()} Models:**")
            for item in items:
                prompt_parts.append(f"- {item}")
        
        prompt_parts.append("""
## Required Output:

Please provide a complete architecture document including:

1. **Architecture Overview**
   - High-level description
   - Architecture diagram (using Mermaid)
   - Key components

2. **Data Flow**
   - Input sources and formats
   - Processing pipeline
   - Output destinations

3. **Clarifai Components**
   - Models to use (with justification)
   - Workflows needed
   - Custom training requirements

4. **Integration Design**
   - API endpoints
   - Authentication
   - Error handling

5. **Infrastructure**
   - Deployment topology
   - Scaling strategy
   - High availability

6. **Security**
   - Data protection
   - Access control
   - Compliance considerations

7. **Monitoring & Observability**
   - Metrics to track
   - Alerting strategy
   - Logging approach

8. **Implementation Phases**
   - Phased rollout plan
   - Dependencies
   - Risk mitigation
""")
        
        prompt = "\n".join(prompt_parts)
        
        return self.generate(prompt, context, **kwargs)
    
    def recommend_models(
        self,
        use_case: str,
        data_types: List[str],
        performance_requirements: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Recommend appropriate Clarifai models for a use case.
        
        Args:
            use_case: Description of the use case.
            data_types: Types of data to process (image, video, text, etc.).
            performance_requirements: Latency, accuracy requirements.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with model recommendations.
        """
        data_types_text = ", ".join(data_types)
        
        perf_text = ""
        if performance_requirements:
            perf_text = "\n## Performance Requirements:\n"
            for key, value in performance_requirements.items():
                perf_text += f"- {key}: {value}\n"
        
        prompt = f"""Recommend the best Clarifai models for the following use case.

## Use Case:
{use_case}

## Data Types:
{data_types_text}
{perf_text}

## Available Models Reference:
{self._format_capabilities()}

Please provide:
1. **Primary Model Recommendation** - Best model for the core use case
2. **Alternative Options** - Other models that could work
3. **Comparison Matrix** - Compare options on accuracy, speed, cost
4. **Custom Training Needs** - Whether fine-tuning would help
5. **Workflow Design** - If multiple models are needed
6. **Implementation Notes** - Tips for best results
"""
        
        return self.generate(prompt, **kwargs)
    
    def _format_capabilities(self) -> str:
        """Format Clarifai capabilities as text."""
        lines = []
        for category, items in CLARIFAI_CAPABILITIES["models"].items():
            lines.append(f"\n**{category.upper()}:**")
            for item in items:
                lines.append(f"  - {item}")
        return "\n".join(lines)
    
    def design_workflow(
        self,
        processing_steps: List[str],
        input_type: str,
        output_requirements: str,
        **kwargs
    ) -> AgentOutput:
        """
        Design a Clarifai workflow for multi-step processing.
        
        Args:
            processing_steps: Required processing steps.
            input_type: Type of input data.
            output_requirements: Required output format/data.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with workflow design.
        """
        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(processing_steps)])
        
        prompt = f"""Design a Clarifai workflow for the following requirements.

## Input Type:
{input_type}

## Processing Steps Required:
{steps_text}

## Output Requirements:
{output_requirements}

Please provide:
1. **Workflow Diagram** (Mermaid format)
2. **Node Configuration** - Each model/operator in the workflow
3. **Data Transformations** - How data flows between nodes
4. **Error Handling** - How to handle failures at each step
5. **Performance Considerations** - Parallel vs sequential processing
6. **Example API Call** - How to invoke the workflow
"""
        
        return self.generate(prompt, **kwargs)
    
    def estimate_infrastructure(
        self,
        expected_volume: str,
        latency_requirements: str,
        availability_requirements: str,
        deployment_preference: str = "cloud",
        **kwargs
    ) -> AgentOutput:
        """
        Estimate infrastructure requirements.
        
        Args:
            expected_volume: Expected request volume.
            latency_requirements: Latency SLA.
            availability_requirements: Uptime requirements.
            deployment_preference: cloud, on-premise, or hybrid.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with infrastructure estimates.
        """
        prompt = f"""Estimate infrastructure requirements for a Clarifai deployment.

## Expected Volume:
{expected_volume}

## Latency Requirements:
{latency_requirements}

## Availability Requirements:
{availability_requirements}

## Deployment Preference:
{deployment_preference}

Please provide:
1. **Resource Estimates** - Compute, memory, storage needs
2. **Scaling Strategy** - How to handle peak loads
3. **High Availability Design** - Redundancy and failover
4. **Cost Estimation** - Rough monthly cost ranges
5. **Deployment Architecture** - Diagram and components
6. **Monitoring Requirements** - What to track
7. **Disaster Recovery** - Backup and recovery strategy
"""
        
        return self.generate(prompt, **kwargs)
    
    def create_poc_plan(
        self,
        solution_summary: str,
        success_criteria: List[str],
        timeline_weeks: int = 4,
        **kwargs
    ) -> AgentOutput:
        """
        Create a Proof of Concept plan.
        
        Args:
            solution_summary: Summary of proposed solution.
            success_criteria: How POC success will be measured.
            timeline_weeks: POC duration in weeks.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with POC plan.
        """
        criteria_text = "\n".join([f"- {c}" for c in success_criteria])
        
        prompt = f"""Create a Proof of Concept (POC) plan for the following solution.

## Solution Summary:
{solution_summary}

## Success Criteria:
{criteria_text}

## Timeline:
{timeline_weeks} weeks

Please provide:
1. **POC Objectives** - What we're proving
2. **Scope Definition** - What's in and out of scope
3. **Week-by-Week Plan** - Detailed activities
4. **Data Requirements** - What data is needed from customer
5. **Deliverables** - What will be delivered
6. **Demo Scenarios** - What will be demonstrated
7. **Success Metrics** - How we'll measure each criterion
8. **Risk Mitigation** - Potential issues and solutions
9. **Resource Requirements** - People and tools needed
10. **Go/No-Go Criteria** - Decision framework for production
"""
        
        return self.generate(prompt, **kwargs)
