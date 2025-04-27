from typing import Dict, List, Any, Tuple, Optional
import logging
from .provider import LLMProvider

logger = logging.getLogger(__name__)

class UserSimulator:
    """Class for simulating user responses in testing."""
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        ground_truth: Dict[str, Any],
        user_intent: Optional[str] = None
    ):
        """
        Initialize a user simulator.
        
        Args:
            llm_provider: Provider for LLM interactions
            ground_truth: Ground truth data for simulation
            user_intent: Optional user intent description
        """
        self.llm = llm_provider
        self.ground_truth = ground_truth
        self.user_intent = user_intent or "No specific intent provided."
        
        # Store the original query
        self.original_query = ground_truth.get("user_query", "")
        
        # Extract ground truth tool calls
        self.gt_tool_calls = ground_truth.get("ground_truth_tool_calls", [])
        
        # Extract context information
        self.context = {
            k: v for k, v in ground_truth.items() 
            if k not in ["user_query", "user_intent", "ground_truth_tool_calls"]
        }
    
    def get_response_to_question(self, question: str) -> str:
        """
        Generate a simulated user response to a clarification question.
        
        Args:
            question: The question asked by the agent
            
        Returns:
            Simulated user response
        """
        # Create a prompt for the LLM to generate a realistic user response
        prompt = f"""
You are simulating a user who is interacting with an AI assistant.

Original query: "{self.original_query}"

User's intent: {self.user_intent}

Ground truth (what the user actually wants):
{self.gt_tool_calls}

Additional context:
{self.context}

The AI assistant has asked the following clarification question:
"{question}"

Generate a realistic user response to this question. The response should:
1. Be natural and conversational
2. Provide information that helps clarify the query
3. Be consistent with the user's original intent and the ground truth
4. Not explicitly mention the ground truth tool calls or parameters directly

Respond as the user would:
"""
        
        # Generate the response
        response = self.llm.generate_text(
            prompt=prompt,
            max_tokens=500,
            temperature=0.4  # Lower temperature for more deterministic responses
        )
        
        return response.strip()