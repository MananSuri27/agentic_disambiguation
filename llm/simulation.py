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
        
        # Track which tool calls have been completed
        self.completed_tool_calls = set()
        
        # Extract potential follow-up queries
        self.potential_follow_ups = ground_truth.get("potential_follow_ups", [])
        self.current_follow_up_index = 0
        
        # Extract context information
        self.context = {
            k: v for k, v in ground_truth.items() 
            if k not in ["user_query", "user_intent", "ground_truth_tool_calls", "potential_follow_ups"]
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
        
    def get_next_request(self, conversation_history: List[Dict[str, Any]]) -> Optional[str]:
        """
        Generate a simulated follow-up request based on the conversation so far.
        
        Args:
            conversation_history: List of conversation turns so far
            
        Returns:
            Simulated user request or None if the user would have no more requests
        """
        # Check if the agent has indicated completion
        if self._agent_indicates_completion(conversation_history):
            return None
            
        # If we have predefined follow-ups, use the next one
        if self.potential_follow_ups and self.current_follow_up_index < len(self.potential_follow_ups):
            next_follow_up = self.potential_follow_ups[self.current_follow_up_index]
            self.current_follow_up_index += 1
            return next_follow_up
        
        # Format conversation history
        formatted_history = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "unknown")
                message = turn.get("message", "")
                history_lines.append(f"{role.capitalize()}: {message}")
            formatted_history = "\n".join(history_lines)
            
        # Create a prompt for the LLM to decide if the user would have a follow-up
        prompt = f"""
You are simulating a user who is interacting with an AI assistant.

Original query: "{self.original_query}"

User's intent: {self.user_intent}

Previous conversation:
{formatted_history}

Based on the conversation so far and the user's intent, decide if the user would have a follow-up request.
Consider:
1. Has everything the user wanted been accomplished?
2. Is there a logical next step the user might want to take?
3. Has the agent clearly indicated that they've completed all necessary tasks?

If you believe the user would have a follow-up request, provide it in a natural, conversational way.
If you believe the conversation is complete, respond with "CONVERSATION_COMPLETE".

Decision:
"""
        
        # Generate the decision
        decision = self.llm.generate_text(
            prompt=prompt,
            max_tokens=500,
            temperature=0.4
        )
        
        decision = decision.strip()
        
        # Check if the decision indicates completion
        if "CONVERSATION_COMPLETE" in decision or "conversation complete" in decision.lower():
            return None
            
        return decision
        
    def _agent_indicates_completion(self, conversation_history: List[Dict[str, Any]]) -> bool:
        """
        Check if the agent has clearly indicated that the conversation is complete.
        
        Args:
            conversation_history: List of conversation turns
            
        Returns:
            True if the agent has indicated completion, False otherwise
        """
        # Look at the most recent agent messages
        recent_agent_messages = []
        for turn in reversed(conversation_history):
            if turn.get("role") == "agent":
                recent_agent_messages.append(turn.get("message", "").lower())
                if len(recent_agent_messages) >= 2:
                    break
                    
        # Check for completion indicators in the most recent agent messages
        completion_phrases = [
            "all done", 
            "completed your request", 
            "finished", 
            "completed all tasks",
            "anything else",
            "is there anything else",
            "all tasks have been completed",
            "all set",
            "that completes",
            "all of your requests have been",
            "task is complete",
            "successfully completed"
        ]
        
        for message in recent_agent_messages:
            if any(phrase in message for phrase in completion_phrases):
                return True
                
        return False