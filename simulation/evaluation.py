from typing import Dict, List, Any, Tuple, Optional
import logging

logger = logging.getLogger(__name__)




class SimulationEvaluator:
    """Class for evaluating simulation results."""
    
    def __init__(self):
        """Initialize a simulation evaluator."""
        pass

    def _extract_final_planned_calls(self, attempts: List[Dict]) -> List[Dict]:
        """Extract the final planned state of each unique tool call."""
        tool_call_map = {}
        
        for attempt in attempts:
            tool_call = attempt.get("tool_call", {})
            tool_name = tool_call.get("tool_name", "")
            arguments = tool_call.get("arguments", {})
            
            # Create a signature based on tool name and arguments structure
            # We use argument keys to identify the "same" tool call across attempts
            arg_keys = sorted(arguments.keys())
            signature = f"{tool_name}:{arg_keys}"
            
            # Keep the latest version of each unique tool call
            # Later attempts in the list will overwrite earlier ones
            tool_call_map[signature] = tool_call
        
        return list(tool_call_map.values())
    
    # def _extract_final_planned_calls(self, attempts: List[Dict]) -> List[Dict]:
    #     """
    #     Extract the final planned state of each unique tool call.
        
    #     Strategy:
    #     1. Group attempts by tool name and argument structure
    #     2. For each group, take the latest attempt that was planned to be executed
    #     3. Return the tool call from that attempt
    #     """
    #     # Group attempts by tool signature
    #     tool_groups = {}
        
    #     for i, attempt in enumerate(attempts):
    #         tool_call = attempt.get("tool_call", {})
    #         tool_name = tool_call.get("tool_name", "")
    #         arguments = tool_call.get("arguments", {})
            
    #         # Create a more specific signature that considers both tool name and argument keys
    #         # This helps distinguish between different calls to the same tool
    #         arg_keys = tuple(sorted(arguments.keys()))
    #         signature = (tool_name, arg_keys)
            
    #         # Store attempt with its index for ordering
    #         if signature not in tool_groups:
    #             tool_groups[signature] = []
    #         tool_groups[signature].append((i, attempt))
        
    #     # For each group, get the latest planned tool call
    #     final_tool_calls = []
    #     for signature, group_attempts in tool_groups.items():
    #         # Sort by index to get chronological order
    #         group_attempts.sort(key=lambda x: x[0])
            
    #         # Take the latest attempt (highest index)
    #         latest_attempt = group_attempts[-1][1]
    #         tool_call = latest_attempt.get("tool_call", {})
            
    #         # Only include if it's a valid tool call
    #         if tool_call.get("tool_name"):
    #             final_tool_calls.append(tool_call)
        
    #     return final_tool_calls

    def _extract_executed_calls(self, attempts: List[Dict]) -> List[Dict]:
        """Extract only tool calls that were actually executed."""
        return [
            a["tool_call"] for a in attempts 
            if a.get("was_executed", False)
        ]

    def _extract_successful_executions(self, attempts: List[Dict]) -> List[Dict]:
        """Extract only tool calls that executed successfully."""
        return [
            a for a in attempts 
            if a.get("was_executed", False) and a.get("success", False)
        ]

    def _calculate_execution_metrics(self, attempts: List[Dict]) -> Dict[str, Any]:
        """Calculate metrics about execution attempts."""
        if not attempts:
            return {
                "total_attempts": 0,
                "executed_attempts": 0,
                "successful_attempts": 0,
                "duplicate_attempts": 0,
                "execution_rate": 0.0,
                "success_rate": 0.0,
                "execution_success": False
            }
        
        total_attempts = len(attempts)
        executed_attempts = len([a for a in attempts if a.get("was_executed")])
        successful_attempts = len([a for a in attempts if a.get("success")])
        duplicate_attempts = len([a for a in attempts if a.get("reason") == "duplicate"])
        failed_attempts = len([a for a in attempts if a.get("was_executed") and not a.get("success")])
        
        # Calculate rates
        execution_rate = executed_attempts / total_attempts if total_attempts > 0 else 0.0
        success_rate = successful_attempts / executed_attempts if executed_attempts > 0 else 0.0
        
        # Overall execution success means at least one tool was executed successfully
        # and no executed tools failed
        execution_success = successful_attempts > 0 and failed_attempts == 0
        
        return {
            "total_attempts": total_attempts,
            "executed_attempts": executed_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "duplicate_attempts": duplicate_attempts,
            "execution_rate": execution_rate,
            "success_rate": success_rate,
            "execution_success": execution_success,
            "attempt_breakdown": {
                "new_executions": len([a for a in attempts if a.get("reason") == "new tool call" and a.get("was_executed")]),
                "clarification_executions": len([a for a in attempts if a.get("reason") == "new tool call after clarification" and a.get("was_executed")]),
                "skipped_duplicates": duplicate_attempts,
                "validation_failures": len([a for a in attempts if not a.get("was_executed") and a.get("reason") != "duplicate"])
            }
        }
    
    def evaluate_simulation(
        self,
        simulation_data: Dict[str, Any],
        simulation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a simulation run using ONLY tool call attempts.
        
        Args:
            simulation_data: Original simulation data
            simulation_result: Result of the simulation
            
        Returns:
            Evaluation metrics
        """
        metrics = {}
        
        # Extract ground truth
        ground_truth = simulation_data.get("ground_truth_tool_calls", [])
        
        # Check if ground truth has turn information
        has_turn_info = any("turn" in tc for tc in ground_truth)
        
        # For backward compatibility, if no turn info is present, assume all are from turn 1
        if not has_turn_info:
            ground_truth = [{"turn": 1, **tc} for tc in ground_truth]
        
        # Extract data from tool call attempts - THIS IS THE ONLY SOURCE
        all_tool_call_attempts = simulation_result.get("all_tool_call_attempts", [])
        
        # Extract conversation and questions
        conversation = simulation_result.get("conversation", [])
        questions = simulation_result.get("questions", [])
        all_candidate_questions = simulation_result.get("all_candidate_questions", [])
        
        # Calculate ALL metrics directly from attempts
        attempt_metrics = self._calculate_attempt_based_metrics(all_tool_call_attempts, ground_truth)
        conversation_metrics = self._calculate_conversation_metrics(conversation)
        question_metrics = self._calculate_question_metrics(questions, all_candidate_questions)
        
        # Combine all metrics
        metrics.update(attempt_metrics)
        metrics["conversation"] = conversation_metrics
        metrics["questions"] = question_metrics
        metrics["num_questions"] = len(questions)
        metrics["num_candidate_questions"] = len(all_candidate_questions)
        metrics["num_tool_call_attempts"] = len(all_tool_call_attempts)
        
        return metrics
    def _calculate_validity_metrics(
        self,
        final_tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate validity metrics - whether tool calls are executable.
        
        Args:
            final_tool_calls: Final tool calls from the simulation
            
        Returns:
            Validity metrics
        """
        metrics = {}
        
        valid_count = 0
        total_count = len(final_tool_calls)
        
        for tc in final_tool_calls:
            # Check if tool has all required parameters (not <UNK>)
            is_valid = True
            arguments = tc.get("arguments", tc.get("parameters", {}))
            
            # For this simulation, we consider a tool call valid if it doesn't have <UNK> values
            for param, value in arguments.items():
                if value == "<UNK>":
                    is_valid = False
                    break
            
            if is_valid:
                valid_count += 1
        
        metrics["total_tool_calls"] = total_count
        metrics["valid_tool_calls"] = valid_count
        metrics["validity_rate"] = valid_count / total_count if total_count > 0 else 0.0
        metrics["all_valid"] = valid_count == total_count
        
        return metrics
    
    def _calculate_correctness_metrics(
        self,
        ground_truth: List[Dict[str, Any]],
        final_tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate correctness metrics - whether tool calls match ground truth.
        
        Args:
            ground_truth: Ground truth tool calls (with turn information)
            final_tool_calls: Final tool calls from the simulation
            
        Returns:
            Correctness metrics
        """
        if not ground_truth:
            return {
                "exact_match": False,
                "tool_match_rate": 0.0,
                "param_match_rate": 0.0,
                "tools_fully_matched_rate": 0.0
            }
            
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
                actual_params = matching_tc.get("arguments", matching_tc.get("parameters", {}))
                
                # Count parameters
                for param_name, gt_value in gt_params.items():
                    total_params += 1
                    
                    if param_name in actual_params:
                        actual_val = actual_params[param_name]
                        
                        # Check for direct equality first
                        if actual_val == gt_value:
                            # Direct match
                            matching_params += 1
                        # Check if one is a single-element list containing the other
                        elif (isinstance(actual_val, list) and len(actual_val) == 1 and actual_val[0] == gt_value) or \
                            (isinstance(gt_value, list) and len(gt_value) == 1 and gt_value[0] == actual_val):
                            # Single-element list matches the other value
                            matching_params += 1

        
        param_match_rate = matching_params / total_params if total_params > 0 else 0.0
        

        # Check for exact match of tool calls (success)
        exact_match = self._check_exact_match(ground_truth, final_tool_calls)
        
        return {
            "exact_match": exact_match,
            "tool_match_rate": tool_match_rate,
            "param_match_rate": param_match_rate,
            "tools_fully_matched_rate": 1.0 if tool_match_rate == 1.0 else 0.0
        }

    def _check_exact_match(
        self,
        ground_truth: List[Dict[str, Any]],
        final_tool_calls: List[Dict[str, Any]]
    ) -> bool:
        """Check if there's an exact match between ground truth and final tool calls."""
        if len(ground_truth) != len(final_tool_calls):
            return False
            
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
                return False
                
            # Compare parameters
            actual_params = matching_tc.get("parameters", matching_tc.get("arguments", {}))
            
            # Check for missing or extra parameters
            if set(gt_params.keys()) != set(actual_params.keys()):
                return False
                
            # Check parameter values
            for param_name, gt_value in gt_params.items():
                if param_name not in actual_params or actual_params[param_name] != gt_value:
                    return False
        
        return True
    
    def _calculate_conversation_metrics(
        self,
        conversation: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calculate metrics for the conversation - excluding automated messages.
        
        Args:
            conversation: List of conversation turns
            
        Returns:
            Conversation metrics
        """
        metrics = {}
        
        # Only count human-relevant turns - exclude execution and confirmation messages
        human_relevant_turns = []
        for turn in conversation:
            if turn.get("type") not in ["execution", "execution_result", "confirmation", "execution_retry", "execution_error"]:
                human_relevant_turns.append(turn)
        
        metrics["total_turns"] = len(human_relevant_turns)
        
        # Count user turns
        user_turns = [turn for turn in human_relevant_turns if turn.get("role") == "user"]
        metrics["user_turns"] = len(user_turns)
        
        # Count agent turns (excluding automated)
        agent_turns = [turn for turn in human_relevant_turns if turn.get("role") == "agent"]
        metrics["agent_turns"] = len(agent_turns)
        
        # Count clarification questions
        clarification_turns = [
            turn for turn in human_relevant_turns 
            if turn.get("role") == "agent" and turn.get("type") == "clarification"
        ]
        metrics["clarification_questions"] = len(clarification_turns)
        
        # Count follow-up requests
        follow_up_turns = [
            turn for turn in human_relevant_turns 
            if turn.get("role") == "user" and turn.get("type") == "follow_up"
        ]
        metrics["follow_up_requests"] = len(follow_up_turns)
        
        return metrics
    
    def _calculate_question_metrics(
        self,
        questions: List[Dict[str, Any]],
        all_candidate_questions: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate metrics for the questions.
        
        Args:
            questions: List of questions with metrics
            all_candidate_questions: List of all candidate questions (including rejected ones)
            
        Returns:
            Question metrics
        """
        metrics = {}
        
        if not questions:
            return {
                "total": 0,
                "average_evpi": 0.0,
                "average_regret_reduction": 0.0,
                "average_ucb_score": 0.0,
                "total_candidates": len(all_candidate_questions) if all_candidate_questions else 0
            }
        
        # Count total questions
        metrics["total"] = len(questions)
        metrics["total_candidates"] = len(all_candidate_questions) if all_candidate_questions else len(questions)
        
        # Calculate average metrics
        total_evpi = sum(q.get("metrics", {}).get("evpi", 0.0) for q in questions)
        total_regret_reduction = sum(q.get("metrics", {}).get("regret_reduction", 0.0) for q in questions)
        total_ucb_score = sum(q.get("metrics", {}).get("ucb_score", 0.0) for q in questions)
        
        metrics["average_evpi"] = total_evpi / len(questions) if questions else 0.0
        metrics["average_regret_reduction"] = total_regret_reduction / len(questions) if questions else 0.0
        metrics["average_ucb_score"] = total_ucb_score / len(questions) if questions else 0.0
        
        # If we have all candidate questions, calculate selection rate
        if all_candidate_questions:
            selected_count = sum(1 for q in all_candidate_questions if q.get("was_selected", False))
            metrics["selection_rate"] = selected_count / len(all_candidate_questions) if all_candidate_questions else 0.0
        
        return metrics
    
    def _calculate_attempt_based_metrics(
        self, 
        attempts: List[Dict[str, Any]], 
        ground_truth: List[Dict[str, Any]]
        ) -> Dict[str, Any]:
        """
        Calculate all metrics directly from tool call attempts.
        """
        if not attempts:
            return {
                "execution": {"total_attempts": 0, "execution_success": False},
                "validity": {"all_valid": False, "validity_rate": 0.0},
                "correctness": {"exact_match": False, "tool_match_rate": 0.0},
                "success": False
            }
        
        # 1. EXECUTION METRICS - what actually happened
        executed_attempts = [a for a in attempts if a.get("was_executed")]
        successful_attempts = [a for a in attempts if a.get("success")]
        duplicate_attempts = [a for a in attempts if a.get("reason") == "duplicate"]
        
        execution_metrics = {
            "total_attempts": len(attempts),
            "executed_attempts": len(executed_attempts),
            "successful_attempts": len(successful_attempts),
            "duplicate_attempts": len(duplicate_attempts),
            "execution_rate": len(executed_attempts) / len(attempts),
            "success_rate": len(successful_attempts) / len(executed_attempts) if executed_attempts else 0.0,
            "execution_success": len(successful_attempts) > 0 and len(executed_attempts) == len(successful_attempts)
        }
        
        # 2. VALIDITY METRICS - could these attempts have been executed?
        # Count attempts that don't have <UNK> values (ignoring duplicates)
        non_duplicate_attempts = [a for a in attempts if a.get("reason") != "duplicate"]
        valid_attempts = []
        
        for attempt in non_duplicate_attempts:
            tool_call = attempt.get("tool_call", {})
            arguments = tool_call.get("arguments", {})
            
            # Check if any argument has <UNK>
            has_unk = any(value == "<UNK>" for value in arguments.values())
            if not has_unk:
                valid_attempts.append(attempt)
        
        validity_metrics = {
            "total_attempts": len(non_duplicate_attempts),
            "valid_attempts": len(valid_attempts),
            "validity_rate": len(valid_attempts) / len(non_duplicate_attempts) if non_duplicate_attempts else 0.0,
            "all_valid": len(valid_attempts) == len(non_duplicate_attempts) if non_duplicate_attempts else False
        }
        
        # 3. CORRECTNESS METRICS - do the attempts match ground truth?
        # Compare successful attempts against ground truth
        gt_tool_names = {tc.get("tool_name") for tc in ground_truth}
        successful_tool_names = {a.get("tool_call", {}).get("tool_name") for a in successful_attempts}
        
        matching_tools = gt_tool_names.intersection(successful_tool_names)
        tool_match_rate = len(matching_tools) / len(gt_tool_names) if gt_tool_names else 0.0
        
        # Check parameter correctness for successful attempts
        total_params = 0
        matching_params = 0
        
        for gt_tc in ground_truth:
            gt_tool_name = gt_tc.get("tool_name")
            gt_params = gt_tc.get("parameters", {})
            total_params += len(gt_params)
            
            # Find matching successful attempt
            for attempt in successful_attempts:
                tool_call = attempt.get("tool_call", {})
                if tool_call.get("tool_name") == gt_tool_name:
                    actual_params = tool_call.get("arguments", {})
                    
                    for param_name, gt_value in gt_params.items():
                        if param_name in actual_params and actual_params[param_name] == gt_value:
                            matching_params += 1
                    break
        
        param_match_rate = matching_params / total_params if total_params > 0 else 0.0
        
        # Exact match: same number of successful attempts as ground truth, and all match
        exact_match = (
            len(successful_attempts) == len(ground_truth) and
            tool_match_rate == 1.0 and
            param_match_rate == 1.0
        )
        
        correctness_metrics = {
            "exact_match": exact_match,
            "tool_match_rate": tool_match_rate,
            "param_match_rate": param_match_rate
        }
        
        # 4. OVERALL SUCCESS
        overall_success = (
            validity_metrics["all_valid"] and
            correctness_metrics["exact_match"] and
            execution_metrics["execution_success"]
        )
        
        return {
            "execution": execution_metrics,
            "validity": validity_metrics,
            "correctness": correctness_metrics,
            "success": overall_success
        }
        
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
                prefix = "User"
                if turn_type == "initial":
                    prefix = "User (initial)"
                elif turn_type == "follow_up":
                    prefix = "User (follow-up)"
                elif turn_type == "clarification_response":
                    prefix = "User (clarification)"
                    
                lines.append(f"\n{prefix}: {message}")
                
            elif role == "agent":
                prefix = "Agent"
                if turn_type:
                    prefix = f"Agent ({turn_type})"
                lines.append(f"\n{prefix}: {message}")
                
            else:
                lines.append(f"\n{role}: {message}")
        
        return "\n".join(lines)
    
    def visualize_questions(
        self,
        questions: List[Dict[str, Any]],
        all_candidate_questions: List[Dict[str, Any]] = None
    ) -> str:
        """
        Visualize the questions and their metrics.
        
        Args:
            questions: List of questions with metrics
            all_candidate_questions: List of all candidate questions
            
        Returns:
            Formatted questions string
        """
        if not questions and not all_candidate_questions:
            return "No questions asked."
            
        lines = ["Questions and Metrics:"]
        
        if all_candidate_questions:
            lines.append(f"\nTotal candidate questions: {len(all_candidate_questions)}")
            lines.append(f"Total selected questions: {len(questions)}")
            lines.append(f"Selection rate: {len(questions)/len(all_candidate_questions):.2f} if all_candidate_questions else 'N/A'")
            
            # Display selected questions
            if questions:
                lines.append("\nSelected Questions:")
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
        else:
            # Legacy format with only selected questions
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
        title: str = "Tool Calls",
        all_tool_call_attempts: List[Dict[str, Any]] = None
    ) -> str:
        """
        Visualize tool calls in a pretty format.
        
        Args:
            tool_calls: List of tool calls
            title: Title for the visualization
            all_tool_call_attempts: List of all tool call attempts (successful and failed)
            
        Returns:
            Formatted tool calls string
        """
        lines = []
        
        if all_tool_call_attempts:
            lines.append(f"All Tool Call Attempts: {len(all_tool_call_attempts)}")
            successful_attempts = sum(1 for a in all_tool_call_attempts if a.get("was_executed", False) and a.get("success", False))
            lines.append(f"Successful Attempts: {successful_attempts}")
            lines.append(f"Failed Attempts: {sum(1 for a in all_tool_call_attempts if a.get('was_executed', False) and not a.get('success', False))}")
            lines.append(f"Skipped Attempts: {sum(1 for a in all_tool_call_attempts if not a.get('was_executed', False))}")
            
            # Add detailed visualization of attempts if desired
            # (omitted for brevity)
            
        if not tool_calls:
            lines.append(f"\n{title}: None")
            return "\n".join(lines)
            
        lines.append(f"\n{title}:")
        
        for i, tc in enumerate(tool_calls):
            tool_name = tc.get("tool_name", "")
            arguments = tc.get("arguments", tc.get("parameters", {}))
            
            # Format parameters
            params_str = ", ".join([f"{k}={v}" for k, v in arguments.items()])
            
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
        validity = metrics.get("validity", {})
        correctness = metrics.get("correctness", {})
        conversation = metrics.get("conversation", {})
        questions = metrics.get("questions", {})
        
        lines = ["Evaluation Metrics:"]
        
        # Validity metrics
        lines.append("\nValidity Metrics:")
        lines.append(f"- Total Tool Calls: {validity.get('total_tool_calls', 0)}")
        lines.append(f"- Valid Tool Calls: {validity.get('valid_tool_calls', 0)}")
        lines.append(f"- Validity Rate: {validity.get('validity_rate', 0.0):.2f}")
        lines.append(f"- All Valid: {'Yes' if validity.get('all_valid', False) else 'No'}")
        
        # Correctness metrics
        lines.append("\nCorrectness Metrics:")
        lines.append(f"- Exact Match: {'Yes' if correctness.get('exact_match', False) else 'No'}")
        lines.append(f"- Tool Match Rate: {correctness.get('tool_match_rate', 0.0):.2f}")
        lines.append(f"- Parameter Match Rate: {correctness.get('param_match_rate', 0.0):.2f}")
        
        # Overall success
        lines.append(f"\nOverall Success: {'Yes' if metrics.get('success', False) else 'No'}")
        
        # Conversation metrics
        lines.append(f"\nConversation Metrics:")
        lines.append(f"- Total Turns (Human-Relevant): {conversation.get('total_turns', 0)}")
        lines.append(f"- User Turns: {conversation.get('user_turns', 0)}")
        lines.append(f"- Agent Turns: {conversation.get('agent_turns', 0)}")
        lines.append(f"- Clarification Questions: {conversation.get('clarification_questions', 0)}")
        lines.append(f"- Follow-up Requests: {conversation.get('follow_up_requests', 0)}")
        
        # Question metrics
        lines.append(f"\nQuestion Metrics:")
        lines.append(f"- Total Questions: {questions.get('total', 0)}")
        lines.append(f"- Total Candidate Questions: {questions.get('total_candidates', 0)}")
        if questions.get('total_candidates', 0) > 0:
            lines.append(f"- Selection Rate: {questions.get('total', 0) / questions.get('total_candidates', 1):.2f}")
        lines.append(f"- Average EVPI: {questions.get('average_evpi', 0.0):.4f}")
        lines.append(f"- Average Regret Reduction: {questions.get('average_regret_reduction', 0.0):.4f}")
        lines.append(f"- Average UCB Score: {questions.get('average_ucb_score', 0.0):.4f}")
        
        # Tool call attempt metrics 
        lines.append(f"\nTool Call Attempt Metrics:")
        lines.append(f"- Total Tool Call Attempts: {metrics.get('num_tool_call_attempts', 0)}")
        
        return "\n".join(lines)