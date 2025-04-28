from typing import Dict, List, Tuple, Any, Optional
import logging
from core.tool_registry import ToolRegistry
from core.uncertainty import ToolCall, UncertaintyCalculator
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
        uncertainty_calculator: UncertaintyCalculator
    ):
        """
        Initialize a question generator.
        
        Args:
            llm_provider: Provider for LLM interactions
            tool_registry: Registry of available tools
            uncertainty_calculator: Calculator for uncertainty metrics
        """
        self.llm = llm_provider
        self.tool_registry = tool_registry
        self.uncertainty_calculator = uncertainty_calculator
        
        # Counter for how many times each argument has been clarified
        self.arg_clarification_counts: Dict[Tuple[str, str], int] = {}
        self.total_clarifications = 0
        
        # Store all generated questions and their evaluations for analysis
        self.question_history: List[Dict[str, Any]] = []
    
    def generate_candidate_questions(
        self,
        user_query: str,
        tool_calls: List[ToolCall],
        max_questions: int = 5
    ) -> List[ClarificationQuestion]:
        """
        Generate candidate clarification questions.
        
        Args:
            user_query: Original user query
            tool_calls: Current tool calls with uncertainty
            max_questions: Maximum number of questions to generate
            
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
        
        # Create prompt for question generation
        prompt = self._create_question_generation_prompt(
            user_query=user_query,
            tool_calls=tool_calls_info,
            uncertain_args=uncertain_args
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
        
        return questions

    def _create_question_generation_prompt(
        self,
        user_query: str,
        tool_calls: List[Dict],
        uncertain_args: List[Dict]
    ) -> str:
        """
        Create a prompt for question generation.
        
        Args:
            user_query: Original user query
            tool_calls: Current tool calls
            uncertain_args: List of uncertain arguments
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing tool calls.

Original user query:
"{user_query}"

Based on the query, I've determined that the following tool calls are needed, but some arguments are uncertain:

Tool Calls:
{tool_calls}

Uncertain Arguments:
{uncertain_args}

Your task is to generate clarification questions that would help resolve the uncertainty about specific arguments.

Instructions:
1. Generate questions that are clear, specific, and directly address the uncertain arguments
2. Each question should target one or more specific arguments
3. Questions should be conversational and easy for a user to understand
4. For each question, specify which tool and argument(s) it aims to clarify

Return your response as a JSON object with the following structure:
{{
  "questions": [
    {{
      "question": "A clear question to ask the user",
      "target_args": [["tool_name", "arg_name"], ["tool_name", "other_arg_name"]]
    }}
  ]
}}

Ensure that each question targets at least one uncertain argument.
"""
        return prompt

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
            key = ".".join(arg_tuple)
            self.arg_clarification_counts[key] = self.arg_clarification_counts.get(key, 0) + 1
        self.total_clarifications += 1
    
    def process_user_response(
        self,
        question: ClarificationQuestion,
        user_response: str,
        tool_calls: List[ToolCall]
    ) -> List[ToolCall]:
        """
        Process user response to a clarification question.
        
        Args:
            question: The question that was asked
            user_response: User's response to the question
            tool_calls: Current tool calls to update
            
        Returns:
            Updated tool calls
        """
        # Prepare context for the LLM
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing tool calls.

A user was asked the following clarification question:
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