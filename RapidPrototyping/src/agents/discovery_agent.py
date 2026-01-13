"""
Discovery Questions Agent

Generates and manages discovery questions for customer engagements.
"""

import logging
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent, AgentContext, AgentOutput


logger = logging.getLogger(__name__)


# Industry-specific question templates
INDUSTRY_QUESTIONS = {
    "retail": [
        "What is the size of your product catalog?",
        "Do you need visual search capabilities?",
        "What is your current recommendation system (if any)?",
        "What e-commerce platform do you use?",
    ],
    "healthcare": [
        "What HIPAA compliance requirements do you have?",
        "Are you working with medical imaging data?",
        "What EHR systems do you need to integrate with?",
        "Do you need FDA approval considerations?",
    ],
    "financial": [
        "What fraud detection capabilities do you need?",
        "What regulatory compliance requirements apply?",
        "Do you need real-time transaction processing?",
        "What is your risk tolerance for false positives/negatives?",
    ],
    "manufacturing": [
        "What quality control processes need automation?",
        "Do you need edge deployment for factory floor?",
        "What types of defects are you looking to detect?",
        "What is your current inspection throughput?",
    ],
    "media": [
        "What content moderation requirements do you have?",
        "Do you need video analysis capabilities?",
        "What volume of content do you process daily?",
        "Do you have existing content tagging systems?",
    ],
}


class DiscoveryAgent(BaseAgent):
    """
    Agent for generating and managing discovery questions.
    
    Helps Solution Engineers gather all necessary information
    from customers during the discovery phase.
    """
    
    def _get_prompt_file(self) -> str:
        return "prompts/discovery.md"
    
    def generate_questions(
        self,
        customer_context: str,
        industry: Optional[str] = None,
        focus_areas: Optional[List[str]] = None,
        existing_info: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Generate discovery questions based on customer context.
        
        Args:
            customer_context: Description of customer and their needs.
            industry: Industry vertical for specialized questions.
            focus_areas: Specific areas to focus on.
            existing_info: Information already gathered.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with categorized questions.
        """
        context = AgentContext(
            industry=industry,
            metadata={
                "focus_areas": focus_areas or [],
                "existing_info": existing_info or {},
            }
        )
        
        prompt_parts = [
            "Generate comprehensive discovery questions for the following customer engagement.",
            f"\n## Customer Context:\n{customer_context}",
        ]
        
        if industry:
            prompt_parts.append(f"\n## Industry: {industry}")
            if industry.lower() in INDUSTRY_QUESTIONS:
                prompt_parts.append("\n## Industry-Specific Considerations:")
                for q in INDUSTRY_QUESTIONS[industry.lower()]:
                    prompt_parts.append(f"- Consider: {q}")
        
        if focus_areas:
            prompt_parts.append("\n## Focus Areas:")
            for area in focus_areas:
                prompt_parts.append(f"- {area}")
        
        if existing_info:
            prompt_parts.append("\n## Information Already Gathered:")
            for key, value in existing_info.items():
                prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("\nDo not ask questions about information already provided.")
        
        prompt_parts.append("""
## Required Output Structure:

Please organize questions into these categories:
1. **Business Requirements** - Understanding business goals and impact
2. **Technical Requirements** - Infrastructure, performance, integration needs
3. **Data Requirements** - Data availability, quality, format, and privacy
4. **Integration Requirements** - Systems and workflows to connect with
5. **Timeline & Budget** - Project constraints and expectations
6. **Success Criteria** - How success will be measured

For each question, include:
- The question itself
- Why this question is important
- Red flags to watch for in the answer
""")
        
        prompt = "\n".join(prompt_parts)
        
        return self.generate(prompt, context, **kwargs)
    
    def prioritize_questions(
        self,
        questions: List[str],
        time_available: int = 30,
        customer_context: Optional[str] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Prioritize questions based on available time.
        
        Args:
            questions: List of potential questions.
            time_available: Minutes available for discovery.
            customer_context: Optional customer context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with prioritized questions.
        """
        questions_text = "\n".join([f"- {q}" for q in questions])
        
        prompt = f"""Given the following discovery questions and {time_available} minutes 
available for the discovery call, prioritize the questions.

## Questions:
{questions_text}

{f"## Customer Context: {customer_context}" if customer_context else ""}

Please provide:
1. **Must Ask** - Critical questions that must be answered
2. **Should Ask** - Important but can be followed up via email
3. **Nice to Have** - Helpful but not essential

Also suggest the optimal order to ask questions for natural conversation flow.
"""
        
        return self.generate(prompt, **kwargs)
    
    def generate_followup_questions(
        self,
        question: str,
        answer: str,
        context: Optional[AgentContext] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Generate follow-up questions based on an answer.
        
        Args:
            question: Original question asked.
            answer: Customer's answer.
            context: Optional conversation context.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with follow-up questions.
        """
        prompt = f"""Based on the following question and answer, generate relevant 
follow-up questions to gather more detail or clarify any ambiguities.

## Question:
{question}

## Answer:
{answer}

Generate 2-4 follow-up questions that would help clarify or expand on this answer.
For each follow-up, explain why it's important.
"""
        
        return self.generate(prompt, context, **kwargs)
    
    def identify_gaps(
        self,
        discovery_notes: str,
        required_sections: Optional[List[str]] = None,
        **kwargs
    ) -> AgentOutput:
        """
        Identify information gaps from discovery notes.
        
        Args:
            discovery_notes: Notes from discovery sessions.
            required_sections: Sections that must be covered.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with identified gaps and questions.
        """
        sections = required_sections or [
            "Business requirements",
            "Technical requirements",
            "Data requirements",
            "Integration requirements",
            "Timeline and budget",
            "Success criteria"
        ]
        
        sections_text = "\n".join([f"- {s}" for s in sections])
        
        prompt = f"""Review the following discovery notes and identify any gaps 
or missing information that would be needed for a complete proposal.

## Discovery Notes:
{discovery_notes}

## Required Information Areas:
{sections_text}

Please provide:
1. **Information Gaps** - What critical information is missing
2. **Assumptions Made** - What we might need to assume if gaps aren't filled
3. **Follow-up Questions** - Specific questions to fill the gaps
4. **Risk Level** - How risky it would be to proceed without this information
"""
        
        return self.generate(prompt, **kwargs)
    
    def create_discovery_guide(
        self,
        customer_name: str,
        industry: str,
        initial_context: str,
        meeting_duration: int = 60,
        **kwargs
    ) -> AgentOutput:
        """
        Create a complete discovery meeting guide.
        
        Args:
            customer_name: Customer company name.
            industry: Industry vertical.
            initial_context: What we know about the opportunity.
            meeting_duration: Length of meeting in minutes.
            **kwargs: Additional LLM arguments.
            
        Returns:
            AgentOutput with complete discovery guide.
        """
        context = AgentContext(
            customer_name=customer_name,
            industry=industry,
        )
        
        prompt = f"""Create a comprehensive discovery meeting guide for a {meeting_duration}-minute 
call with {customer_name} in the {industry} industry.

## Initial Context:
{initial_context}

Please create a guide that includes:

1. **Meeting Objectives** - What we need to accomplish
2. **Agenda** - Time-boxed agenda for the call
3. **Introduction Script** - How to open the conversation
4. **Core Questions** - Organized by category with time allocations
5. **Probing Questions** - Follow-ups for common answers
6. **Red Flags** - Warning signs to watch for
7. **Demo Opportunities** - When to show Clarifai capabilities
8. **Next Steps Script** - How to close and set next actions
9. **Pre-Meeting Prep** - What to research before the call

Make the guide practical and actionable for a Solution Engineer.
"""
        
        return self.generate(prompt, context, **kwargs)
