import math
from decimal import Decimal, InvalidOperation, getcontext
from typing import Dict, List, Tuple, Any, Optional, Union
import logging
from plugins.base_plugin import BasePlugin

try:
    import mpmath
except ImportError:
    # If mpmath is not available, we'll handle it gracefully in the methods
    pass

logger = logging.getLogger(__name__)

class MathPlugin(BasePlugin):
    """Plugin for mathematical operations.
    
    This plugin provides tools for various mathematical operations such as 
    basic arithmetic, logarithms, statistical functions, unit conversions,
    and more.
    """
    
    def __init__(self):
        """Initialize the math plugin."""
        self._name = "math"
        self._description = "Plugin for various mathematical operations and calculations"
        self._tools = self._generate_tool_definitions()
    
    @property
    def name(self) -> str:
        """Get the name of the plugin."""
        return self._name
    
    @property
    def description(self) -> str:
        """Get the description of the plugin."""
        return self._description
    
    def _generate_tool_definitions(self) -> List[Dict[str, Any]]:
        """Generate tool definitions for the math plugin."""
        return [
            {
                "name": "logarithm",
                "description": "Compute the logarithm of a number with adjustable precision",
                "arguments": [
                    {
                        "name": "value",
                        "description": "The number to compute the logarithm of",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0.000001, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "base",
                        "description": "The base of the logarithm",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0.000001, 1000],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "precision",
                        "description": "Desired precision for the result",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 100],
                            "importance": 0.5
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "mean",
                "description": "Calculate the mean of a list of numbers",
                "arguments": [
                    {
                        "name": "numbers",
                        "description": "List of numbers to calculate the mean of",
                        "domain": {
                            "type": "list",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "standard_deviation",
                "description": "Calculate the standard deviation of a list of numbers",
                "arguments": [
                    {
                        "name": "numbers",
                        "description": "List of numbers to calculate the standard deviation of",
                        "domain": {
                            "type": "list",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "si_unit_conversion",
                "description": "Convert a value from one SI unit to another",
                "arguments": [
                    {
                        "name": "value",
                        "description": "Value to be converted",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "unit_in",
                        "description": "Unit of the input value",
                        "domain": {
                            "type": "finite",
                            "values": ["km", "m", "cm", "mm", "um", "nm"],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "unit_out",
                        "description": "Unit to convert the value to",
                        "domain": {
                            "type": "finite",
                            "values": ["km", "m", "cm", "mm", "um", "nm"],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "imperial_si_conversion",
                "description": "Convert a value between imperial and SI units",
                "arguments": [
                    {
                        "name": "value",
                        "description": "Value to be converted",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "unit_in",
                        "description": "Unit of the input value",
                        "domain": {
                            "type": "finite",
                            "values": ["cm", "in", "m", "ft", "yd", "km", "miles", "kg", "lb", "celsius", "fahrenheit"],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "unit_out",
                        "description": "Unit to convert the value to",
                        "domain": {
                            "type": "finite",
                            "values": ["cm", "in", "m", "ft", "yd", "km", "miles", "kg", "lb", "celsius", "fahrenheit"],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "add",
                "description": "Add two numbers",
                "arguments": [
                    {
                        "name": "a",
                        "description": "First number",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "b",
                        "description": "Second number",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "subtract",
                "description": "Subtract one number from another",
                "arguments": [
                    {
                        "name": "a",
                        "description": "Number to subtract from",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "b",
                        "description": "Number to subtract",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "multiply",
                "description": "Multiply two numbers",
                "arguments": [
                    {
                        "name": "a",
                        "description": "First number",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "b",
                        "description": "Second number",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "divide",
                "description": "Divide one number by another",
                "arguments": [
                    {
                        "name": "a",
                        "description": "Numerator",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "b",
                        "description": "Denominator (cannot be zero)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "power",
                "description": "Raise a number to a power",
                "arguments": [
                    {
                        "name": "base",
                        "description": "The base number",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "exponent",
                        "description": "The exponent",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-100, 100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "square_root",
                "description": "Calculate the square root of a number with adjustable precision",
                "arguments": [
                    {
                        "name": "number",
                        "description": "The number to calculate the square root of",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "precision",
                        "description": "Desired precision for the result",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 100],
                            "importance": 0.5
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "absolute_value",
                "description": "Calculate the absolute value of a number",
                "arguments": [
                    {
                        "name": "number",
                        "description": "The number to calculate the absolute value of",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "round_number",
                "description": "Round a number to a specified number of decimal places",
                "arguments": [
                    {
                        "name": "number",
                        "description": "The number to round",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "decimal_places",
                        "description": "The number of decimal places to round to",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 20],
                            "importance": 0.5
                        },
                        "required": False,
                        "default": 0
                    }
                ]
            },
            {
                "name": "percentage",
                "description": "Calculate the percentage of a part relative to a whole",
                "arguments": [
                    {
                        "name": "part",
                        "description": "The part value",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "whole",
                        "description": "The whole value (cannot be zero)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [-1e100, 1e100],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "min_value",
                "description": "Find the minimum value in a list of numbers",
                "arguments": [
                    {
                        "name": "numbers",
                        "description": "List of numbers to find the minimum from",
                        "domain": {
                            "type": "list",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "max_value",
                "description": "Find the maximum value in a list of numbers",
                "arguments": [
                    {
                        "name": "numbers",
                        "description": "List of numbers to find the maximum from",
                        "domain": {
                            "type": "list",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "sum_values",
                "description": "Calculate the sum of a list of numbers",
                "arguments": [
                    {
                        "name": "numbers",
                        "description": "List of numbers to sum",
                        "domain": {
                            "type": "list",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            }
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of tools provided by this plugin."""
        return self._tools
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with the given parameters."""
        # Validate parameters first
        is_valid, error = self.validate_tool_call(tool_name, parameters)
        if not is_valid:
            return {
                "success": False,
                "message": error,
                "error": "INVALID_PARAMETERS"
            }
        
        try:
            # Dispatch to appropriate method based on tool name
            if tool_name == "logarithm":
                result = self._logarithm(**parameters)
            elif tool_name == "mean":
                result = self._mean(**parameters)
            elif tool_name == "standard_deviation":
                result = self._standard_deviation(**parameters)
            elif tool_name == "si_unit_conversion":
                result = self._si_unit_conversion(**parameters)
            elif tool_name == "imperial_si_conversion":
                result = self._imperial_si_conversion(**parameters)
            elif tool_name == "add":
                result = self._add(**parameters)
            elif tool_name == "subtract":
                result = self._subtract(**parameters)
            elif tool_name == "multiply":
                result = self._multiply(**parameters)
            elif tool_name == "divide":
                result = self._divide(**parameters)
            elif tool_name == "power":
                result = self._power(**parameters)
            elif tool_name == "square_root":
                result = self._square_root(**parameters)
            elif tool_name == "absolute_value":
                result = self._absolute_value(**parameters)
            elif tool_name == "round_number":
                result = self._round_number(**parameters)
            elif tool_name == "percentage":
                result = self._percentage(**parameters)
            elif tool_name == "min_value":
                result = self._min_value(**parameters)
            elif tool_name == "max_value":
                result = self._max_value(**parameters)
            elif tool_name == "sum_values":
                result = self._sum_values(**parameters)
            else:
                return {
                    "success": False,
                    "message": f"Unknown tool: {tool_name}",
                    "error": "UNKNOWN_TOOL"
                }
            
            # Handle error responses
            if "error" in result:
                return {
                    "success": False,
                    "message": result["error"],
                    "error": "EXECUTION_ERROR"
                }
            
            # Return success with result
            return {
                "success": True,
                "message": f"Successfully executed {tool_name}",
                "output": result
            }
            
        except Exception as e:
            logger.exception(f"Error executing {tool_name}: {e}")
            return {
                "success": False,
                "message": str(e),
                "error": "EXECUTION_ERROR"
            }
    
    def validate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate a tool call before execution."""
        # Find the tool definition
        tool_def = None
        for tool in self._tools:
            if tool["name"] == tool_name:
                tool_def = tool
                break
        
        if not tool_def:
            return False, f"Unknown tool: {tool_name}"
        
        # Check required arguments
        for arg_def in tool_def.get("arguments", []):
            if arg_def.get("required", True) and arg_def["name"] not in parameters:
                return False, f"Missing required argument: {arg_def['name']}"
            
            # If the argument is provided, validate its value
            if arg_def["name"] in parameters and parameters[arg_def["name"]] != "<UNK>":
                value = parameters[arg_def["name"]]
                
                # Validate based on domain type
                domain = arg_def.get("domain", {})
                domain_type = domain.get("type", "string")
                
                if domain_type == "numeric_range":
                    try:
                        val = float(value)
                        start, end = domain.get("values", [-1e100, 1e100])
                        if not (start <= val <= end):
                            return False, f"Value {value} for {arg_def['name']} is out of range [{start}, {end}]"
                    except (ValueError, TypeError):
                        return False, f"Invalid numeric value for {arg_def['name']}: {value}"
                
                elif domain_type == "finite":
                    if value not in domain.get("values", []):
                        values_str = ", ".join(str(v) for v in domain.get("values", []))
                        return False, f"Invalid value for {arg_def['name']}: {value}. Expected one of: {values_str}"
                
                elif domain_type == "list":
                    if not isinstance(value, list):
                        return False, f"Invalid list value for {arg_def['name']}: {value}"
        
        return True, None
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """Get math-specific prompt templates."""
        return {
            "tool_selection": """
You are an AI assistant that helps users with mathematical calculations.

Conversation history:
{conversation_history}

User query: "{user_query}"

Available tools:
{tool_descriptions}

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What mathematical operation or calculation is the user asking for?
2. Which math tool(s) are needed to complete this task?
3. What parameters are needed for each tool?
4. Which parameters can be determined from the query, and which are uncertain?

Return your response as a JSON object with the following structure:
{
  "reasoning": "Your step-by-step reasoning about what tools to use and why",
  "tool_calls": [
    {
      "tool_name": "name_of_tool",
      "arguments": {
        "arg1": "value1",
        "arg2": "<UNK>"
      }
    }
  ]
}
""",
            "question_generation": """
You are an AI assistant that helps users with mathematical calculations.

Conversation history:
{conversation_history}

Original user query: "{user_query}"

I've determined that the following tool calls are needed, but some arguments are uncertain:

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
{
  "questions": [
    {
      "question": "A clear question to ask the user",
      "target_args": [["tool_name", "arg_name"], ["tool_name", "other_arg_name"]]
    }
  ]
}
"""
        }

    # Tool implementation methods
    def _logarithm(self, value: float, base: float, precision: int) -> Dict[str, Any]:
        """Compute the logarithm of a number with adjustable precision."""
        try:
            if 'mpmath' not in globals():
                return {"error": "mpmath library is not available"}
                
            # Set precision for mpmath
            mpmath.mp.dps = precision

            # Use mpmath for high-precision logarithmic calculations
            result = float(mpmath.log(value) / mpmath.log(base))

            return {"result": result}
        except Exception as e:
            return {"error": str(e)}

    def _mean(self, numbers: List[float]) -> Dict[str, Any]:
        """Calculate the mean of a list of numbers."""
        if not numbers:
            return {"error": "Cannot calculate mean of an empty list"}
        try:
            return {"result": sum(numbers) / len(numbers)}
        except TypeError:
            return {"error": "All elements in the list must be numbers"}

    def _standard_deviation(self, numbers: List[float]) -> Dict[str, Any]:
        """Calculate the standard deviation of a list of numbers."""
        if not numbers:
            return {"error": "Cannot calculate standard deviation of an empty list"}
        try:
            mean = sum(numbers) / len(numbers)
            variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
            return {"result": math.sqrt(variance)}
        except TypeError:
            return {"error": "All elements in the list must be numbers"}

    def _si_unit_conversion(self, value: float, unit_in: str, unit_out: str) -> Dict[str, Any]:
        """Convert a value from one SI unit to another."""
        to_meters = {"km": 1000, "m": 1, "cm": 0.01, "mm": 0.001, "um": 1e-6, "nm": 1e-9}
        from_meters = {unit: 1 / factor for unit, factor in to_meters.items()}

        if not isinstance(value, (int, float)):
            return {"error": "Value must be a number"}

        if unit_in not in to_meters or unit_out not in from_meters:
            return {
                "error": f"Conversion from '{unit_in}' to '{unit_out}' is not supported"
            }

        try:
            value_in_meters = value * to_meters[unit_in]
            result = value_in_meters * from_meters[unit_out]
            return {"result": result}
        except OverflowError:
            return {"error": "Conversion resulted in a value too large to represent"}

    def _imperial_si_conversion(self, value: float, unit_in: str, unit_out: str) -> Dict[str, Any]:
        """Convert a value between imperial and SI units."""
        conversion = {
            "cm_to_in": 0.393701,
            "in_to_cm": 2.54,
            "m_to_ft": 3.28084,
            "ft_to_m": 0.3048,
            "m_to_yd": 1.09361,
            "yd_to_m": 0.9144,
            "km_to_miles": 0.621371,
            "miles_to_km": 1.60934,
            "kg_to_lb": 2.20462,
            "lb_to_kg": 0.453592,
            "celsius_to_fahrenheit": 1.8,
            "fahrenheit_to_celsius": 5 / 9,
        }

        if not isinstance(value, (int, float)):
            return {"error": "Value must be a number"}

        if unit_in == unit_out:
            return {"result": value}

        conversion_key = f"{unit_in}_to_{unit_out}"
        if conversion_key not in conversion:
            return {
                "error": f"Conversion from '{unit_in}' to '{unit_out}' is not supported"
            }

        try:
            if unit_in == "celsius" and unit_out == "fahrenheit":
                result = (value * conversion[conversion_key]) + 32
            elif unit_in == "fahrenheit" and unit_out == "celsius":
                result = (value - 32) * conversion[conversion_key]
            else:
                result = value * conversion[conversion_key]

            return {"result": result}
        except OverflowError:
            return {"error": "Conversion resulted in a value too large to represent"}

    def _add(self, a: float, b: float) -> Dict[str, Any]:
        """Add two numbers."""
        try:
            return {"result": a + b}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

    def _subtract(self, a: float, b: float) -> Dict[str, Any]:
        """Subtract one number from another."""
        try:
            return {"result": a - b}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

    def _multiply(self, a: float, b: float) -> Dict[str, Any]:
        """Multiply two numbers."""
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return {"error": "Both inputs must be numbers"}

        try:
            return {"result": a * b}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

    def _divide(self, a: float, b: float) -> Dict[str, Any]:
        """Divide one number by another."""
        try:
            if b == 0:
                return {"error": "Cannot divide by zero"}
            return {"result": a / b}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

    def _power(self, base: float, exponent: float) -> Dict[str, Any]:
        """Raise a number to a power."""
        try:
            return {"result": base**exponent}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

    def _square_root(self, number: float, precision: int) -> Dict[str, Any]:
        """Calculate the square root of a number with adjustable precision."""
        try:
            if number < 0:
                return {"error": "Cannot calculate square root of a negative number"}

            # Set the precision for the decimal context
            getcontext().prec = precision

            # Use Decimal for high-precision square root calculation
            decimal_number = Decimal(number)

            result = float(decimal_number.sqrt())
            return {"result": result}
        except (TypeError, InvalidOperation):
            return {
                "error": "Input must be a number or computation resulted in an invalid operation"
            }

    def _absolute_value(self, number: float) -> Dict[str, Any]:
        """Calculate the absolute value of a number."""
        try:
            return {"result": abs(number)}
        except TypeError:
            return {"error": "Input must be a number"}

    def _round_number(self, number: float, decimal_places: int = 0) -> Dict[str, Any]:
        """Round a number to a specified number of decimal places."""
        try:
            return {"result": round(number, decimal_places)}
        except TypeError:
            return {
                "error": "First input must be a number, second input must be an integer"
            }

    def _percentage(self, part: float, whole: float) -> Dict[str, Any]:
        """Calculate the percentage of a part relative to a whole."""
        try:
            if whole == 0:
                return {"error": "Whole value cannot be zero"}
            return {"result": (part / whole) * 100}
        except TypeError:
            return {"error": "Both inputs must be numbers"}

    def _min_value(self, numbers: List[float]) -> Dict[str, Any]:
        """Find the minimum value in a list of numbers."""
        if not numbers:
            return {"error": "Cannot find minimum of an empty list"}
        try:
            return {"result": min(numbers)}
        except TypeError:
            return {"error": "All elements in the list must be numbers"}

    def _max_value(self, numbers: List[float]) -> Dict[str, Any]:
        """Find the maximum value in a list of numbers."""
        if not numbers:
            return {"error": "Cannot find maximum of an empty list"}
        try:
            return {"result": max(numbers)}
        except TypeError:
            return {"error": "All elements in the list must be numbers"}

    def _sum_values(self, numbers: List[float]) -> Dict[str, Any]:
        """Calculate the sum of a list of numbers."""
        if not numbers:
            return {"error": "Cannot calculate sum of an empty list"}
        try:
            return {"result": sum(numbers)}
        except TypeError:
            return {"error": "All elements in the list must be numbers"}