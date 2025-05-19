from typing import Dict, List, Any, Tuple, Optional
import logging
import copy
from dataclasses import dataclass
from core.tool_registry import ToolRegistry
from core.uncertainty import ToolCall, UncertaintyCalculator
from core.question_generation import QuestionGenerator, ClarificationQuestion
from core.tool_executor import ToolExecutor, ToolExecutionResult
from core.plugin_manager import PluginManager
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from agent execution."""
    success: bool
    message: str
    type: str = "completed"  # "completed", "clarification", "error"
    tool_calls: List[Dict] = None
    context: Dict = None
    question_obj: ClarificationQuestion = None
    
    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.context is None:
            self.context = {}


class StepTracker:
    """Tracks a single agentic step (reason -> disambiguate -> execute)."""
    
    def __init__(self, step_index: int):
        self.step_index = step_index
        self.reason_data = None
        self.disambiguation_data = None
        self.execution_data = None
    
    def record_reason(self, chain_of_thought: str, tool_call: ToolCall):
        self.reason_data = {
            "chain_of_thought": chain_of_thought,
            "selected_tool": {
                "name": tool_call.tool_name,
                "args": tool_call.arguments
            }
        }
    
    def record_disambiguation(self, disambiguation_result):
        """Record disambiguation attempt and results."""
        self.disambiguation_data = {
            "required": disambiguation_result.get("required", False),
            "certainty_score": disambiguation_result.get("certainty_score", 1.0),
            "candidates_generated": disambiguation_result.get("candidates_generated", 0),
            "selected_question": disambiguation_result.get("selected_question")
        }
    
    def record_execution(self, tool_call: ToolCall, result: ToolExecutionResult):
        self.execution_data = {
            "attempted": True,
            "tool_call": {"name": tool_call.tool_name, "args": tool_call.arguments},
            "result": result.to_dict(),
            "observation_added": result.message if result.success else f"Error: {result.message}"
        }
    
    def to_dict(self) -> Dict:
        return {
            "step_index": self.step_index,
            "reason": self.reason_data,
            "disambiguation": self.disambiguation_data,
            "tool_execution": self.execution_data
        }


class TurnTracker:
    """Tracks a single turn (user input -> agent response)."""
    
    def __init__(self, turn_index: int, enriched_request: str):
        self.turn_index = turn_index
        self.enriched_request = enriched_request
        self.steps = []
        self.turn_outcome = None
        self.user_response = None
    
    def start_new_step(self) -> StepTracker:
        step = StepTracker(len(self.steps))
        self.steps.append(step)
        return step
    
    def set_outcome(self, outcome: str):
        self.turn_outcome = outcome
    
    def set_user_response(self, clarification_text: str, response_type: str = "clarification"):
        self.user_response = {
            "clarification_text": clarification_text,
            "response_type": response_type
        }
    
    def to_dict(self) -> Dict:
        return {
            "turn_index": self.turn_index,
            "enriched_request": self.enriched_request,
            "agentic_steps": [step.to_dict() for step in self.steps],
            "turn_outcome": self.turn_outcome,
            "user_response": self.user_response
        }


class RequestTracker:
    """Tracks a single request (initial query or follow-up)."""
    
    def __init__(self, request_index: int, request_text: str, request_type: str):
        self.request_index = request_index
        self.request_text = request_text
        self.request_type = request_type  # "initial" or "follow_up"
        self.turns = []
        self.request_result = None
    
    def start_new_turn(self, enriched_request: str) -> TurnTracker:
        turn = TurnTracker(len(self.turns), enriched_request)
        self.turns.append(turn)
        return turn
    
    def set_result(self, success: bool, final_message: str, tool_calls_executed: List[Dict]):
        self.request_result = {
            "success": success,
            "final_message": final_message, 
            "tool_calls_executed": tool_calls_executed,
            "total_turns": len(self.turns),
            "total_steps": sum(len(turn.steps) for turn in self.turns)
        }
    
    def to_dict(self) -> Dict:
        return {
            "request_index": self.request_index,
            "request_text": self.request_text,
            "request_type": self.request_type,
            "turns": [turn.to_dict() for turn in self.turns],
            "request_result": self.request_result
        }


class ConversationTracker:
    """Tracks the full conversation with nested structure."""
    
    def __init__(self):
        self.requests = []
        self.current_request = None
    
    def start_new_request(self, text: str, request_type: str) -> RequestTracker:
        request = RequestTracker(len(self.requests), text, request_type)
        self.requests.append(request)
        self.current_request = request
        return request
    
    def export_full_structure(self) -> Dict:
        """Export the full nested structure."""
        total_turns = sum(len(req.turns) for req in self.requests)
        total_steps = sum(sum(len(turn.steps) for turn in req.turns) for req in self.requests)
        
        return {
            "requests": [req.to_dict() for req in self.requests],
            "metrics": {
                "total_requests": len(self.requests),
                "total_turns": total_turns,
                "total_steps": total_steps,
                "avg_turns_per_request": total_turns / len(self.requests) if self.requests else 0,
                "avg_steps_per_turn": total_steps / total_turns if total_turns else 0
            }
        }
    
    def export_compatibility_format(self) -> Dict:
        """Export flattened data for backward compatibility."""
        conversation = []
        questions = []
        all_candidate_questions = []
        final_tool_calls = []
        all_tool_call_attempts = []
        
        for req in self.requests:
            # Add initial user message
            conversation.append({
                "role": "user",
                "message": req.request_text,
                "type": req.request_type,
                "request_index": req.request_index,
                "turn_index": 0
            })
            
            for turn in req.turns:
                # Process each step in the turn
                for step in turn.steps:
                    # Record tool call attempts
                    if step.execution_data:
                        exec_data = step.execution_data
                        all_tool_call_attempts.append({
                            "tool_call": exec_data["tool_call"],
                            "was_executed": True,
                            "success": exec_data["result"]["success"],
                            "reason": "executed",
                            "execution_result": exec_data["result"],
                            "request_index": req.request_index,
                            "turn_index": turn.turn_index,
                            "step_index": step.step_index
                        })
                        
                        # Record successful tool calls
                        if exec_data["result"]["success"]:
                            final_tool_calls.append({
                                **exec_data["tool_call"],
                                "request_index": req.request_index,
                                "turn_index": turn.turn_index,
                                "step_index": step.step_index,
                                "success": True
                            })
                    
                    # Record questions
                    if step.disambiguation_data and step.disambiguation_data.get("selected_question"):
                        q_data = step.disambiguation_data["selected_question"]
                        questions.append({
                            **q_data,
                            "request_index": req.request_index,
                            "turn_index": turn.turn_index,
                            "step_index": step.step_index
                        })
                
                # Add agent response
                if turn.turn_outcome == "needs_clarification":
                    # Find the question from this turn
                    agent_message = "I need clarification."
                    for step in turn.steps:
                        if step.disambiguation_data and step.disambiguation_data.get("selected_question"):
                            agent_message = step.disambiguation_data["selected_question"]["question_text"]
                            break
                    
                    conversation.append({
                        "role": "agent",
                        "message": agent_message,
                        "type": "clarification",
                        "request_index": req.request_index,
                        "turn_index": turn.turn_index
                    })
                    
                    # Add user clarification if provided
                    if turn.user_response:
                        conversation.append({
                            "role": "user",
                            "message": turn.user_response["clarification_text"],
                            "type": "clarification_response",
                            "request_index": req.request_index,
                            "turn_index": turn.turn_index
                        })
                elif turn.turn_outcome == "completed":
                    # Add final agent response
                    conversation.append({
                        "role": "agent",
                        "message": req.request_result["final_message"] if req.request_result else "Completed",
                        "type": "action_response",
                        "request_index": req.request_index,
                        "turn_index": turn.turn_index
                    })
        
        return {
            "conversation": conversation,
            "questions": questions,
            "all_candidate_questions": all_candidate_questions,
            "final_tool_calls": final_tool_calls,
            "all_tool_call_attempts": all_tool_call_attempts
        }


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
        """Initialize a ReAct agent."""
        self.llm = llm_provider
        self.tool_registry = tool_registry
        self.uncertainty_calculator = uncertainty_calculator
        self.question_generator = question_generator
        self.tool_executor = tool_executor
        self.plugin_manager = plugin_manager
        self.config = config or {}
        self.max_steps = self.config.get("max_steps", 10)
        
        # Add final_answer as virtual tool
        self._add_final_answer_tool()
        
        # Initialize conversation tracker
        self.conversation_tracker = ConversationTracker()
    
    def _add_final_answer_tool(self):
        """Add final_answer as a virtual tool to base plugin."""
        try:
            # Find base plugin or create one
            base_plugin = None
            for plugin in self.plugin_manager.plugins.values():
                if hasattr(plugin, '_add_virtual_tool'):
                    base_plugin = plugin
                    break
            
            if base_plugin:
                base_plugin._add_virtual_tool({
                    "name": "final_answer",
                    "description": "Provide final answer to the user and complete the task",
                    "arguments": [
                        {
                            "name": "answer",
                            "description": "The final answer to provide to the user",
                            "domain": {"type": "string", "importance": 1.0},
                            "required": True
                        }
                    ]
                })
                logger.info("Added final_answer virtual tool")
        except Exception as e:
            logger.warning(f"Could not add final_answer virtual tool: {e}")
    
    def run(self, request: str, context: Dict = None) -> AgentResult:
        """
        Execute the ReAct loop for a single request.
        
        Args:
            request: The enriched request (including clarifications)
            context: Context including observations that persist during clarifications
            
        Returns:
            AgentResult indicating success, need for clarification, or error
        """
        context = context or {"observations": []}
        observations = context["observations"]
        
        # Start tracking this turn
        turn_tracker = self.conversation_tracker.current_request.start_new_turn(request)
        
        for step in range(self.max_steps):
            step_tracker = turn_tracker.start_new_step()
            
            # REASON phase
            chain_of_thought, tool_call = self._reason(request, observations)
            step_tracker.record_reason(chain_of_thought, tool_call)
            
            # DISAMBIGUATION phase - use existing sophisticated strategy
            disambiguation_result = self._handle_disambiguation([tool_call], request)
            step_tracker.record_disambiguation(disambiguation_result)
            
            if disambiguation_result["needs_clarification"]:
                turn_tracker.set_outcome("needs_clarification")
                return AgentResult(
                    success=False,
                    message=disambiguation_result["question"],
                    type="clarification",
                    question_obj=disambiguation_result["question_obj"]
                )
            
            # ACT phase
            execution_result = self.tool_executor.execute_tool_call(tool_call)
            step_tracker.record_execution(tool_call, execution_result)
            
            # ERROR HANDLING
            if not execution_result.success:
                error_action = self._handle_error(execution_result, request, context)
                if error_action["needs_clarification"]:
                    turn_tracker.set_outcome("needs_clarification")
                    return AgentResult(
                        success=False,
                        message=error_action["question"],
                        type="error_clarification"
                    )
                else:
                    observations.append(error_action["observation"])
                    continue
            
            # SUCCESS - check if this is final answer
            if tool_call.tool_name == "final_answer":
                turn_tracker.set_outcome("completed")
                return AgentResult(
                    success=True,
                    message=tool_call.arguments.get("answer", execution_result.message),
                    type="completed",
                    context=context
                )
            
            # Continue with next step
            observations.append(execution_result.message)
            context["observations"] = observations
        
        # Max steps reached
        turn_tracker.set_outcome("completed")
        return AgentResult(
            success=True,
            message="Task completed (max steps reached)",
            type="completed",
            context=context
        )
    
    def _reason(self, request: str, observations: List[str]) -> Tuple[str, ToolCall]:
        """Reason about what tool to use next."""
        # Build simple reasoning prompt
        obs_text = "\n".join(f"- {obs}" for obs in observations) if observations else "None"
        
        prompt = f"""You are an AI assistant helping with a user request.

Request: {request}

Previous observations:
{obs_text}

Available tools:
{self.tool_registry.get_tool_descriptions()}

Think step by step about what tool to use next. If you have enough information to provide a final answer, use the final_answer tool.

Respond in JSON format:
{{
    "reasoning": "Your step-by-step thinking",
    "tool_call": {{
        "tool_name": "name_of_tool",
        "arguments": {{
            "arg1": "value1",
            "arg2": "value2"
        }}
    }}
}}
"""
        
        response = self.llm.generate_json(
            prompt=prompt,
            response_model={
                "reasoning": "string",
                "tool_call": {
                    "tool_name": "string",
                    "arguments": {}
                }
            },
            max_tokens=2000
        )
        
        # Extract reasoning and tool call
        reasoning = response.get("reasoning", "")
        tc_data = response.get("tool_call", {})
        tool_call = ToolCall(tc_data.get("tool_name", ""), tc_data.get("arguments", {}))
        
        return reasoning, tool_call
    
    def _handle_disambiguation(self, tool_calls: List[ToolCall], user_query: str) -> Dict:
        """Handle disambiguation using existing sophisticated strategy."""
        # Calculate uncertainty using existing framework
        overall_certainty, _ = self.uncertainty_calculator.calculate_sequence_certainty(tool_calls)
        
        certainty_threshold = self.config.get("certainty_threshold", 0.9)
        if overall_certainty >= certainty_threshold:
            return {
                "needs_clarification": False,
                "certainty_score": overall_certainty,
                "candidates_generated": 0
            }
        
        # Generate candidates using existing system
        candidates = self.question_generator.generate_candidate_questions(
            user_query=user_query,
            tool_calls=tool_calls,
            max_questions=self.config.get("max_candidates", 5)
        )
        
        # Evaluate using existing sophisticated metrics (EVPI, regret reduction, UCB)
        best_question, eval_metrics = self.question_generator.evaluate_questions(
            questions=candidates,
            tool_calls=tool_calls,
            base_threshold=self.config.get("base_threshold", 0.1),
            certainty_threshold=certainty_threshold
        )
        
        if best_question:
            # Update question tracking
            self.question_generator.update_arg_clarification_counts(best_question)
            
            return {
                "needs_clarification": True,
                "question": best_question.question_text,
                "question_obj": best_question,
                "certainty_score": overall_certainty,
                "candidates_generated": len(candidates),
                "selected_question": {
                    "question_id": best_question.question_id,
                    "question_text": best_question.question_text,
                    "target_args": best_question.target_args,
                    "metrics": {
                        "evpi": best_question.evpi,
                        "regret_reduction": best_question.regret_reduction,
                        "ucb_score": best_question.ucb_score
                    }
                }
            }
        
        return {
            "needs_clarification": False,
            "certainty_score": overall_certainty,
            "candidates_generated": len(candidates)
        }
    
    def _handle_error(self, error_result: ToolExecutionResult, request: str, context: Dict) -> Dict:
        """Handle execution errors."""
        # Check if error is recoverable through reasoning
        if self._is_recoverable_error(error_result):
            return {
                "needs_clarification": False,
                "observation": f"Error occurred: {error_result.message}. Trying different approach."
            }
        else:
            # Generate clarification question for the error
            question = f"I encountered an error: {error_result.message}. Can you provide more information to help resolve this?"
            return {
                "needs_clarification": True,
                "question": question
            }
    
    def _is_recoverable_error(self, error_result: ToolExecutionResult) -> bool:
        """Check if an error can be recovered from through reasoning."""
        # Simple heuristics for now
        recoverable_errors = ["TIMEOUT", "TEMPORARY_FAILURE"]
        return error_result.error in recoverable_errors
    
    def process_clarification(self, original_request: str, clarification: str) -> str:
        """Process user clarification and return enriched request."""
        # Record the clarification in current turn
        if (self.conversation_tracker.current_request and 
            self.conversation_tracker.current_request.turns):
            current_turn = self.conversation_tracker.current_request.turns[-1]
            current_turn.set_user_response(clarification, "clarification")
        
        # Use existing clarification processing if available
        if hasattr(self, '_last_question') and self._last_question:
            self.question_generator.process_user_response(
                question=self._last_question,
                user_response=clarification,
                tool_calls=[]  # Will be handled in next reasoning step
            )
        
        return f"{original_request}\nClarification: {clarification}"
    
    def get_full_conversation_data(self) -> Dict:
        """Get the full nested conversation structure."""
        return self.conversation_tracker.export_full_structure()
    
    def get_compatibility_data(self) -> Dict:
        """Get flattened data for backward compatibility."""
        return self.conversation_tracker.export_compatibility_format()
    
    def start_new_request(self, request_text: str, request_type: str = "initial") -> RequestTracker:
        """Start tracking a new request."""
        return self.conversation_tracker.start_new_request(request_text, request_type)
    
    def complete_current_request(self, success: bool, message: str, tool_calls: List[Dict] = None):
        """Mark the current request as completed."""
        if self.conversation_tracker.current_request:
            self.conversation_tracker.current_request.set_result(
                success=success,
                final_message=message,
                tool_calls_executed=tool_calls or []
            )