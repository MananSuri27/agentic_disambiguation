from typing import Dict, List, Any, Tuple, Optional
import logging
import copy
from core.tool_registry import ToolRegistry
from core.uncertainty import ToolCall, UncertaintyCalculator
from core.question_generation import QuestionGenerator, ClarificationQuestion
from core.tool_executor import ToolExecutor, ToolExecutionResult
from core.plugin_manager import PluginManager
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)

class AgentContext:
    """Class for maintaining state across recursive ReAct cycles."""
    
    def __init__(self):
        """Initialize an empty agent context."""
        self.tool_calls = []  # Current planned tool calls
        self.conversation_history = []  # Conversation history
        self.current_reasoning = ""  # Latest reasoning
        self.all_reasoning_history = []  # Track all reasoning outputs
        self.turn_count = 0  # Track conversation turns
        self.last_question = None  # Last clarification question asked
        self.should_end_flag = False  # Flag to indicate if conversation should end
        self.executed_tool_calls = set()  # Set of tool calls that have been executed (to prevent duplication)
        self.current_task_complete = False  # Flag to track if the current task is complete
        
        # Track all tool call attempts (both succeeded and failed)
        self.all_tool_call_attempts = []


class ReactAgent:
    """
    An agent that implements the ReAct (Reason-Act-Observe) loop for tool use,
    with information-seeking clarification questions.
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
        Initialize a ReAct agent.
        
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
        
        # Initialize agent context
        self.context = AgentContext()
        
        # Track all tool calls and execution results for backward compatibility
        self.all_tool_calls = []
        self.all_execution_results = []
        
        # Track question history for backward compatibility
        self.question_history = []
        
    def process_user_input(self, user_input: str, is_initial: bool = False) -> Dict[str, Any]:
        """
        Process a user input through the ReAct cycle.
        
        Args:
            user_input: User's input text
            is_initial: Whether this is the initial request in a conversation
            
        Returns:
            Response including agent's reply and any tool execution results
        """
        logger.info(f"Processing user input: '{user_input}', is_initial={is_initial}")
        self.context.turn_count += 1
        
        # For new tasks, reset the task completion flag
        self.context.current_task_complete = False
        
        # Add user input to conversation history
        user_message = {
            "role": "user",
            "message": user_input,
            "type": "initial" if is_initial else "follow_up"
        }
        self.context.conversation_history.append(user_message)
        
        # Start the ReAct cycle
        return self._react_cycle(user_input)
    
    def _react_cycle(self, user_input: str) -> Dict[str, Any]:
        """
        The main ReAct cycle.
        
        Args:
            user_input: User's input text
            
        Returns:
            Response including agent's reply and any tool execution results
        """
        logger.debug(f"Starting ReAct cycle with user_input: '{user_input}'")
        
        # REASON phase - analyze what tools are needed
        tool_calls, reasoning = self._reason(user_input)
        self.context.current_reasoning = reasoning
        self.context.all_reasoning_history.append({
            "turn": self.context.turn_count,
            "user_input": user_input,
            "reasoning": reasoning
        })
        self.context.tool_calls = tool_calls
        
        logger.info(f"Reasoning complete. Tool calls planned: {len(tool_calls)}")
        for tc in tool_calls:
            logger.debug(f"  - Tool: {tc.tool_name}, Args: {tc.arguments}")
            
        # If no tool calls were identified, log a warning and return a proper response
        if not tool_calls:
            logger.warning(f"No tool calls identified for input: '{user_input}'")
            return {
                "agent_message": {
                    "role": "agent",
                    "message": "I don't have the right tools to process your request. Could you please provide more details or try a different request?",
                    "type": "error_response"
                },
                "tool_calls": [],
                "execution_results": [],
                "reasoning": reasoning,
                "all_reasoning_history": self.context.all_reasoning_history,
                "requires_clarification": False,
                "success": False,
                "conversation_status": "awaiting_clarification",
                "all_tool_call_attempts": self.context.all_tool_call_attempts,
                "all_candidate_questions": self.question_generator.get_all_candidate_questions()
            }
        
        # Calculate uncertainty
        overall_certainty, arg_certainties = self.uncertainty_calculator.calculate_sequence_certainty(tool_calls)
        logger.info(f"Overall certainty: {overall_certainty:.4f}")
        
        # If high uncertainty, use EXISTING question generator and evaluation system
        certainty_threshold = self.config.get("certainty_threshold", 0.9)
        if overall_certainty < certainty_threshold:
            logger.info(f"Certainty {overall_certainty:.4f} below threshold {certainty_threshold}, generating clarification questions")
            
            # Generate candidate questions using EXISTING question generator
            candidate_questions = self.question_generator.generate_candidate_questions(
                user_query=user_input,
                tool_calls=tool_calls,
                max_questions=self.config.get("max_candidates", 5),
                conversation_history=self.context.conversation_history
            )
            
            logger.info(f"Generated {len(candidate_questions)} candidate questions")
            
            # Evaluate questions using EXISTING evaluation system
            best_question, eval_metrics = self.question_generator.evaluate_questions(
                questions=candidate_questions,
                tool_calls=tool_calls,
                base_threshold=self.config.get("base_threshold", 0.1),
                certainty_threshold=certainty_threshold
            )
            
            # If we have a good question, ask it
            if best_question:
                logger.info(f"Selected question: '{best_question.question_text}'")
                return self._ask_clarification_question(best_question)
            else:
                logger.info("No question selected, proceeding with execution despite uncertainty")
        
        # ACT phase - execute tools
        logger.info("Executing tool calls")
        
        # Create a unique signature for each tool call to prevent duplicate execution
        new_tool_calls = []
        duplicate_calls = []
        for tc in tool_calls:
            tc_signature = f"{tc.tool_name}:{sorted([(k, v) for k, v in tc.arguments.items()])}"
            if tc_signature not in self.context.executed_tool_calls:
                new_tool_calls.append(tc)
                self.context.executed_tool_calls.add(tc_signature)
                # Add to the context's all tool call attempts
                self.context.all_tool_call_attempts.append({
                    "tool_call": tc.to_dict(),
                    "was_executed": True,
                    "reason": "new tool call"
                })
            else:
                logger.warning(f"Skipping duplicate tool call: {tc.tool_name}")
                duplicate_calls.append(tc)
                # Add to the context's all tool call attempts
                self.context.all_tool_call_attempts.append({
                    "tool_call": tc.to_dict(),
                    "was_executed": False,
                    "reason": "duplicate"
                })
                
        # If no new tool calls, log a warning and return a response indicating this
        if not new_tool_calls and tool_calls:
            logger.warning("No new tool calls to execute - all were duplicates")
            return {
                "agent_message": {
                    "role": "agent",
                    "message": "I've already processed this request previously. Did you want me to try something different?",
                    "type": "action_response"
                },
                "tool_calls": [tc.to_dict() for tc in duplicate_calls],
                "execution_results": [],
                "reasoning": reasoning,
                "all_reasoning_history": self.context.all_reasoning_history,
                "requires_clarification": False,
                "success": True,
                "conversation_status": "awaiting_further_requests",
                "all_tool_call_attempts": self.context.all_tool_call_attempts,
                "all_candidate_questions": self.question_generator.get_all_candidate_questions()
            }
        
        # Execute the new tool calls (or none if empty list)
        execution_results = self.tool_executor.execute_tool_calls(new_tool_calls)

        # Record execution results in all_tool_call_attempts
        for i, result in enumerate(execution_results):
            if i < len(new_tool_calls):
                # Find the corresponding tool call attempt
                for attempt in self.context.all_tool_call_attempts:
                    if attempt["was_executed"] and attempt["tool_call"]["tool_name"] == result.tool_name:
                        # Add execution result to this attempt
                        attempt["execution_result"] = result.to_dict()
                        attempt["success"] = result.success
                        break
                
            # OBSERVE phase - process results
            logger.info("Processing execution results")
            observation_results = self._observe(execution_results)
            
            # Add execution results to tracking
            self.all_tool_calls.extend(new_tool_calls)
            self.all_execution_results.extend(execution_results)
            
            # If there were failures that need clarification
            if observation_results.get("needs_clarification", False):
                logger.info("Tool execution failed, needs clarification from user")
                return self._handle_tool_failures_with_clarification(observation_results["failures"])
            
            # Set the task completion flag
            self.context.current_task_complete = True
            
            # Generate response based on execution results
            logger.info("Task complete, generating response")
            return self._generate_response(observation_results)
        
    def _reason(self, user_input: str) -> Tuple[List[ToolCall], str]:
        """
        Reasoning phase: determine what tools to use.
        
        Args:
            user_input: User's input text
            
        Returns:
            Tuple of (tool calls, reasoning)
        """
        logger.debug("Generating reasoning prompt")
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing the appropriate tool calls.

Conversation history:
{self._format_conversation_history()}

Current user query: "{user_input}"

Available tools:
{self.tool_registry.get_tool_descriptions()}

Please reason step-by-step about what the user is asking for:
1. What is the user trying to accomplish?
2. What information do we already have from the conversation history?
3. What tools would help accomplish this task?
4. What parameters are needed for each tool?
5. Do we have enough information to execute these tools, or do we need to ask clarifying questions?

Think carefully about each step before proceeding to the next one.

**IMPORTANT: YOU MUST USE <UNK> AS THE VALUE FOR ANY PARAMETER THAT IS NOT EXPLICITLY MENTIONED OR CLEAR FROM THE USER'S REQUEST. DO NOT GUESS VALUES.**

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
        
        # Extract reasoning and tool calls
        reasoning = response.get("reasoning", "")
        tool_calls_data = response.get("tool_calls", [])
        
        # Convert to ToolCall objects
        tool_calls = []
        for tc_data in tool_calls_data:
            tool_name = tc_data.get("tool_name", "")
            arguments = tc_data.get("arguments", {})
            
            if tool_name:
                tool_call = ToolCall(tool_name, arguments)
                tool_calls.append(tool_call)
        
        return tool_calls, reasoning
    
    def _act(self, tool_calls: List[ToolCall]) -> List[ToolExecutionResult]:
        """
        Acting phase: execute tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of execution results
        """
        # Execute each tool call
        execution_results = self.tool_executor.execute_tool_calls(tool_calls)
        
        # Log execution results
        for result in execution_results:
            if result.success:
                logger.info(f"Successfully executed {result.tool_name}")
            else:
                logger.warning(f"Failed to execute {result.tool_name}: {result.error}")
        
        return execution_results
    
    def _observe(self, execution_results: List[ToolExecutionResult]) -> Dict[str, Any]:
        """
        Observation phase: process execution results.
        
        Args:
            execution_results: Results of tool execution
            
        Returns:
            Observation results with categorization of successes and failures
        """
        # Initialize observation results
        observation_results = {
            "all_succeeded": True,
            "successes": [],
            "failures": [],
            "needs_clarification": False,
            "all_results": execution_results
        }
        
        # Process each execution result
        for result in execution_results:
            if result.success:
                # Add successful result
                observation_results["successes"].append(result)
            else:
                # Add failed result
                observation_results["failures"].append(result)
                observation_results["all_succeeded"] = False
                
                # Check for validation failures or missing parameters - these ALWAYS need clarification
                if (result.error in ["MISSING_PARAMS", "INVALID_PARAM_VALUE"] or 
                    "validation failed" in result.message.lower() or 
                    "required argument" in result.message.lower() or
                    "unknown value" in result.message.lower()):
                    observation_results["needs_clarification"] = True
                else:
                    # For other errors, we might not need clarification
                    # But for simplicity, we'll still mark all failures as needing clarification
                    observation_results["needs_clarification"] = True
        
        return observation_results
    
    def _ask_clarification_question(self, question: ClarificationQuestion) -> Dict[str, Any]:
        """
        Ask a clarification question using the existing system.
        
        Args:
            question: The clarification question to ask
            
        Returns:
            Response structure
        """
        # Update the question tracking
        self.question_generator.update_arg_clarification_counts(question)
        self.context.last_question = question
        
        # Add to question history for tracking
        self.question_history.append(question.to_dict())
        
        # Construct agent response with question
        agent_message = {
            "role": "agent",
            "message": question.question_text,
            "type": "clarification"
        }
        
        # We do NOT add the message to conversation history here
        # This is now the responsibility of main.py to avoid duplication
        
        logger.info(f"Asking clarification question: '{question.question_text}'")
        
        # Return response with the clarification question and explicit conversation status
        return {
            "agent_message": agent_message,
            "requires_clarification": True,
            "potential_tool_calls": [tc.to_dict() for tc in self.context.tool_calls],
            "reasoning": self.context.current_reasoning,
            "all_reasoning_history": self.context.all_reasoning_history,
            "conversation_status": "awaiting_clarification",
            "all_tool_call_attempts": self.context.all_tool_call_attempts,
            "all_candidate_questions": self.question_generator.get_all_candidate_questions()
        }
            
    def _handle_tool_failures_with_clarification(self, failures: List[ToolExecutionResult]) -> Dict[str, Any]:
        """
        Handle tool failures by asking clarification using existing system.
        
        Args:
            failures: List of failed tool executions
            
        Returns:
            Response structure
        """
        logger.info("Handling tool failures with clarification")
        
        # Use the tool_executor's generate_error_clarification method
        error_result = failures[0]  # Take the first failure
        
        # Extract the full conversation history for context
        last_user_message = ""
        for turn in reversed(self.context.conversation_history):
            if turn.get("role") == "user":
                last_user_message = turn.get("message", "")
                break
        
        # Generate a clarification question based on the error
        prompt = f"""
You are an AI assistant helping a user with a task.

The user is trying to perform an operation, but there was an error:
Tool: {error_result.tool_name}
Error: {error_result.error}
Message: {error_result.message}

Based on this error, generate a natural, conversational clarification question 
to ask the user to get the information needed to fix the error.

Your question should be specific, helpful, and focus on resolving the error.
"""
        
        # Generate clarification question
        clarification_question = self.llm.generate_text(
            prompt=prompt,
            max_tokens=200,
            temperature=0.4
        ).strip()
        
        # Update tool calls - use original tool calls for now
        updated_tool_calls = self.context.tool_calls
        
        # If we generated a clarification question, use it
        if clarification_question:
            # Create a dummy ClarificationQuestion object
            question = ClarificationQuestion(
                question_id=f"error_q_{len(self.question_history)}",
                question_text=clarification_question,
                target_args=[]  # This is simplified but works
            )
            
            # Update context with the fixed tool calls
            self.context.tool_calls = updated_tool_calls
            
            # Use our existing clarification asking mechanism
            return self._ask_clarification_question(question)
        
        # If no clarification question generated, generate a generic response about the failure
        logger.info("No clarification question generated, reporting failure")
        
        # Generate a simple response about the failure
        response_text = f"I wasn't able to {error_result.tool_name} because: {error_result.message}. Can you provide more information?"
        
        # Construct agent response with failure message
        agent_message = {
            "role": "agent",
            "message": response_text,
            "type": "action_response"
        }
        
        # We do NOT add the message to conversation history here
        # This is now the responsibility of main.py to avoid duplication
        
        # Return the results with explicit conversation status
        return {
            "agent_message": agent_message,
            "tool_calls": [tc.to_dict() for tc in self.context.tool_calls],
            "execution_results": [result.to_dict() for result in failures],
            "requires_clarification": False,
            "success": False,
            "reasoning": self.context.current_reasoning,
            "all_reasoning_history": self.context.all_reasoning_history,
            "conversation_status": "awaiting_clarification",  # Still need clarification even though not using formal mechanism
            "all_tool_call_attempts": self.context.all_tool_call_attempts,
            "all_candidate_questions": self.question_generator.get_all_candidate_questions()
        }
    
    def _generate_error_resolution(self, error_result: ToolExecutionResult, user_query: str) -> Tuple[str, List[ToolCall]]:
        """
        Use LLM to generate a better error resolution strategy.
        
        Args:
            error_result: The error from tool execution
            user_query: Original user query
            
        Returns:
            Tuple of (clarification question, updated tool calls)
        """
        # Create a prompt for the LLM to reason about the error and suggest fixes
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing tool calls.

Conversation history:
{self._format_conversation_history()}

A tool execution failed with the following error:
Tool: {error_result.tool_name}
Error Type: {error_result.error}
Error Message: {error_result.message}

Current tool calls:
{[tc.to_dict() for tc in self.context.tool_calls]}

Please reason about this error by answering these questions:
1. What is the root cause of this error?
2. Is this due to missing information from the user, invalid input, or a system limitation?
3. Can I infer the correct parameters from the conversation history?
4. Should I ask the user for clarification, and if so, what exactly should I ask?

Based on your reasoning, provide:
1. A natural, conversational clarification question to ask the user (if needed)
2. Updated tool calls that might fix the issue (if you can infer the solution)

Return your response as a JSON object with the following structure:
{{
  "reasoning": "Your step-by-step reasoning about the error",
  "clarification_question": "Question to ask the user, or null if not needed",
  "updated_tool_calls": [
    {{
      "tool_name": "name_of_tool",
      "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
      }}
    }}
  ]
}}
"""
        
        # Call LLM to generate error resolution
        response = self.llm.generate_json(
            prompt=prompt,
            response_model={
                "reasoning": "string",
                "clarification_question": "string",
                "updated_tool_calls": [
                    {
                        "tool_name": "string",
                        "arguments": {}
                    }
                ]
            },
            max_tokens=2000
        )
        
        # Extract the clarification question and updated tool calls
        clarification_question = response.get("clarification_question", "")
        updated_tool_calls_data = response.get("updated_tool_calls", [])
        
        # Convert to ToolCall objects
        updated_tool_calls = []
        for tc_data in updated_tool_calls_data:
            tool_name = tc_data.get("tool_name", "")
            arguments = tc_data.get("arguments", {})
            
            if tool_name:
                tool_call = ToolCall(tool_name, arguments)
                updated_tool_calls.append(tool_call)
        
        # If no updated tool calls were provided, keep the original ones
        if not updated_tool_calls:
            updated_tool_calls = self.context.tool_calls
        
        return clarification_question, updated_tool_calls
    
    def _generate_response(self, observation_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a simple response based on observations.
        
        Args:
            observation_results: Results from observation phase
            
        Returns:
            Response structure
        """
        # Get successful tool executions
        successful_executions = observation_results.get("successes", [])
        all_results = observation_results.get("all_results", [])
        failures = observation_results.get("failures", [])
        all_succeeded = observation_results.get("all_succeeded", False)
        
        logger.info(f"Generating response for {len(successful_executions)} successful and {len(failures)} failed executions")
        
        # If no executions happened at all, be explicit about it
        if not all_results:
            response_text = "I wasn't able to process your request. No tools were executed."
            agent_message = {
                "role": "agent",
                "message": response_text,
                "type": "error_response"  # New type for clarity
            }
            return {
                "agent_message": agent_message,
                "tool_calls": [],
                "execution_results": [],
                "requires_clarification": False,
                "success": False,
                "reasoning": self.context.current_reasoning,
                "all_reasoning_history": self.context.all_reasoning_history,
                "conversation_status": "awaiting_clarification",
                "all_tool_call_attempts": self.context.all_tool_call_attempts,
                "all_candidate_questions": self.question_generator.get_all_candidate_questions()
            }
        
        # Build a simple response
        response_parts = []
        
        # Add success messages with output
        for execution in successful_executions:
            tool_name = execution.tool_name
            
            # Format the output to include in the response
            output_str = ""
            if hasattr(execution, 'output') and execution.output:
                # Use a simple representation of the output
                if isinstance(execution.output, dict):
                    # Format dictionary output more cleanly
                    output_items = []
                    for k, v in execution.output.items():
                        if k != 'tool_name' and k != 'parameters':  # Skip redundant info
                            output_items.append(f"{k}: {v}")
                    if output_items:
                        output_str = f" Output: {', '.join(output_items)}."
                else:
                    # For non-dictionary outputs
                    output_str = f" Output: {execution.output}."
            
            # Include the message from the execution
            tool_message = execution.message if hasattr(execution, 'message') else ""
            
            # Simple generic template with output and message included
            response_parts.append(f"I've executed the {tool_name} operation successfully. {tool_message}{output_str}")
        
        # Add failure messages
        for execution in failures:
            tool_name = execution.tool_name
            error_message = execution.message
            # Simple generic template
            response_parts.append(f"I couldn't complete the {tool_name} operation: {error_message}.")
        
        # Combine all response parts
        response_text = " ".join(response_parts)
        
        # If no parts, use a generic response
        if not response_parts:
            response_text = "I've processed your request."
        
        # Add a question about whether there's anything else ONLY if the task is complete
        if self.context.current_task_complete:
            response_text += " Is there anything else you would like me to help you with?"
        
        # Construct agent response with success/failure message
        agent_message = {
            "role": "agent",
            "message": response_text,
            "type": "action_response"
        }
        
        # We do NOT add the message to conversation history here
        # This is now the responsibility of main.py to avoid duplication
        
        logger.info(f"Final response: '{response_text}'")
        
        # Return the results with explicit conversation status
        return {
            "agent_message": agent_message,
            "tool_calls": [tc.to_dict() for tc in self.context.tool_calls],
            "execution_results": [result.to_dict() for result in all_results],
            "requires_clarification": False,
            "success": all_succeeded,
            "reasoning": self.context.current_reasoning,
            "all_reasoning_history": self.context.all_reasoning_history,
            "conversation_status": "awaiting_further_requests",  # Signal that we're ready for new requests
            "all_tool_call_attempts": self.context.all_tool_call_attempts,
            "all_candidate_questions": self.question_generator.get_all_candidate_questions()
        }
    
    def process_clarification_response(self, user_response: str, previous_tool_calls: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process user's response to a clarification question.
        
        Args:
            user_response: User's response text
            previous_tool_calls: Optional previous tool calls as dictionaries (for backward compatibility)
            
        Returns:
            Response structure
        """
        logger.info(f"Processing clarification response: '{user_response}'")
        
        # Add user response to conversation history
        user_message = {
            "role": "user",
            "message": user_response,
            "type": "clarification_response"
        }
        self.context.conversation_history.append(user_message)
        
        # If previous_tool_calls is provided (backward compatibility), use it
        if previous_tool_calls is not None:
            # Convert to ToolCall objects
            tool_calls = []
            for tc_dict in previous_tool_calls:
                tool_name = tc_dict.get("tool_name", "")
                arguments = tc_dict.get("arguments", {})
                
                if tool_name:
                    tool_call = ToolCall(tool_name, arguments)
                    tool_calls.append(tool_call)
                    
            # Update context
            self.context.tool_calls = tool_calls
        
        # Process the clarification response using existing system
        updated_tool_calls = self.question_generator.process_user_response(
            question=self.context.last_question,
            user_response=user_response,
            tool_calls=self.context.tool_calls,
            conversation_history=self.context.conversation_history
        )
        
        logger.info(f"Updated tool calls after processing clarification response: {len(updated_tool_calls)}")
        
        # Update context with the resolved tool calls
        self.context.tool_calls = updated_tool_calls
        
        # ACT phase - execute tools with the updated information
        logger.info("Executing tool calls after clarification")
        
        # Create a unique signature for each tool call to prevent duplicate execution
        new_tool_calls = []
        duplicate_calls = []
        for tc in updated_tool_calls:
            tc_signature = f"{tc.tool_name}:{sorted([(k, v) for k, v in tc.arguments.items()])}"
            if tc_signature not in self.context.executed_tool_calls:
                new_tool_calls.append(tc)
                self.context.executed_tool_calls.add(tc_signature)
                # Add to the context's all tool call attempts
                self.context.all_tool_call_attempts.append({
                    "tool_call": tc.to_dict(),
                    "was_executed": True,
                    "reason": "new tool call after clarification"
                })
            else:
                logger.warning(f"Skipping duplicate tool call after clarification: {tc.tool_name}")
                duplicate_calls.append(tc)
                # Add to the context's all tool call attempts
                self.context.all_tool_call_attempts.append({
                    "tool_call": tc.to_dict(),
                    "was_executed": False,
                    "reason": "duplicate after clarification"
                })
        
        # If no new tool calls, just return a response
        if not new_tool_calls and updated_tool_calls:
            logger.warning("No new tool calls to execute after clarification")
            return {
                "agent_message": {
                    "role": "agent",
                    "message": "I've already processed a similar request. Did you want me to try something different?",
                    "type": "action_response"
                },
                "tool_calls": [tc.to_dict() for tc in duplicate_calls],
                "execution_results": [],
                "requires_clarification": False,
                "success": True,
                "reasoning": self.context.current_reasoning,
                "all_reasoning_history": self.context.all_reasoning_history,
                "conversation_status": "awaiting_further_requests",
                "all_tool_call_attempts": self.context.all_tool_call_attempts,
                "all_candidate_questions": self.question_generator.get_all_candidate_questions()
            }
        
        # Execute the new tool calls with updated information
        execution_results = self.tool_executor.execute_tool_calls(new_tool_calls)

        # Update all_tool_call_attempts with execution results
        for i, result in enumerate(execution_results):
            if i < len(new_tool_calls):
                # Find the corresponding tool call attempt
                for attempt in self.context.all_tool_call_attempts:
                    if attempt["was_executed"] and attempt["tool_call"]["tool_name"] == result.tool_name:
                        # Add execution result to this attempt
                        attempt["execution_result"] = result.to_dict()
                        attempt["success"] = result.success
                        break
        
        # OBSERVE phase - process results
        observation_results = self._observe(execution_results)
        
        # Add execution results to tracking
        self.all_tool_calls.extend(new_tool_calls)
        self.all_execution_results.extend(execution_results)
        
        # CRITICAL FIX: Check if there were failures that need clarification, just like in _react_cycle
        if observation_results.get("needs_clarification", False):
            logger.info("Tool execution failed after clarification, needs further clarification")
            return self._handle_tool_failures_with_clarification(observation_results["failures"])
        
        # Set the task completion flag if successful
        if observation_results.get("all_succeeded", False):
            self.context.current_task_complete = True
        
        # Generate response based on execution results
        return self._generate_response(observation_results)
    
    def _format_conversation_history(self) -> str:
        """Format conversation history for inclusion in prompts."""
        if not self.context.conversation_history:
            return "No prior conversation."
            
        formatted = []
        for turn in self.context.conversation_history:
            role = turn.get("role", "unknown")
            message = turn.get("message", "")
            
            formatted.append(f"{role.capitalize()}: {message}")
        
        return "\n".join(formatted)
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the current conversation history."""
        return self.context.conversation_history
    
    def should_end_conversation(self) -> bool:
        """Determine if the conversation should end based on the current state."""
        # We're using explicit signals now, so this is less important
        # Always return false and let main.py decide based on conversation_status
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
            "turn_count": self.context.turn_count,
            "tool_call_count": len(self.all_tool_calls),
            "successful_execution_count": sum(1 for result in self.all_execution_results if result.success),
            "question_count": len(self.question_history)
        }
    
    def get_all_tool_call_attempts(self) -> List[Dict[str, Any]]:
        """Get all tool call attempts (successful and failed)."""
        return self.context.all_tool_call_attempts