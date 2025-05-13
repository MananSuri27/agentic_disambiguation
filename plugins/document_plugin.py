import logging
from typing import Dict, List, Any, Optional, Tuple
import copy
from plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

class DocumentPlugin(BasePlugin):
    """Plugin for document-related operations.
    
    This plugin provides tools for working with PDF documents, including
    viewing, editing, converting, and manipulating PDF files.
    """
    
    def __init__(self):
        """Initialize the document plugin."""
        self._tools = self._load_tool_definitions()
        self._current_context = {
            "number_of_pages": 1,  # Default, will be updated from context
            "pdf_name": "document.pdf"  # Default, will be updated from context
        }
    
    @property
    def name(self) -> str:
        return "document"
    
    @property
    def description(self) -> str:
        return "Plugin for document-related operations like viewing, editing, and converting PDFs."
    
    def _load_tool_definitions(self) -> List[Dict[str, Any]]:
        """Load tool definitions for PDF operations."""
        # This is based on the PDF_TOOLS_CONFIG from config.py
        return [
            {
                "name": "duplicate",
                "description": "Create a duplicate of the PDF file",
                "arguments": [
                    {
                        "name": "output_filename",
                        "description": "Name of the output file",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "rename",
                "description": "Rename the PDF file",
                "arguments": [
                    {
                        "name": "output_filename",
                        "description": "New name for the file",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "search",
                "description": "Search for content in the PDF",
                "arguments": [
                    {
                        "name": "object_name",
                        "description": "Term or type of object to search for",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "count_pages",
                "description": "Count the number of pages in the PDF",
                "arguments": []
            },
            {
                "name": "compress_file",
                "description": "Compress the PDF file",
                "arguments": [
                    {
                        "name": "output_filename",
                        "description": "Name of the compressed output file",
                        "domain": {
                            "type": "string",
                            "importance": 0.6
                        },
                        "required": False,
                        "default": None
                    }
                ]
            },
            {
                "name": "convert",
                "description": "Convert the PDF to another format",
                "arguments": [
                    {
                        "name": "format",
                        "description": "Target format for conversion",
                        "domain": {
                            "type": "finite",
                            "values": ["pptx", "doc", "png", "jpeg", "tiff"],
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "output_filename",
                        "description": "Name of the output file",
                        "domain": {
                            "type": "string",
                            "importance": 0.7
                        },
                        "required": True
                    },
                    {
                        "name": "zip",
                        "description": "Whether to zip the output (for image formats)",
                        "domain": {
                            "type": "boolean",
                            "importance": 0.4
                        },
                        "required": False,
                        "default": False
                    }
                ]
            },
            {
                "name": "add_comment",
                "description": "Add a comment to a page",
                "arguments": [
                    {
                        "name": "page_num",
                        "description": "Page number to add comment to",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 1],  # Will be updated based on document
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "coordinates",
                        "description": "Coordinates for the comment [x, y]",
                        "domain": {
                            "type": "list",
                            "importance": 0.6
                        },
                        "required": True
                    },
                    {
                        "name": "font_size",
                        "description": "Font size for the comment",
                        "domain": {
                            "type": "numeric_range",
                            "values": [8, 72],
                            "importance": 0.5
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "redact_page_range",
                "description": "Redact content from a range of pages",
                "arguments": [
                    {
                        "name": "start",
                        "description": "Start page number (inclusive)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 1],  # Will be updated based on document
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "end",
                        "description": "End page number (inclusive)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 1],  # Will be updated based on document
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "extract_pages",
                "description": "Extract a range of pages to a new file",
                "arguments": [
                    {
                        "name": "start",
                        "description": "Start page number (inclusive)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 1],  # Will be updated based on document
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "end",
                        "description": "End page number (inclusive)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 1],  # Will be updated based on document
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "overwrite",
                        "description": "Whether to overwrite the original file",
                        "domain": {
                            "type": "boolean",
                            "importance": 0.7
                        },
                        "required": True
                    },
                    {
                        "name": "output_pathname",
                        "description": "Name of the output file if not overwriting",
                        "domain": {
                            "type": "string",
                            "importance": 0.7
                        },
                        "required": False,
                        "default": None
                    }
                ]
            }
            # Additional tools would continue here... but omitted for brevity
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of tools provided by this plugin."""
        return self._tools
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with the given parameters."""
        # Validate the tool call first
        is_valid, error = self.validate_tool_call(tool_name, parameters)
        if not is_valid:
            return {
                "success": False,
                "message": f"Validation failed: {error}",
                "error": error
            }
        
        # This would call actual PDF operations in a real implementation
        # For now, return a mock successful result with appropriate messaging
        if tool_name == "duplicate":
            output_filename = parameters.get("output_filename", "")
            return {
                "success": True,
                "message": f"Successfully duplicated {self._current_context['pdf_name']} to {output_filename}",
                "output": {
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            }
        
        elif tool_name == "rename":
            output_filename = parameters.get("output_filename", "")
            return {
                "success": True,
                "message": f"Successfully renamed {self._current_context['pdf_name']} to {output_filename}",
                "output": {
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            }
        
        elif tool_name == "search":
            object_name = parameters.get("object_name", "")
            return {
                "success": True,
                "message": f"Found '{object_name}' in {self._current_context['pdf_name']}",
                "output": {
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "results": ["page 1", "page 3"]  # Mock results
                }
            }
        
        elif tool_name == "count_pages":
            return {
                "success": True,
                "message": f"{self._current_context['pdf_name']} has {self._current_context['number_of_pages']} pages",
                "output": {
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "page_count": self._current_context['number_of_pages']
                }
            }
        
        elif tool_name == "extract_pages":
            start = parameters.get("start", 1)
            end = parameters.get("end", 1)
            output_pathname = parameters.get("output_pathname", "extracted.pdf")
            
            return {
                "success": True,
                "message": f"Successfully extracted pages {start}-{end} to {output_pathname}",
                "output": {
                    "tool_name": tool_name,
                    "parameters": parameters
                }
            }
        
        # Handle other tools similarly
        # Default case for tools not explicitly handled
        return {
            "success": True,
            "message": f"Executed {tool_name} with parameters {parameters}",
            "output": {
                "tool_name": tool_name,
                "parameters": parameters
            }
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
            if arg_def["name"] in parameters:
                value = parameters[arg_def["name"]]
                
                # Skip validation for unknown values
                if value == "<UNK>":
                    if arg_def.get("required", True):
                        return False, f"Required argument {arg_def['name']} has unknown value"
                    continue
                
                # Validate based on domain type
                domain = arg_def.get("domain", {})
                domain_type = domain.get("type", "string")
                
                if domain_type == "numeric_range":
                    try:
                        val = float(value)
                        start, end = domain.get("values", [1, 1])
                        if not (start <= val <= end):
                            return False, f"Value {value} for {arg_def['name']} is out of range [{start}, {end}]"
                    except (ValueError, TypeError):
                        return False, f"Invalid numeric value for {arg_def['name']}: {value}"
                
                elif domain_type == "finite":
                    if value not in domain.get("values", []):
                        values_str = ", ".join(str(v) for v in domain.get("values", []))
                        return False, f"Invalid value for {arg_def['name']}: {value}. Expected one of: {values_str}"
                
                elif domain_type == "boolean":
                    if not isinstance(value, bool) and value not in [True, False, "true", "false", "True", "False"]:
                        return False, f"Invalid boolean value for {arg_def['name']}: {value}"
                
                elif domain_type == "list":
                    if not isinstance(value, list):
                        return False, f"Invalid list value for {arg_def['name']}: {value}"
        
        return True, None
    
    def get_domain_updates_from_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update tool domains based on context."""
        updates = {}
        
        # Update the current context
        self._current_context.update({
            k: v for k, v in context.items() 
            if k in ["number_of_pages", "pdf_name"]
        })
        
        # Update numeric range domains based on number of pages
        num_pages = self._current_context.get("number_of_pages", 1)
        
        for tool in self._tools:
            for arg in tool.get("arguments", []):
                domain = arg.get("domain", {})
                if domain.get("data_dependent") and domain.get("type") == "numeric_range":
                    if arg["name"] in ["page_num", "start", "end"]:
                        updates[f"{tool['name']}.{arg['name']}"] = {
                            "type": "numeric_range",
                            "values": [1, num_pages]
                        }
        
        return updates
    
    def get_uncertainty_context(self) -> Dict[str, Any]:
        """Get document-specific context for uncertainty calculation."""
        return {
            "number_of_pages": self._current_context.get("number_of_pages", 1),
            "pdf_name": self._current_context.get("pdf_name", "document.pdf")
        }
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """Get document-specific prompt templates."""
        return {
            "tool_selection": """
You are an AI assistant that helps users with document operations.

User query: "{user_query}"

Available tools:
{tool_descriptions}

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What is the user trying to accomplish with the document?
2. Which tool(s) are needed to complete this task?
3. What parameters are needed for each tool?
4. Which parameters can be determined from the query, and which are uncertain?
""",
            "question_generation": """
You are an AI assistant that helps users with document operations.

User query: "{user_query}"

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
"""
        }