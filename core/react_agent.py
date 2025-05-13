from typing import Dict, List, Any, Tuple, Optional
import logging
import copy
from core.tool_registry import ToolRegistry
from core.uncertainty import ToolCall, UncertaintyCalculator
from core.question_generation import QuestionGenerator
from core.tool_executor import ToolExecutor
from core.plugin_manager import PluginManager
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)

class ReactAgent:
    """
    Class implementing a Reason-Action (Re-Act) agent that maintains conversation history
    and processes multi-turn interactions.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        uncertainty_calculator: UncertaintyCalculator,
        question_generator: QuestionGenerator,
        tool_executor: ToolExecutor,
        plugin_manager: PluginManager,
        config: Dict[str, Any] = None
    ):
        """
        Initialize a Re-Act agent.
        
        Args:
            llm_provider: Provider for LLM interactions
            tool_registry: Registry of available tools
            uncertainty_calculator: Calculator for uncertainty metrics
            question_generator: Generator for clarification questions
            tool_executor: Executor for tool calls
            plugin_manager: Manager for API plugins
            config: Configuration parameters
        """
        self.llm = llm_provider
        self.tool_registry = tool_registry
        self.uncertainty_calculator = uncertainty_calculator
        self.question_generator = question_generator
        self.tool_executor = tool_executor
        self.plugin_manager = plugin_manager
        self.config = config or {}
        
        # Initialize conversation history
        self.conversation_history = []
        
        # Initialize metrics tracking
        self.all_tool_calls = []
        self.all_execution_results = []
        self.question_history = []
        
        # Flag to track if the conversation should end
        self.should_end_flag = False
        
        # Track turn count
        self.turn_count = 0
    
    def process_user_input(self, user_input: str, is_initial: bool = False) -> Dict[str, Any]:
        """
        Process a user input through the Re-Act cycle.
        
        Args:
            user_input: User's input text
            is_initial: Whether this is the initial request in a conversation
            
        Returns:
            Response including agent's reply and any tool execution results
        """
        self.turn_count += 1
        
        # 1. Add user input to conversation history
        user_message = {
            "role": "user",
            "message": user_input,
            "type": "initial" if is_initial else "follow_up"
        }
        self.conversation_history.append(user_message)
        
        # 2. REASON: Analyze what tools might be needed and why
        reasoning_result = self._generate_reasoning(user_input)
        
        # Store the reasoning for reference
        reasoning = reasoning_result.get("reasoning", "")
        
        # Get potential tool calls from reasoning
        potential_tool_calls = reasoning_result.get("tool_calls", [])
        
        # Convert to ToolCall objects
        tool_calls = []
        for tc_result in potential_tool_calls:
            tool_name = tc_result.get("tool_name", "")
            arguments = tc_result.get("arguments", {})
            
            tool_call = ToolCall(tool_name, arguments)
            tool_calls.append(tool_call)
        
        # Calculate uncertainty
        overall_certainty, _ = self.uncertainty_calculator.calculate_sequence_certainty(tool_calls)
        
        # 3. Determine if clarification is needed
        certainty_threshold = self.config.get("certainty_threshold", 0.9)
        
        if overall_certainty < certainty_threshold:
            # Generate candidate questions
            candidate_questions = self.question_generator.generate_candidate_questions(
                user_query=user_input,
                tool_calls=tool_calls,
                max_questions=self.config.get("max_candidates", 5)
            )
            
            # Evaluate questions
            best_question, eval_metrics = self.question_generator.evaluate_questions(
                questions=candidate_questions,
                tool_calls=tool_calls,
                base_threshold=self.config.get("base_threshold", 0.1),
                certainty_threshold=certainty_threshold
            )
            
            # Store question metrics for evaluation
            if candidate_questions:
                for q in candidate_questions:
                    self.question_history.append(q.to_dict())
            
            # If we have a good question, ask it
            if best_question:
                # Construct agent response with question
                agent_message = {
                    "role": "agent",
                    "message": best_question.question_text,
                    "type": "clarification"
                }
                self.conversation_history.append(agent_message)
                
                # Return response with the clarification question
                return {
                    "agent_message": agent_message,
                    "requires_clarification": True,
                    "potential_tool_calls": [tc.to_dict() for tc in tool_calls],
                    "certainty": overall_certainty,
                    "reasoning": reasoning
                }
        
        # 4. ACT: Execute appropriate tool calls
        execution_results = self.tool_executor.execute_tool_calls(tool_calls)
        
        # Track the tool calls and results
        self.all_tool_calls.extend(tool_calls)
        self.all_execution_results.extend(execution_results)
        
        # Check if all executions were successful
        all_succeeded = all(result.success for result in execution_results)
        
        # 5. Generate response summarizing actions and results
        response_text = self._generate_response(tool_calls, execution_results, reasoning)
        
        # 6. Add agent response to conversation history
        agent_message = {
            "role": "agent",
            "message": response_text,
            "type": "action_response"
        }
        self.conversation_history.append(agent_message)
        
        # Return the results
        return {
            "agent_message": agent_message,
            "tool_calls": [tc.to_dict() for tc in tool_calls],
            "execution_results": [result.to_dict() for result in execution_results],
            "requires_clarification": False,
            "success": all_succeeded,
            "certainty": overall_certainty,
            "reasoning": reasoning
        }
    
    def process_clarification_response(self, user_response: str, previous_tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process a user's response to a clarification question.
        
        Args:
            user_response: User's response text
            previous_tool_calls: Previous tool calls as dictionaries
            
        Returns:
            Response including agent's reply and any tool execution results
        """
        # Add user response to conversation history
        user_message = {
            "role": "user",
            "message": user_response,
            "type": "clarification_response"
        }
        self.conversation_history.append(user_message)
        
        # Convert previous tool calls back to ToolCall objects
        tool_calls = []
        for tc_dict in previous_tool_calls:
            tool_name = tc_dict.get("tool_name", "")
            arguments = tc_dict.get("arguments", {})
            
            tool_call = ToolCall(tool_name, arguments)
            tool_calls.append(tool_call)
        
        # Get the last clarification question
        last_question = None
        for message in reversed(self.conversation_history):
            if message.get("type") == "clarification" and message.get("role") == "agent":
                last_question = message.get("message", "")
                break
        
        # Create a dummy ClarificationQuestion object to process the response
        from core.question_generation import ClarificationQuestion
        question = ClarificationQuestion(
            question_id="q_temp",
            question_text=last_question,
            target_args=[]  # This is incomplete but will be handled by process_user_response
        )
        
        # Process the clarification response
        updated_tool_calls = self.question_generator.process_user_response(
            question=question,
            user_response=user_response,
            tool_calls=tool_calls
        )
        
        # Now continue with execution
        execution_results = self.tool_executor.execute_tool_calls(updated_tool_calls)
        
        # Track the tool calls and results
        self.all_tool_calls.extend(updated_tool_calls)
        self.all_execution_results.extend(execution_results)
        
        # Check if all executions were successful
        all_succeeded = all(result.success for result in execution_results)
        
        # Generate response based on execution results
        reasoning = "Based on your clarification, I've updated my understanding."
        response_text = self._generate_response(updated_tool_calls, execution_results, reasoning)
        
        # Add agent response to conversation history
        agent_message = {
            "role": "agent",
            "message": response_text,
            "type": "action_response"
        }
        self.conversation_history.append(agent_message)
        
        # Return the results
        return {
            "agent_message": agent_message,
            "tool_calls": [tc.to_dict() for tc in updated_tool_calls],
            "execution_results": [result.to_dict() for result in execution_results],
            "requires_clarification": False,
            "success": all_succeeded
        }
    
    def _generate_reasoning(self, user_input: str) -> Dict[str, Any]:
        """
        Generate reasoning about what tools might be needed.
        
        Args:
            user_input: Current user query
            
        Returns:
            Dictionary with reasoning and potential tool calls
        """
        # Get formatted conversation history
        formatted_history = self._format_conversation_history()
        
        # Get tool descriptions
        tool_descriptions = self.tool_registry.get_tool_descriptions()
        
        # Create prompt for reasoning
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing the appropriate tool calls.

Conversation history:
{formatted_history}

Current user query: "{user_input}"

Available tools:
{tool_descriptions}

Please reason step-by-step about what the user is asking for:
1. What is the user trying to accomplish?
2. What information do we already have from the conversation history?
3. What tools would help accomplish this task?
4. What parameters are needed for each tool?
5. Do we have enough information to execute these tools, or do we need to ask clarifying questions?

Think carefully about each step before proceeding to the next one.

After your reasoning, select the appropriate tool(s) to call.

Tool calls should be formatted as:
{{
  "tool_name": "name_of_tool",
  "arguments": {{
    "arg1": "value1",
    "arg2": "<UNK>" if uncertain
  }}
}}

Return your response as a JSON object with the following structure:
{{
  "reasoning": "Your step-by-step reasoning about what tools to use and why",
  "tool_calls": [
    {{
      "tool_name": "name_of_tool",
      "arguments": {{
        "arg1": "value1",
        "arg2": "<UNK>"
      }}
    }}
  ]
}}
"""
        
        # Call LLM to generate reasoning
        response = self.llm.generate_json(
            prompt=prompt,
            response_model={
                "reasoning": "string",
                "tool_calls": [
                    {
                        "tool_name": "string",
                        "arguments": {}
                    }
                ]
            },
            max_tokens=2000
        )
        
        return response
    
    def _generate_response(self, tool_calls: List[ToolCall], execution_results: List[Any], reasoning: str) -> str:
        """
        Generate a response based on tool execution results.
        
        Args:
            tool_calls: List of tool calls that were executed
            execution_results: Results of tool execution
            reasoning: Reasoning that led to the tool calls
            
        Returns:
            Formatted response text
        """
        # Check if this is the last expected action based on conversation flow
        is_last_expected_action = self._is_likely_last_action()
        
        # Create a prompt for response generation
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing tool calls.

Conversation history:
{self._format_conversation_history()}

Your reasoning about the user's request:
{reasoning}

Tool calls you executed:
{[tc.to_dict() for tc in tool_calls]}

Execution results:
{[result.to_dict() for result in execution_results]}

Create a helpful, natural, and informative response to the user that explains:
1. What you understood their request to be
2. What actions you took to fulfill the request
3. The results of those actions
4. If there were any issues, explain them clearly

{"Since this appears to be the completion of what the user wanted, also indicate that you've completed their request and ask if there's anything else they need help with." if is_last_expected_action else ""}

Your response should be conversational and user-friendly, not overly technical.
"""
        
        # Call LLM to generate response
        response = self.llm.generate_text(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.strip()
        
    
    def _format_conversation_history(self) -> str:
        """Format conversation history for inclusion in prompts."""
        if not self.conversation_history:
            return "No prior conversation."
            
        formatted = []
        for turn in self.conversation_history:
            role = turn.get("role", "unknown")
            message = turn.get("message", "")
            
            formatted.append(f"{role.capitalize()}: {message}")
        
        return "\n".join(formatted)
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the current conversation history."""
        return self.conversation_history
    
    def should_end_conversation(self) -> bool:
        """Determine if the conversation should end based on the current state."""
        # Check explicit end flag
        if self.should_end_flag:
            return True
            
        # Check if we've reached a natural conclusion based on the last few messages
        if len(self.conversation_history) >= 2:
            last_message = self.conversation_history[-1]
            if last_message.get("role") == "agent":
                content = last_message.get("message", "").lower()
                # Check for completion phrases
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
                if any(phrase in content for phrase in completion_phrases):
                    # This is a heuristic - the agent has indicated completion
                    return True
        
        # Otherwise, conversation should continue
        return False
        
    def _is_likely_last_action(self) -> bool:
        """
        Determine if the current action is likely the last one based on conversation flow.
        
        Returns:
            True if this appears to be the last expected action, False otherwise
        """
        # If we have very few turns, probably not the end yet
        if len(self.conversation_history) < 3:
            return False
            
        # Count how many tool executions we've done
        action_count = 0
        for turn in self.conversation_history:
            if turn.get("role") == "agent" and turn.get("type") == "action_response":
                action_count += 1
                
        # If we've already done multiple actions, more likely to be wrapping up
        if action_count >= 2:
            return True
            
        # Check if the last user message suggests completion
        user_messages = [turn for turn in self.conversation_history if turn.get("role") == "user"]
        if user_messages:
            last_user_message = user_messages[-1].get("message", "").lower()
            completion_indicators = ["that's all", "that's it", "that's what i needed", "thank you"]
            if any(indicator in last_user_message for indicator in completion_indicators):
                return True
                
        return False
    
    def get_all_tool_calls(self) -> List[Dict[str, Any]]:
        """Get all tool calls made during the conversation."""
        return [tc.to_dict() for tc in self.all_tool_calls]
    
    def get_all_execution_results(self) -> List[Dict[str, Any]]:
        """Get all execution results from the conversation."""
        return [result.to_dict() for result in self.all_execution_results]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics about the conversation."""
        return {
            "turn_count": self.turn_count,
            "tool_call_count": len(self.all_tool_calls),
            "question_count": len(self.question_history),
            "successful_execution_count": sum(1 for result in self.all_execution_results if result.success)
        }