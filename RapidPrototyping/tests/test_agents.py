"""
Tests for the Rapid Prototyping Framework agents.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.agents.base_agent import BaseAgent, AgentContext, AgentOutput, Message
from src.agents.proposal_agent import ProposalAgent
from src.agents.discovery_agent import DiscoveryAgent
from src.agents.solution_agent import SolutionAgent


class TestAgentContext:
    """Tests for AgentContext dataclass."""
    
    def test_default_values(self):
        """Test default initialization."""
        ctx = AgentContext()
        assert ctx.customer_name is None
        assert ctx.project_name is None
        assert ctx.industry is None
        assert ctx.documents == []
        assert ctx.goals == []
        assert ctx.constraints == []
        assert ctx.metadata == {}
        assert ctx.conversation_history == []
    
    def test_with_values(self):
        """Test initialization with values."""
        ctx = AgentContext(
            customer_name="TestCorp",
            project_name="AI Project",
            industry="Technology",
            goals=["Goal 1", "Goal 2"],
        )
        assert ctx.customer_name == "TestCorp"
        assert ctx.project_name == "AI Project"
        assert ctx.industry == "Technology"
        assert ctx.goals == ["Goal 1", "Goal 2"]


class TestAgentOutput:
    """Tests for AgentOutput dataclass."""
    
    def test_creation(self):
        """Test output creation."""
        ctx = AgentContext(customer_name="TestCorp")
        output = AgentOutput(
            content="Test content",
            agent_type="TestAgent",
            timestamp=datetime.now(),
            context=ctx,
        )
        assert output.content == "Test content"
        assert output.agent_type == "TestAgent"
        assert output.context.customer_name == "TestCorp"
    
    def test_save(self, tmp_path):
        """Test saving output to file."""
        ctx = AgentContext(customer_name="TestCorp")
        output = AgentOutput(
            content="# Test Proposal\n\nThis is test content.",
            agent_type="ProposalAgent",
            timestamp=datetime.now(),
            context=ctx,
        )
        
        filepath = output.save(str(tmp_path))
        assert filepath.exists()
        assert filepath.suffix == ".md"
        
        content = filepath.read_text()
        assert "Test Proposal" in content
        assert "customer: TestCorp" in content


class TestProposalAgent:
    """Tests for ProposalAgent."""
    
    @patch('src.agents.base_agent.ClarifaiClient')
    def test_initialization(self, mock_client):
        """Test agent initialization."""
        mock_client.return_value = MagicMock()
        agent = ProposalAgent()
        assert agent.agent_name == "ProposalAgent"
    
    @patch('src.agents.base_agent.ClarifaiClient')
    def test_generate_proposal(self, mock_client):
        """Test proposal generation."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.content = "# Generated Proposal\n\nTest content"
        mock_response.usage = {"total_tokens": 100}
        mock_response.model = "test-model"
        mock_response.finish_reason = "stop"
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        agent = ProposalAgent()
        result = agent.generate_proposal(
            customer_name="TestCorp",
            project_name="AI Project",
            goals=["Implement visual search"],
            industry="Retail",
        )
        
        assert result.content == "# Generated Proposal\n\nTest content"
        assert result.agent_type == "ProposalAgent"
        assert result.context.customer_name == "TestCorp"


class TestDiscoveryAgent:
    """Tests for DiscoveryAgent."""
    
    @patch('src.agents.base_agent.ClarifaiClient')
    def test_initialization(self, mock_client):
        """Test agent initialization."""
        mock_client.return_value = MagicMock()
        agent = DiscoveryAgent()
        assert agent.agent_name == "DiscoveryAgent"
    
    @patch('src.agents.base_agent.ClarifaiClient')
    def test_generate_questions(self, mock_client):
        """Test question generation."""
        mock_response = MagicMock()
        mock_response.content = "## Discovery Questions\n\n1. What is your goal?"
        mock_response.usage = {"total_tokens": 100}
        mock_response.model = "test-model"
        mock_response.finish_reason = "stop"
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        agent = DiscoveryAgent()
        result = agent.generate_questions(
            customer_context="E-commerce company looking for AI",
            industry="retail",
        )
        
        assert "Discovery Questions" in result.content
        assert result.agent_type == "DiscoveryAgent"


class TestSolutionAgent:
    """Tests for SolutionAgent."""
    
    @patch('src.agents.base_agent.ClarifaiClient')
    def test_initialization(self, mock_client):
        """Test agent initialization."""
        mock_client.return_value = MagicMock()
        agent = SolutionAgent()
        assert agent.agent_name == "SolutionAgent"
    
    @patch('src.agents.base_agent.ClarifaiClient')
    def test_design_architecture(self, mock_client):
        """Test architecture design."""
        mock_response = MagicMock()
        mock_response.content = "## Architecture\n\nCloud-based solution"
        mock_response.usage = {"total_tokens": 100}
        mock_response.model = "test-model"
        mock_response.finish_reason = "stop"
        
        mock_client_instance = MagicMock()
        mock_client_instance.chat.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        agent = SolutionAgent()
        result = agent.design_architecture(
            requirements="Visual search for e-commerce",
            constraints=["Must use AWS"],
        )
        
        assert "Architecture" in result.content
        assert result.agent_type == "SolutionAgent"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
