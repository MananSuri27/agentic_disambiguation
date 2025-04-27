from typing import Dict, List, Any, Tuple, Optional
import copy
import math
import logging
from .tool_registry import Tool, ToolRegistry, DomainType

logger = logging.getLogger(__name__)

# Small positive value for numerical stability with infinite domains
EPSILON = 1e-3

class ArgumentState:
    """Class representing the state of an argument in a tool call."""
    
    def __init__(
        self,
        tool_name: str,
        arg_name: str,
        value: Any = "<UNK>",
        certainty: float = 0.0
    ):
        """
        Initialize an argument state.
        
        Args:
            tool_name: Name of the tool this argument belongs to
            arg_name: Name of the argument
            value: Current value of the argument (or <UNK> if unknown)
            certainty: Certainty probability (0-1)
        """
        self.tool_name = tool_name
        self.arg_name = arg_name
        self.value = value
        self.certainty = certainty
    
    def to_dict(self) -> Dict:
        """Convert the argument state to a dictionary."""
        return {
            "tool_name": self.tool_name,
            "arg_name": self.arg_name,
            "value": self.value,
            "certainty": self.certainty
        }


class ToolCall:
    """Class representing a tool call with argument states."""
    
    def __init__(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ):
        """
        Initialize a tool call.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Dictionary of argument names to values
        """
        self.tool_name = tool_name
        self.arguments = arguments
        self.arg_states: Dict[str, ArgumentState] = {}
    
    def to_dict(self) -> Dict:
        """Convert the tool call to a dictionary."""
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "arg_states": {name: state.to_dict() for name, state in self.arg_states.items()}
        }
    
    def to_execution_dict(self) -> Dict:
        """Convert the tool call to a dictionary suitable for execution."""
        return {
            "tool_name": self.tool_name,
            "parameters": {k: v for k, v in self.arguments.items() if v != "<UNK>"}
        }
    
    def __repr__(self):
        return repr(self.to_dict())


class UncertaintyCalculator:
    """Class for calculating uncertainty in tool calls."""
    
    def __init__(self, tool_registry: ToolRegistry):
        """
        Initialize an uncertainty calculator.
        
        Args:
            tool_registry: Registry of available tools
        """
        self.tool_registry = tool_registry
    
    def calculate_arg_certainty(
        self,
        tool: Tool,
        arg_name: str,
        arg_value: Any
    ) -> float:
        """
        Calculate certainty for a single argument.
        
        Args:
            tool: Tool the argument belongs to
            arg_name: Name of the argument
            arg_value: Current value of the argument
            
        Returns:
            Certainty probability (0-1)
        """
        # Unknown value has low certainty
        if arg_value == "<UNK>" or (isinstance(arg_value ,(list, tuple, dict, set)) and "<UNK>" in arg_value):
            arg = tool.get_argument(arg_name)
            if not arg:
                logger.warning(f"Unknown argument {arg_name} for tool {tool.name}")
                return EPSILON
            
            domain = arg.domain
            domain_size = domain.get_size()
            
            # For finite domains, use 1/size
            if domain_size < float('inf'):
                return 1.0 / domain_size
            else:
                # For infinite domains, use epsilon
                return EPSILON
        else:
            # Known value has certainty 1.0
            return 1.0
    
    def calculate_tool_call_certainty(
        self,
        tool_call: ToolCall
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate certainty for a tool call.
        
        Args:
            tool_call: Tool call to evaluate
            
        Returns:
            Tuple of (overall certainty, dict of argument certainties)
        """
        tool = self.tool_registry.get_tool(tool_call.tool_name)
        if not tool:
            logger.warning(f"Unknown tool: {tool_call.tool_name}")
            return 0.0, {}
        
        arg_certainties = {}
        overall_certainty = 1.0
        
        # Process each argument in the tool
        for arg in tool.arguments:
            arg_name = arg.name
            arg_value = tool_call.arguments.get(arg_name, "<UNK>")
            
            
            certainty = self.calculate_arg_certainty(tool, arg_name, arg_value)
            arg_certainties[arg_name] = certainty
            
            # Update the argument state in the tool call
            tool_call.arg_states[arg_name] = ArgumentState(
                tool_name=tool_call.tool_name,
                arg_name=arg_name,
                value=arg_value,
                certainty=certainty
            )
            
            # Update overall certainty (product of all certainties)
            overall_certainty *= certainty
        
        return overall_certainty, arg_certainties
    
    def calculate_sequence_certainty(
        self,
        tool_calls: List[ToolCall]
    ) -> Tuple[float, Dict[str, Dict[str, float]]]:
        """
        Calculate certainty for a sequence of tool calls.
        
        Args:
            tool_calls: List of tool calls to evaluate
            
        Returns:
            Tuple of (overall certainty, nested dict of tool and argument certainties)
        """
        overall_certainty = 1.0
        all_certainties = {}
        
        for i, tool_call in enumerate(tool_calls):
            call_certainty, arg_certainties = self.calculate_tool_call_certainty(tool_call)
            overall_certainty *= call_certainty
            all_certainties[f"{i}_{tool_call.tool_name}"] = arg_certainties
        
        return overall_certainty, all_certainties
    
    def calculate_regret(
        self,
        tool_calls: List[ToolCall]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate regret for a sequence of tool calls.
        
        Regret = sum(importance * (1 - certainty)) for each argument
        
        Args:
            tool_calls: List of tool calls to evaluate
            
        Returns:
            Tuple of (total regret, dict of argument regrets)
        """
        total_regret = 0.0
        arg_regrets = {}
        
        for tool_call in tool_calls:
            tool = self.tool_registry.get_tool(tool_call.tool_name)
            if not tool:
                continue
            
            for arg in tool.arguments:
                arg_name = arg.name
                if arg_name in tool_call.arg_states:
                    arg_state = tool_call.arg_states[arg_name]
                    importance = arg.domain.importance
                    certainty = arg_state.certainty
                    regret = importance * (1.0 - certainty)
                    
                    key = f"{tool_call.tool_name}.{arg_name}"
                    arg_regrets[key] = regret
                    total_regret += regret
        
        return total_regret, arg_regrets
    
    def compute_evpi(
        self,
        tool_calls: List[ToolCall],
        question_args: Dict[str, List[Tuple[str, str]]]
    ) -> float:
        """
        Compute Expected Value of Perfect Information for a question.
        
        Args:
            tool_calls: Current list of tool calls
            question_args: Dictionary mapping question to list of (tool_name, arg_name) it would resolve
            
        Returns:
            EVPI value
        """
        # Calculate current probability

        print(tool_calls)
        current_prob, _ = self.calculate_sequence_certainty(tool_calls)
        
        # Create a copy of tool calls to simulate perfect information
        tool_calls_copy = copy.deepcopy(tool_calls)
        # for tc in tool_calls:
        #     tc_copy = copy.deepcopy(tc)
        #     # tc_copy.arg_states = {k: ArgumentState(
        #     #     v.tool_name, v.arg_name, v.value, v.certainty
        #     # ) for k, v in tc.arg_states.items()}
        #     tool_calls_copy.append(tc_copy)
        
        # For each argument that would be resolved, set certainty to 1.0
        for question_id, arg_list in question_args.items():
            for arg_tuple in arg_list:
                print(arg_tuple)
                if len(arg_tuple) == 2:  # Ensure the tuple has the expected format
                    tool_name, arg_name = arg_tuple
                    for tc in tool_calls_copy:
                        if tc.tool_name == tool_name and arg_name in tc.arg_states:
                            tc.arg_states[arg_name].certainty = 1.0
                            tc.arguments[arg_name] = 'KNOWN'
        
        print(tool_calls)
        print(tool_calls_copy)
        
        # Calculate new probability
        new_prob, _ = self.calculate_sequence_certainty(tool_calls_copy)

        print(current_prob, new_prob)
        
        # EVPI is the difference in probabilities
        return new_prob - current_prob
    
    def compute_regret_reduction(
        self,
        tool_calls: List[ToolCall],
        question_args: Dict[str, List[Tuple[str, str]]]
    ) -> float:
        """
        Compute regret reduction for a question.
        
        Args:
            tool_calls: Current list of tool calls
            question_args: Dictionary mapping question to list of (tool_name, arg_name) it would resolve
            
        Returns:
            Regret reduction value
        """
        # Calculate current regret
        current_regret, _ = self.calculate_regret(tool_calls)
        
        # Create a copy of tool calls to simulate perfect information
        tool_calls_copy = []
        for tc in tool_calls:
            tc_copy = ToolCall(tc.tool_name, tc.arguments.copy())
            tc_copy.arg_states = {k: ArgumentState(
                v.tool_name, v.arg_name, v.value, v.certainty
            ) for k, v in tc.arg_states.items()}
            tool_calls_copy.append(tc_copy)
        
        # For each argument that would be resolved, set certainty to 1.0
        for question_id, arg_list in question_args.items():
            for arg_tuple in arg_list:
                if len(arg_tuple) == 2:  # Ensure the tuple has the expected format
                    tool_name, arg_name = arg_tuple
                    for tc in tool_calls_copy:
                        if tc.tool_name == tool_name and arg_name in tc.arg_states:
                            tc.arg_states[arg_name].certainty = 1.0
        
        # Calculate new regret
        new_regret, _ = self.calculate_regret(tool_calls_copy)
        
        # Regret reduction is the difference in regrets
        return current_regret - new_regret
    
    def compute_ucb_score(
        self,
        evpi: float,
        regret_reduction: float,
        arg_clarification_counts: Dict[Tuple[str, str], int],
        target_args: List[Tuple[str, str]],
        total_clarifications: int,
        c: float = 1.0
    ) -> float:
        """
        Compute UCB score for a question.
        
        UCB(q_k) = (EVPI(q_k) + ΔRegret(q_k)) + c * sqrt(log(N+1) / (n_k+1))
        
        Args:
            evpi: EVPI value for the question
            regret_reduction: Regret reduction value for the question
            arg_clarification_counts: Dictionary mapping (tool_name, arg_name) to count of clarifications
            target_args: List of (tool_name, arg_name) tuples targeted by this question
            total_clarifications: Total number of clarification attempts made so far
            c: Exploration constant
            
        Returns:
            UCB score
        """
        # Calculate the average number of times the target arguments have been clarified
        if not target_args:
            n_k = 0
        else:
            total_arg_counts = 0
            for arg_tuple in target_args:
                print(arg_clarification_counts)
                print(arg_tuple)
                total_arg_counts += arg_clarification_counts.get(".".join(arg_tuple), 0)
            n_k = total_arg_counts / len(target_args)
        
        # Calculate exploration term
        exploration = c * math.sqrt(math.log(total_clarifications + 1) / (n_k + 1))
        
        # Calculate UCB score
        ucb = (evpi + regret_reduction) + exploration
        
        return ucb
    
    def compute_dynamic_threshold(
        self,
        base_threshold: float,
        total_clarifications: int,
        alpha: float = 0.05,
        certainty_threshold: float = 0.9
    ) -> float:
        """
        Compute dynamic threshold for asking questions.
        
        tau = tau_0 * (1 + alpha * N)
        
        Args:
            base_threshold: Base threshold value
            total_clarifications: Total number of clarification attempts made so far
            alpha: Threshold increase factor
            certainty_threshold: Overall certainty threshold to stop clarification
            
        Returns:
            Dynamic threshold value
        """
        return base_threshold * (1.0 + alpha * total_clarifications)