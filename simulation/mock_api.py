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
            strict_validation: Whether to require exact parameter matching
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
        
        Important distinction: This method executes ANY valid tool call
        (one that has all required parameters), even if parameters 
        don't match ground truth. However, it provides feedback about
        parameter correctness.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            
        Returns:
            Execution result
        """
        # First check if the tool exists in ground truth
        if tool_name not in self.gt_tool_call_map:
            return {
                "success": False,
                "message": f"Tool '{tool_name}' is not part of the ground truth",
                "error": "INVALID_TOOL"
            }
        
        # Get the ground truth parameters
        gt_params = self.gt_tool_call_map[tool_name].get("parameters", {})
        
        # For required parameters, check if they're provided
        missing_params = []
        for param_name in gt_params:
            if param_name not in parameters:
                missing_params.append(param_name)
        
        # If missing required parameters, fail execution
        if missing_params:
            return {
                "success": False,
                "message": f"Missing required parameters: {', '.join(missing_params)}",
                "error": "MISSING_PARAMS",
                "details": {
                    "missing_params": missing_params
                }
            }
        
        # Compare parameters for correctness (but don't fail execution)
        incorrect_params = []
        if self.strict_validation:
            for param_name, gt_value in gt_params.items():
                if param_name in parameters and parameters[param_name] != gt_value:
                    incorrect_params.append({
                        "param": param_name,
                        "expected": gt_value,
                        "actual": parameters[param_name]
                    })
        
        # Check for extra parameters (informational only)
        extra_params = [p for p in parameters if p not in gt_params]
        
        # Execute the tool with provided parameters
        # Note: The execution succeeds as long as all required parameters are present
        execution_result = {
            "success": True,
            "message": f"Tool '{tool_name}' executed successfully",
            "output": {
                "tool_name": tool_name,
                "parameters": copy.deepcopy(parameters)
            }
        }
        
        # Add correctness information
        if incorrect_params:
            execution_result["parameter_correctness"] = {
                "all_correct": False,
                "incorrect_params": incorrect_params
            }
        else:
            execution_result["parameter_correctness"] = {
                "all_correct": True
            }
        
        if extra_params:
            execution_result["extra_parameters"] = extra_params
        
        return execution_result
    
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
            
            # If execution failed (missing params), stop processing
            if not result.get("success", False):
                break
        
        return results
    
    def validate_tool_calls_against_ground_truth(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate if a sequence of tool calls matches the ground truth.
        This is a separate validation method that checks correctness.
        
        Args:
            tool_calls: List of tool calls to validate
            
        Returns:
            Validation results
        """
        # Create sets of tool names for comparison
        gt_tool_names = {tc.get("tool_name") for tc in self.gt_tool_calls}
        actual_tool_names = {tc.get("tool_name") for tc in tool_calls}
        
        # Check for missing tools
        missing_tools = gt_tool_names - actual_tool_names
        
        # Check for extra tools
        extra_tools = actual_tool_names - gt_tool_names
        
        # Check parameter correctness
        tool_parameter_matches = {}
        for tc in tool_calls:
            tool_name = tc.get("tool_name", "")
            if tool_name in self.gt_tool_call_map:
                gt_params = self.gt_tool_call_map[tool_name].get("parameters", {})
                actual_params = tc.get("parameters", {})
                
                matching_params = []
                missing_params = []
                incorrect_params = []
                
                for param_name, gt_value in gt_params.items():
                    if param_name not in actual_params:
                        missing_params.append(param_name)
                    elif actual_params[param_name] == gt_value:
                        matching_params.append(param_name)
                    else:
                        incorrect_params.append({
                            "param": param_name,
                            "expected": gt_value,
                            "actual": actual_params[param_name]
                        })
                
                tool_parameter_matches[tool_name] = {
                    "matching_params": matching_params,
                    "missing_params": missing_params,
                    "incorrect_params": incorrect_params,
                    "all_correct": len(missing_params) == 0 and len(incorrect_params) == 0
                }
        
        # Determine overall correctness
        all_correct = (
            len(missing_tools) == 0 and 
            len(extra_tools) == 0 and
            all(v["all_correct"] for v in tool_parameter_matches.values())
        )
        
        return {
            "all_correct": all_correct,
            "missing_tools": list(missing_tools),
            "extra_tools": list(extra_tools),
            "tool_parameter_matches": tool_parameter_matches
        }