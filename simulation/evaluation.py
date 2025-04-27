from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class SimulationEvaluator:
    """Class for evaluating simulation results."""
    
    def __init__(self):
        """Initialize a simulation evaluator."""
        pass
    
    def evaluate_simulation(
        self,
        simulation_data: Dict[str, Any],
        simulation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a simulation run.
        
        Args:
            simulation_data: Original simulation data
            simulation_result: Result of the simulation
            
        Returns:
            Evaluation metrics
        """
        metrics = {}
        
        # Extract ground truth
        ground_truth = simulation_data.get("ground_truth_tool_calls", [])
        
        # Extract final tool calls
        final_tool_calls = simulation_result.get("final_tool_calls", [])
        
        # Extract conversation
        conversation = simulation_result.get("conversation", [])
        
        # Extract question metrics
        questions = simulation_result.get("questions", [])
        
        # Calculate success metrics
        success, tool_match_rate, param_match_rate = self._calculate_success_metrics(ground_truth, final_tool_calls)
        
        # Calculate conversation metrics
        conversation_metrics = self._calculate_conversation_metrics(conversation)
        
        # Calculate question metrics
        question_metrics = self._calculate_question_metrics(questions)
        
        # Combine all metrics
        metrics["success"] = success
        metrics["tool_match_rate"] = tool_match_rate
        metrics["tools_fully_matched_rate"] = 1.0 if tool_match_rate == 1.0 else 0.0
        metrics["param_match_rate"] = param_match_rate
        metrics["conversation"] = conversation_metrics
        metrics["questions"] = question_metrics
        metrics["num_questions"] = len(questions)
        
        return metrics
    
    def _calculate_success_metrics(
        self,
        ground_truth: List[Dict[str, Any]],
        final_tool_calls: List[Dict[str, Any]]
    ) -> Tuple[bool, float, float]:
        """
        Calculate success metrics for the simulation.
        
        Args:
            ground_truth: Ground truth tool calls
            final_tool_calls: Final tool calls from the simulation
            
        Returns:
            Tuple of (success, tool_match_rate, param_match_rate)
        """
        if not ground_truth:
            return False, 0.0, 0.0
            
        # Create sets of tool names for comparison
        gt_tool_names = {tc.get("tool_name") for tc in ground_truth}
        actual_tool_names = {tc.get("tool_name") for tc in final_tool_calls}
        
        # Calculate tool match rate
        if not gt_tool_names:
            tool_match_rate = 0.0
        else:
            # Calculate intersection
            matching_tools = gt_tool_names.intersection(actual_tool_names)
            tool_match_rate = len(matching_tools) / len(gt_tool_names)
        
        # Calculate parameter match rate
        total_params = 0
        matching_params = 0
        
        for gt_tc in ground_truth:
            gt_tool_name = gt_tc.get("tool_name")
            gt_params = gt_tc.get("parameters", {})
            
            # Find matching tool call
            matching_tc = None
            for tc in final_tool_calls:
                if tc.get("tool_name") == gt_tool_name:
                    matching_tc = tc
                    break
            
            if matching_tc:
                actual_params = matching_tc.get("parameters", {})
                
                # Count parameters
                for param_name, gt_value in gt_params.items():
                    total_params += 1
                    if param_name in actual_params and actual_params[param_name] == gt_value:
                        matching_params += 1
        
        param_match_rate = matching_params / total_params if total_params > 0 else 0.0
        
        # Check for exact match of tool calls (success)
        exact_match = True
        if len(ground_truth) != len(final_tool_calls):
            exact_match = False
        else:
            # Check each tool call
            for gt_tc in ground_truth:
                gt_tool_name = gt_tc.get("tool_name")
                gt_params = gt_tc.get("parameters", {})
                
                # Find matching tool call
                matching_tc = None
                for tc in final_tool_calls:
                    if tc.get("tool_name") == gt_tool_name:
                        matching_tc = tc
                        break
                
                if not matching_tc:
                    exact_match = False
                    break
                    
                # Compare parameters
                actual_params = matching_tc.get("parameters", {})
                
                # Check for missing or extra parameters
                if set(gt_params.keys()) != set(actual_params.keys()):
                    exact_match = False
                    break
                    
                # Check parameter values
                for param_name, gt_value in gt_params.items():
                    if param_name not in actual_params or actual_params[param_name] != gt_value:
                        exact_match = False
                        break
                
                if not exact_match:
                    break
        
        return exact_match, tool_match_rate, param_match_rate
    
    def _calculate_conversation_metrics(
        self,
        conversation: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate metrics for the conversation.
        
        Args:
            conversation: List of conversation turns
            
        Returns:
            Conversation metrics
        """
        metrics = {}
        
        # Count total turns
        metrics["total_turns"] = len(conversation)
        
        # Count user turns
        user_turns = [turn for turn in conversation if turn.get("role") == "user"]
        metrics["user_turns"] = len(user_turns)
        
        # Count agent turns
        agent_turns = [turn for turn in conversation if turn.get("role") == "agent"]
        metrics["agent_turns"] = len(agent_turns)
        
        # Count clarification questions
        clarification_turns = [
            turn for turn in conversation 
            if turn.get("role") == "agent" and turn.get("type") == "clarification"
        ]
        metrics["clarification_questions"] = len(clarification_turns)
        
        return metrics
    
    def _calculate_question_metrics(
        self,
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate metrics for the questions.
        
        Args:
            questions: List of questions with metrics
            
        Returns:
            Question metrics
        """
        metrics = {}
        
        if not questions:
            return {
                "total": 0,
                "average_evpi": 0.0,
                "average_regret_reduction": 0.0,
                "average_ucb_score": 0.0
            }
        
        # Count total questions
        metrics["total"] = len(questions)
        
        # Calculate average metrics
        total_evpi = sum(q.get("metrics", {}).get("evpi", 0.0) for q in questions)
        total_regret_reduction = sum(q.get("metrics", {}).get("regret_reduction", 0.0) for q in questions)
        total_ucb_score = sum(q.get("metrics", {}).get("ucb_score", 0.0) for q in questions)
        
        metrics["average_evpi"] = total_evpi / len(questions) if questions else 0.0
        metrics["average_regret_reduction"] = total_regret_reduction / len(questions) if questions else 0.0
        metrics["average_ucb_score"] = total_ucb_score / len(questions) if questions else 0.0
        
        return metrics


class SimulationVisualizer:
    """Class for visualizing simulation results."""
    
    def __init__(self):
        """Initialize a simulation visualizer."""
        pass
    
    def visualize_conversation(
        self,
        conversation: List[Dict[str, Any]]
    ) -> str:
        """
        Visualize the conversation in a pretty format.
        
        Args:
            conversation: List of conversation turns
            
        Returns:
            Formatted conversation string
        """
        if not conversation:
            return "No conversation recorded."
            
        lines = []
        
        for i, turn in enumerate(conversation):
            role = turn.get("role", "unknown")
            message = turn.get("message", "")
            turn_type = turn.get("type", "")
            
            if role == "user":
                lines.append(f"\nUser: {message}")
            elif role == "agent":
                prefix = "Agent" if not turn_type else f"Agent ({turn_type})"
                lines.append(f"\n{prefix}: {message}")
            else:
                lines.append(f"\n{role}: {message}")
        
        return "\n".join(lines)
    
    def visualize_questions(
        self,
        questions: List[Dict[str, Any]]
    ) -> str:
        """
        Visualize the questions and their metrics.
        
        Args:
            questions: List of questions with metrics
            
        Returns:
            Formatted questions string
        """
        if not questions:
            return "No questions asked."
            
        lines = ["Questions and Metrics:"]
        
        for i, q in enumerate(questions):
            question_text = q.get("question_text", "")
            target_args = q.get("target_args", [])
            metrics = q.get("metrics", {})
            
            # Format target arguments
            target_args_str = ", ".join([f"{tool}.{arg}" for tool, arg in target_args])
            
            # Format metrics
            evpi = metrics.get("evpi", 0.0)
            regret_reduction = metrics.get("regret_reduction", 0.0)
            ucb_score = metrics.get("ucb_score", 0.0)
            
            lines.append(f"\nQuestion {i+1}: {question_text}")
            lines.append(f"Target Arguments: {target_args_str}")
            lines.append(f"Metrics: EVPI={evpi:.4f}, Regret Reduction={regret_reduction:.4f}, UCB Score={ucb_score:.4f}")
        
        return "\n".join(lines)
    
    def visualize_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        title: str = "Tool Calls"
    ) -> str:
        """
        Visualize tool calls in a pretty format.
        
        Args:
            tool_calls: List of tool calls
            title: Title for the visualization
            
        Returns:
            Formatted tool calls string
        """
        if not tool_calls:
            return f"{title}: None"
            
        lines = [f"{title}:"]
        
        for i, tc in enumerate(tool_calls):
            tool_name = tc.get("tool_name", "")
            parameters = tc.get("parameters", {})
            
            # Format parameters
            params_str = ", ".join([f"{k}={v}" for k, v in parameters.items()])
            
            lines.append(f"\n{i+1}. {tool_name}({params_str})")
        
        return "\n".join(lines)
    
    def visualize_metrics(
        self,
        metrics: Dict[str, Any]
    ) -> str:
        """
        Visualize evaluation metrics in a pretty format.
        
        Args:
            metrics: Evaluation metrics
            
        Returns:
            Formatted metrics string
        """
        success = metrics.get("success", False)
        tool_match_rate = metrics.get("tool_match_rate", 0.0)
        tools_fully_matched_rate = metrics.get("tools_fully_matched_rate", 0.0)
        param_match_rate = metrics.get("param_match_rate", 0.0)
        conversation_metrics = metrics.get("conversation", {})
        question_metrics = metrics.get("questions", {})
        num_questions = metrics.get("num_questions", 0)
        
        lines = ["Evaluation Metrics:"]
        
        # Success metrics
        lines.append(f"\nSuccess (exact match): {'Yes' if success else 'No'}")
        lines.append(f"Tool Match Rate: {tool_match_rate:.2f}")
        lines.append(f"Tools Fully Matched: {'Yes' if tools_fully_matched_rate == 1.0 else 'No'}")
        lines.append(f"Parameter Match Rate: {param_match_rate:.2f}")
        
        # Conversation metrics
        lines.append(f"\nConversation Metrics:")
        lines.append(f"- Total Turns: {conversation_metrics.get('total_turns', 0)}")
        lines.append(f"- User Turns: {conversation_metrics.get('user_turns', 0)}")
        lines.append(f"- Agent Turns: {conversation_metrics.get('agent_turns', 0)}")
        lines.append(f"- Clarification Questions: {conversation_metrics.get('clarification_questions', 0)}")
        
        # Question metrics
        lines.append(f"\nQuestion Metrics:")
        lines.append(f"- Total Questions: {num_questions}")
        lines.append(f"- Average EVPI: {question_metrics.get('average_evpi', 0.0):.4f}")
        lines.append(f"- Average Regret Reduction: {question_metrics.get('average_regret_reduction', 0.0):.4f}")
        lines.append(f"- Average UCB Score: {question_metrics.get('average_ucb_score', 0.0):.4f}")
        
        return "\n".join(lines)