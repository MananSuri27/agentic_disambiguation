from typing import Dict, List, Any, Optional, Tuple
import logging
import json
import copy

logger = logging.getLogger(__name__)

class MockAPIClient:
    """Mock API client for simulating tool execution."""
    
    def __init__(
        self,
        ground_truth: Dict[str, Any],
        strict_validation: bool = False
    ):
        """
        Initialize a mock API client.
        
        Args:
            ground_truth: Ground truth data for validation
            strict_validation: Whether to strictly validate parameter values
        """
        self.ground_truth = ground_truth
        self.strict_validation = strict_validation
        
        # Extract ground truth tool calls
        self.gt_tool_calls = ground_truth.get("ground_truth_tool_calls", [])
        
        # Create a map for easier lookup
        self.gt_tool_call_map = {}
        for tc in self.gt_tool_calls:
            tool_name = tc.get("tool_name")
            if tool_name:
                self.gt_tool_call_map[tool_name] = tc
    
    def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool call via the mock API.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            
        Returns:
            Execution result
        """
        # Check if the tool exists in ground truth
        if tool_name not in self.gt_tool_call_map:
            return {
                "success": False,
                "message": f"Tool '{tool_name}' is not part of the ground truth",
                "error": "INVALID_TOOL"
            }
        
        # Get the ground truth parameters
        gt_params = self.gt_tool_call_map[tool_name].get("parameters", {})
        
        # Compare parameters
        missing_params = []
        incorrect_params = []
        
        for param_name, gt_value in gt_params.items():
            if param_name not in parameters:
                "ok"
                missing_params.append(param_name)
            elif self.strict_validation and parameters[param_name] != gt_value:
                incorrect_params.append({
                    "param": param_name,
                    "expected": gt_value,
                    "actual": parameters[param_name]
                })
        
        # Check for extra parameters
        extra_params = [p for p in parameters if p not in gt_params]
        
        # If there are issues, return an error
        if missing_params:
            return {
                "success": False,
                "message": f"Missing required parameters: {', '.join(missing_params)}",
                "error": "MISSING_PARAMS",
                "details": {
                    "missing_params": missing_params
                }
            }
        
        if extra_params:
            return {
                "success": False,
                "message": f"Unexpected parameters: {', '.join(extra_params)}",
                "error": "EXTRA_PARAMS",
                "details": {
                    "extra_params": extra_params
                }
            }
        
        if incorrect_params:
            return {
                "success": False,
                "message": "Incorrect parameter values",
                "error": "INCORRECT_PARAMS",
                "details": {
                    "incorrect_params": incorrect_params
                }
            }
        
        # If all checks pass, return success
        return {
            "success": True,
            "message": f"Tool '{tool_name}' executed successfully",
            "output": {
                "tool_name": tool_name,
                "parameters": copy.deepcopy(parameters)
            }
        }
    
    def execute_tool_sequence(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute a sequence of tool calls.
        
        Args:
            tool_calls: List of tool calls to execute
            
        Returns:
            List of execution results
        """
        results = []
        
        for tc in tool_calls:
            tool_name = tc.get("tool_name", "")
            parameters = tc.get("parameters", {})
            
            result = self.execute_tool(tool_name, parameters)
            results.append(result)
            
            # If execution failed, stop processing further tool calls
            if not result.get("success", False):
                break
        
        return results
    
    def validate_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> Tuple[bool, List[Dict[str, Any]], str]:
        """
        Validate if a sequence of tool calls matches the ground truth.
        
        Args:
            tool_calls: List of tool calls to validate
            
        Returns:
            Tuple of (is_valid, missing_tool_calls, error_message)
        """
        # Create sets of tool names for comparison
        gt_tool_names = {tc.get("tool_name") for tc in self.gt_tool_calls}
        actual_tool_names = {tc.get("tool_name") for tc in tool_calls}
        
        # Check for missing tools
        missing_tools = gt_tool_names - actual_tool_names
        
        # Check for extra tools
        extra_tools = actual_tool_names - gt_tool_names
        
        # Execute each tool call to validate parameters
        execution_results = self.execute_tool_sequence(tool_calls)
        
        # Check if all executions succeeded
        all_succeeded = all(res.get("success", False) for res in execution_results)
        
        # Identify missing tool calls
        missing_tool_calls = []
        for tool_name in missing_tools:
            missing_tool_calls.append(
                self.gt_tool_call_map.get(tool_name, {"tool_name": tool_name})
            )
        
        # Determine validation result
        is_valid = (not missing_tools and not extra_tools and all_succeeded)
        
        # Create error message
        error_message = ""
        if missing_tools:
            error_message += f"Missing tool calls: {', '.join(missing_tools)}. "
        if extra_tools:
            error_message += f"Extra tool calls: {', '.join(extra_tools)}. "
        if not all_succeeded:
            failed_results = [res for res in execution_results if not res.get("success", False)]
            for res in failed_results:
                error_message += f"{res.get('message', 'Unknown error')}. "
        
        if not error_message:
            error_message = "All tool calls validated successfully."
        
        return is_valid, missing_tool_calls, error_message