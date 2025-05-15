from typing import Dict, List, Tuple, Any, Optional
import logging
from core.tool_registry import ToolRegistry, Tool
from core.uncertainty import ToolCall, UncertaintyCalculator
from core.plugin_manager import PluginManager
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class ClarificationQuestion:
    """Class representing a clarification question."""
    
    def __init__(
        self, 
        question_id: str,
        question_text: str,
        target_args: List[Tuple[str, str]]  # List of (tool_name, arg_name) tuples
    ):
        """
        Initialize a clarification question.
        
        Args:
            question_id: Unique identifier for the question
            question_text: Text of the question to ask the user
            target_args: List of (tool_name, arg_name) tuples this question targets
        """
        self.question_id = question_id
        self.question_text = question_text
        self.target_args = target_args
        
        # Metrics for this question (to be populated later)
        self.evpi = 0.0
        self.regret_reduction = 0.0
        self.ucb_score = 0.0
    
    def to_dict(self) -> Dict:
        """Convert the question to a dictionary."""
        return {
            "question_id": self.question_id,
            "question_text": self.question_text,
            "target_args": self.target_args,
            "metrics": {
                "evpi": self.evpi,
                "regret_reduction": self.regret_reduction,
                "ucb_score": self.ucb_score
            }
        }


class QuestionGenerator:
    """Class for generating and evaluating clarification questions."""
    
    def __init__(
        self, 
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        uncertainty_calculator: UncertaintyCalculator,
        plugin_manager: PluginManager
    ):
        """
        Initialize a question generator.
        
        Args:
            llm_provider: Provider for LLM interactions
            tool_registry: Registry of available tools
            uncertainty_calculator: Calculator for uncertainty metrics
            plugin_manager: Manager for API plugins
        """
        self.llm = llm_provider
        self.tool_registry = tool_registry
        self.uncertainty_calculator = uncertainty_calculator
        self.plugin_manager = plugin_manager
        
        # Counter for how many times each argument has been clarified
        self.arg_clarification_counts: Dict[str, int] = {}
        self.total_clarifications = 0
        
        # Store all generated questions and their evaluations for analysis
        self.question_history: List[Dict[str, Any]] = []
        
        # Store all candidate questions ever generated
        self.all_candidate_questions: List[Dict[str, Any]] = []


    def generate_candidate_questions(
        self,
        user_query: str,
        tool_calls: List[ToolCall],
        max_questions: int = 5,
        conversation_history: List[Dict[str, Any]] = None
    ) -> List[ClarificationQuestion]:
        """
        Generate candidate clarification questions.
        
        Args:
            user_query: Original user query
            tool_calls: Current tool calls with uncertainty
            max_questions: Maximum number of questions to generate
            conversation_history: Optional conversation history
            
        Returns:
            List of clarification questions
        """
        # Extract uncertain arguments
        uncertain_args = []
        for tc in tool_calls:
            tool = self.tool_registry.get_tool(tc.tool_name)
            if not tool:
                continue
                
            for arg_name, arg_state in tc.arg_states.items():
                if arg_state.certainty < 0.9:  # Only consider uncertain arguments
                    arg = tool.get_argument(arg_name)
                    if arg:
                        uncertain_args.append({
                            "tool_name": tc.tool_name,
                            "arg_name": arg_name,
                            "domain": str(arg.domain),
                            "description": arg.description,
                            "certainty": arg_state.certainty
                        })
        
        # Prepare tool call information for the LLM
        tool_calls_info = []
        for tc in tool_calls:
            tool_calls_info.append({
                "tool_name": tc.tool_name,
                "arguments": tc.arguments
            })
        
        # Get detailed tool documentation for relevant tools
        tool_documentation = self._get_tool_documentation(tool_calls)
        
        # Create prompt for question generation
        prompt = self._create_question_generation_prompt(
            user_query=user_query,
            tool_calls=tool_calls_info,
            uncertain_args=uncertain_args,
            tool_documentation=tool_documentation,
            conversation_history=conversation_history
        )
        
        # Call LLM to generate questions
        questions_json = self.llm.generate_json(
            prompt=prompt,
            response_model={
                "questions": [
                    {
                        "question": "string",
                        "target_args": [["tool_name", "arg_name"]]
                    }
                ]
            },
            max_tokens=2000
        )

        
        # Process the results
        questions = []
        if "questions" in questions_json:
            for i, q_data in enumerate(questions_json["questions"]):
                if i >= max_questions:
                    break
                    
                q_text = q_data.get("question", "")
                target_args = q_data.get("target_args", [])
                
                if q_text and target_args:
                    q_id = f"q_{len(questions)}"
                    question = ClarificationQuestion(
                        question_id=q_id,
                        question_text=q_text,
                        target_args=target_args
                    )
                    questions.append(question)
                    
                    # Add to all_candidate_questions for tracking
                    self.all_candidate_questions.append({
                        "question_id": q_id,
                        "question_text": q_text,
                        "target_args": target_args,
                        "was_selected": False,  # Will be updated if question is selected
                        "metrics": {
                            "evpi": 0.0,
                            "regret_reduction": 0.0,
                            "ucb_score": 0.0
                        }
                    })
        
        return questions
    
    def _get_tool_documentation(self, tool_calls: List[ToolCall]) -> str:
        """
        Get detailed documentation for tools involved in the tool calls.
        
        Args:
            tool_calls: List of tool calls
            
        Returns:
            Formatted string with detailed tool documentation
        """
        tool_docs = []
        seen_tools = set()
        
        for tc in tool_calls:
            tool_name = tc.tool_name
            if tool_name in seen_tools:
                continue
                
            seen_tools.add(tool_name)
            tool = self.tool_registry.get_tool(tool_name)
            
            if not tool:
                continue
                
            # Format detailed documentation for this tool
            arg_docs = []
            for arg in tool.arguments:
                arg_docs.append(f"  - {arg.name}: {arg.description} - {str(arg.domain)}")
                
            tool_doc = f"Tool: {tool_name}\nDescription: {tool.description}\nArguments:\n" + "\n".join(arg_docs)
            tool_docs.append(tool_doc)
            
        return "\n\n".join(tool_docs)

    def _create_question_generation_prompt(
        self,
        user_query: str,
        tool_calls: List[Dict],
        uncertain_args: List[Dict],
        tool_documentation: str,
        conversation_history: List[Dict[str, Any]] = None
    ) -> str:
        """
        Create a prompt for question generation.
        
        Args:
            user_query: Original user query
            tool_calls: Current tool calls
            uncertain_args: List of uncertain arguments
            tool_documentation: Detailed documentation for relevant tools
            conversation_history: Optional conversation history
            
        Returns:
            Formatted prompt string
        """
        # Format conversation history if provided
        formatted_history = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "unknown")
                message = turn.get("message", "")
                history_lines.append(f"{role.capitalize()}: {message}")
            formatted_history = "\n".join(history_lines)
            formatted_history = f"Conversation history:\n{formatted_history}\n\n"
            
        # Get the first tool call to determine which plugin to use
        # if tool_calls:
        #     first_tool = tool_calls[0].get("tool_name", "")
        #     plugin = self.plugin_manager.get_plugin_for_tool(first_tool)
            
        #     if plugin:
        #         # Use plugin-specific template if available
        #         templates = plugin.get_prompt_templates()
        #         if "question_generation" in templates:
        #             template = templates["question_generation"]
                    
        #             # If the template doesn't have a placeholder for conversation history, add it
        #             if "{conversation_history}" not in template:
        #                 template = formatted_history + template
                    
        #             # If the template doesn't have a placeholder for tool documentation, add it
        #             if "{tool_documentation}" not in template:
        #                 # Find a good place to insert it - after tool_calls and before instructions
        #                 if "Uncertain Arguments:" in template:
        #                     template = template.replace(
        #                         "Uncertain Arguments:",
        #                         "Detailed Tool Documentation:\n{tool_documentation}\n\nUncertain Arguments:"
        #                     )
                        
        #             return template.format(
        #                 user_query=user_query,
        #                 tool_calls=tool_calls,
        #                 uncertain_args=uncertain_args,
        #                 conversation_history=formatted_history,
        #                 tool_documentation=tool_documentation
        #             )
        
        # Fall back to default template if no plugin-specific one is available
        default_template = """
You are an AI assistant that helps users by understanding their queries and executing tool calls.

{conversation_history}Original user query:
"{user_query}"

Based on the query, I've determined that the following tool calls are needed, but some arguments are uncertain:

Tool Calls:
{tool_calls}

Detailed Tool Documentation:
{tool_documentation}

Uncertain Arguments:
{uncertain_args}

Your task is to generate clarification questions that would help resolve the uncertainty about specific arguments.

Instructions:
1. Generate questions that are clear, specific, and directly address the uncertain arguments
2. Each question should target one or more specific arguments
3. Questions should be conversational and easy for a user to understand
4. For each question, specify which tool and argument(s) it aims to clarify.
5. Generate 5 diverse questions.
6. Keep in mind the the arguments you wish to clarify, their domains etc.

Return your response as a JSON object with the following structure:
{{
  "questions": [
    {{
      "question": "A clear question to ask the user",
      "target_args": [["tool_name", "arg_name"], ["tool_name", "other_arg_name"]]
    }}
    // ... 5 total questions
  ]
}}

Ensure that each question targets at least one uncertain argument.
"""
        return default_template.format(
            user_query=user_query,
            tool_calls=tool_calls,
            uncertain_args=uncertain_args,
            conversation_history=formatted_history,
            tool_documentation=tool_documentation
        )
        
    def process_user_response(
        self,
        question: ClarificationQuestion,
        user_response: str,
        tool_calls: List[ToolCall],
        conversation_history: List[Dict[str, Any]] = None
    ) -> List[ToolCall]:
        """
        Process user response to a clarification question.
        
        Args:
            question: The question that was asked
            user_response: User's response to the question
            tool_calls: Current tool calls to update
            conversation_history: Optional conversation history
            
        Returns:
            Updated tool calls
        """
        # Format conversation history if provided
        formatted_history = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "unknown")
                message = turn.get("message", "")
                history_lines.append(f"{role.capitalize()}: {message}")
            formatted_history = "\n".join(history_lines)
            formatted_history = f"Conversation history:\n{formatted_history}\n\n"
            
        # Prepare context for the LLM
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing tool calls.

{formatted_history}A user was asked the following clarification question:
"{question.question_text}"

The user's response was:
"{user_response}"

This question was targeting the following arguments:
{question.target_args}

The current tool calls are:
{[tc.to_dict() for tc in tool_calls]}

Your task is to update the tool calls based on the user's response. Focus specifically on the target arguments.

Return your response as a JSON object with the updated tool calls:
{{
  "updated_tool_calls": [
    {{
      "tool_name": "tool_name",
      "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
      }}
    }}
  ]
}}

If the user says that they have no other requests, tool calls don't need to be updated, then just return "DONE", no JSON.
"""
        
        # Call LLM to update tool calls
        updated_calls_json = self.llm.generate_json(
            prompt=prompt,
            response_model={
                "updated_tool_calls": [
                    {
                        "tool_name": "string",
                        "arguments": {}
                    }
                ]
            },
            max_tokens=2000
        )
        
        # Process the results
        if "updated_tool_calls" in updated_calls_json:
            updated_tool_calls = []
            
            # Map original tool calls by tool name for reference
            tool_call_map = {tc.tool_name: tc for tc in tool_calls}
            
            for updated_call_data in updated_calls_json["updated_tool_calls"]:
                tool_name = updated_call_data.get("tool_name", "")
                arguments = updated_call_data.get("arguments", {})
                
                # Check if this is updating an existing tool call
                if tool_name in tool_call_map:
                    # Update existing tool call
                    original_tc = tool_call_map[tool_name]
                    # Merge arguments, keeping original ones that weren't updated
                    merged_args = original_tc.arguments.copy()
                    merged_args.update(arguments)
                    
                    updated_tc = ToolCall(tool_name, merged_args)
                    updated_tool_calls.append(updated_tc)
                else:
                    # This is a new tool call
                    new_tc = ToolCall(tool_name, arguments)
                    updated_tool_calls.append(new_tc)
            
            # If no tool calls were returned, keep the original ones
            if not updated_tool_calls:
                return tool_calls
                
            return updated_tool_calls
        
        # If something went wrong, return the original tool calls
        return tool_calls

    def evaluate_questions(
        self,
        questions: List[ClarificationQuestion],
        tool_calls: List[ToolCall],
        base_threshold: float = 0.1,
        certainty_threshold: float = 0.9
    ) -> Tuple[Optional[ClarificationQuestion], Dict[str, Any]]:
        """
        Evaluate and rank clarification questions.
        
        Args:
            questions: List of candidate questions
            tool_calls: Current tool calls with uncertainty
            base_threshold: Base threshold for question asking
            certainty_threshold: Overall certainty threshold to stop clarification
            
        Returns:
            Tuple of (best question or None, evaluation metrics)
        """
        if not questions:
            return None, {"message": "No questions generated"}
        
        # Calculate overall certainty
        overall_certainty, _ = self.uncertainty_calculator.calculate_sequence_certainty(tool_calls)
        
        # If certainty is already high enough, don't ask more questions
        if overall_certainty >= certainty_threshold:
            return None, {
                "message": f"Certainty threshold reached: {overall_certainty:.4f} >= {certainty_threshold}",
                "overall_certainty": overall_certainty,
                "questions": []
            }
        
        # Calculate metrics for each question
        for question in questions:
            # Convert target_args list to format needed by uncertainty calculator
            target_args_dict = {question.question_id: question.target_args}
            
            # Calculate EVPI
            evpi = self.uncertainty_calculator.compute_evpi(tool_calls, target_args_dict)
            question.evpi = evpi
            
            # Calculate regret reduction
            regret_reduction = self.uncertainty_calculator.compute_regret_reduction(
                tool_calls, target_args_dict
            )
            question.regret_reduction = regret_reduction
            
            # Calculate UCB score
            ucb_score = self.uncertainty_calculator.compute_ucb_score(
                evpi=evpi,
                regret_reduction=regret_reduction,
                arg_clarification_counts=self.arg_clarification_counts,
                target_args=question.target_args,
                total_clarifications=self.total_clarifications
            )
            question.ucb_score = ucb_score
            
            # Store question information in history
            self.question_history.append({
                "question_id": question.question_id,
                "question_text": question.question_text,
                "target_args": question.target_args,
                "metrics": {
                    "evpi": evpi,
                    "regret_reduction": regret_reduction,
                    "ucb_score": ucb_score
                },
                "overall_certainty": overall_certainty
            })
            
            # Update the stored candidate question with metrics
            for candidate in self.all_candidate_questions:
                if candidate["question_id"] == question.question_id:
                    candidate["metrics"]["evpi"] = evpi
                    candidate["metrics"]["regret_reduction"] = regret_reduction
                    candidate["metrics"]["ucb_score"] = ucb_score
        
        # Sort questions by UCB score
        questions.sort(key=lambda q: q.ucb_score, reverse=True)
        
        # Get the best question
        best_question = questions[0] if questions else None
        
        # Check if the best question exceeds the dynamic threshold
        dynamic_threshold = self.uncertainty_calculator.compute_dynamic_threshold(
            base_threshold=base_threshold,
            total_clarifications=self.total_clarifications,
            certainty_threshold=certainty_threshold
        )
        
        # Prepare evaluation metrics
        metrics = {
            "questions": [q.to_dict() for q in questions],
            "dynamic_threshold": dynamic_threshold,
            "total_clarifications": self.total_clarifications,
            "arg_clarification_counts": dict(self.arg_clarification_counts),
            "overall_certainty": overall_certainty
        }
        
        # Check if the best question exceeds the threshold
        if best_question and best_question.ucb_score >= dynamic_threshold:
            # Mark this question as selected in the all_candidate_questions list
            for candidate in self.all_candidate_questions:
                if candidate["question_id"] == best_question.question_id:
                    candidate["was_selected"] = True
            return best_question, metrics
        else:
            return None, metrics
    
    def update_arg_clarification_counts(self, question: ClarificationQuestion) -> None:
        """
        Update the counters for arguments that were clarified.
        
        Args:
            question: The question that was asked
        """
        for arg_tuple in question.target_args:
            if len(arg_tuple) == 2:
                tool_name, arg_name = arg_tuple
                key = f"{tool_name}.{arg_name}"
                self.arg_clarification_counts[key] = self.arg_clarification_counts.get(key, 0) + 1
        self.total_clarifications += 1
    
    def get_all_candidate_questions(self) -> List[Dict[str, Any]]:
        """
        Get all candidate questions that have been generated.
        
        Returns:
            List of all candidate questions with their details
        """
        return self.all_candidate_questions