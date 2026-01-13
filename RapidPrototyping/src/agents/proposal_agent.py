"""
Proposal Generation Agent

Generates comprehensive project proposals for Clarifai customers.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent, AgentContext, AgentOutput
from src.clients.clarifai_client import Message


logger = logging.getLogger(__name__)


class ProposalAgent(BaseAgent):
    """
    Agent for generating project proposals.
    
    Creates comprehensive proposals including:
    - Executive summary
    - Problem statement
    - Proposed solution
    - Technical approach
    - Deliverables
    - Timeline
    - Pricing considerations
    - Risks and mitigations
    - Success metrics
    - Next steps
    """
    
    def _get_prompt_file(self) -> str:
        return "prompts/proposal.md"
    
    def generate_proposal(
        self,
        customer_name: str,
        project_name: str,
        goals: List[str],
        industry: Optional[str] = None,
        requirements: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        documents_summary: Optional[str] = None,
        discovery_answers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Generate a comprehensive project proposal.
        
        Args:
            customer_name: Name of the customer/company.
            project_name: Name of the project.
            goals: List of project goals.
            industry: Industry vertical.
            requirements: Detailed requirements text.
            constraints: List of constraints or limitations.
            documents_summary: Summary of provided documents.
            discovery_answers: Answers to discovery questions.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with the generated proposal.
        """
        # Build context
        context = AgentContext(
            customer_name=customer_name,
            project_name=project_name,
            industry=industry,
            goals=goals,
            constraints=constraints or [],
        )
        
        # Build detailed prompt
        prompt_parts = [
            f"Generate a comprehensive project proposal for {customer_name}.",
            f"\n## Project: {project_name}",
            f"\n## Industry: {industry or 'Not specified'}",
            "\n## Goals:",
        ]
        
        for goal in goals:
            prompt_parts.append(f"- {goal}")
        
        if requirements:
            prompt_parts.append(f"\n## Requirements:\n{requirements}")
        
        if constraints:
            prompt_parts.append("\n## Constraints:")
            for constraint in constraints:
                prompt_parts.append(f"- {constraint}")
        
        if documents_summary:
            prompt_parts.append(f"\n## Document Summary:\n{documents_summary}")
        
        if discovery_answers:
            prompt_parts.append("\n## Discovery Information:")
            for question, answer in discovery_answers.items():
                prompt_parts.append(f"\n**{question}**\n{answer}")
        
        prompt_parts.append(
            "\n\nPlease generate a complete project proposal with all sections "
            "(Executive Summary, Problem Statement, Proposed Solution, Technical Approach, "
            "Deliverables, Timeline, Pricing Considerations, Risks & Mitigations, "
            "Success Metrics, and Next Steps)."
        )
        
        prompt = "\n".join(prompt_parts)
        
        return self.generate(prompt, context, **kwargs)
    
    def refine_proposal(
        self,
        original_proposal: str,
        feedback: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Refine an existing proposal based on feedback.
        
        Args:
            original_proposal: The original proposal text.
            feedback: Feedback for improvements.
            context: Optional context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with refined proposal.
        """
        prompt = f"""Please refine the following proposal based on the feedback provided.

## Original Proposal:
{original_proposal}

## Feedback:
{feedback}

Please update the proposal to address the feedback while maintaining the overall structure and quality.
"""
        
        return self.generate(prompt, context, **kwargs)
    
    def generate_executive_summary(
        self,
        full_proposal: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Generate a standalone executive summary from a full proposal.
        
        Args:
            full_proposal: The full proposal text.
            context: Optional context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with executive summary.
        """
        prompt = f"""Based on the following proposal, generate a concise executive summary 
(1-2 pages) suitable for C-level executives. Focus on business value, ROI, and key outcomes.

## Full Proposal:
{full_proposal}
"""
        
        return self.generate(prompt, context, **kwargs)
    
    def generate_technical_appendix(
        self,
        full_proposal: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Generate a technical appendix with implementation details.
        
        Args:
            full_proposal: The full proposal text.
            context: Optional context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with technical appendix.
        """
        prompt = f"""Based on the following proposal, generate a detailed technical appendix 
that covers:
1. API specifications and endpoints
2. Data requirements and formats
3. Integration architecture
4. Model configurations
5. Infrastructure requirements
6. Security considerations
7. Performance benchmarks

## Full Proposal:
{full_proposal}
"""
        
        return self.generate(prompt, context, **kwargs)
    
    def compare_solutions(
        self,
        requirements: str,
        solutions: List[Dict[str, str]],
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Compare multiple solution approaches.
        
        Args:
            requirements: Customer requirements.
            solutions: List of solution options with name and description.
            context: Optional context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with comparison analysis.
        """
        solutions_text = "\n\n".join([
            f"### Option {i+1}: {sol['name']}\n{sol['description']}"
            for i, sol in enumerate(solutions)
        ])
        
        prompt = f"""Compare the following solution options for the given requirements.
Provide a detailed comparison matrix and recommendation.

## Requirements:
{requirements}

## Solution Options:
{solutions_text}

Please provide:
1. Comparison matrix (features, pros, cons, effort, cost)
2. Recommendation with justification
3. Risk analysis for each option
"""
        
        return self.generate(prompt, context, **kwargs)
