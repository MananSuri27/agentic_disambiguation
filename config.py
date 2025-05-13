"""
Configuration for the agentic disambiguation system.
"""

from typing import Dict, Any, List

# LLM Configuration
LLM_CONFIG = {
    "provider": "ollama",  # Options: ollama, openai
    "model": "llama3",  # Model name
    "temperature": 0.2,  # Lower temperature for more deterministic outputs
    "max_tokens": 2000,  # Maximum tokens to generate
    "api_base": "http://localhost:11434"  # Base URL for Ollama
}

# Question Generation Configuration
QUESTION_CONFIG = {
    "max_candidates": 5,  # Maximum number of candidate questions to generate
    "base_threshold": 0.1,  # Base threshold for asking questions
    "threshold_alpha": 0.05,  # Threshold increase factor
    "exploration_constant": 1.0,  # Exploration constant for UCB
    "certainty_threshold": 0.9  # Overall certainty threshold to stop clarification
}

# Tool Execution Configuration
EXECUTION_CONFIG = {
    "strict_validation": False,  # Whether to strictly validate parameter values
    "max_attempts": 3  # Maximum number of attempts to execute a tool
}

# Simulation Configuration
SIMULATION_CONFIG = {
    "data_dir": "/fs/nexus-scratch/manans/disambiguation/data/examples",  # Directory for simulation data
    "results_dir": "simulation_results_test",  # Directory for simulation results
    "log_dir": "logs",  # Directory for logs
    "max_turns": 10  # Maximum number of conversation turns
}

# PDF Tool Registry Configuration
PDF_TOOLS_CONFIG = [
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
        "name": "redact_text",
        "description": "Redact specific text in a range of pages",
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
                "name": "object_name",
                "description": "List of text to redact",
                "domain": {
                    "type": "list",
                    "importance": 0.9
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
    },
    {
        "name": "highlight_text",
        "description": "Highlight specific text in a range of pages",
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
                "name": "object_name",
                "description": "List of text to highlight",
                "domain": {
                    "type": "list",
                    "importance": 0.9
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
    },
    {
        "name": "underline_text",
        "description": "Underline specific text in a range of pages",
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
                "name": "object_name",
                "description": "List of text to underline",
                "domain": {
                    "type": "list",
                    "importance": 0.9
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
    },
    {
        "name": "delete_page",
        "description": "Delete a specific page",
        "arguments": [
            {
                "name": "page_num",
                "description": "Page number to delete",
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
    },
    {
        "name": "delete_page_range",
        "description": "Delete a range of pages",
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
    },
    {
        "name": "add_signature",
        "description": "Add a signature to a page",
        "arguments": [
            {
                "name": "page_num",
                "description": "Page number to add signature to",
                "domain": {
                    "type": "numeric_range",
                    "values": [1, 1],  # Will be updated based on document
                    "importance": 0.9,
                    "data_dependent": True
                },
                "required": True
            },
            {
                "name": "position",
                "description": "Position for the signature",
                "domain": {
                    "type": "finite",
                    "values": ["top-left", "top-middle", "top-right", "bottom-right", "bottom-left", "bottom-middle"],
                    "importance": 0.7
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
    },
    {
        "name": "add_page_with_text",
        "description": "Add a new page with text content",
        "arguments": [
            {
                "name": "text_content",
                "description": "Text content for the new page",
                "domain": {
                    "type": "string",
                    "importance": 0.9
                },
                "required": True
            },
            {
                "name": "font_size",
                "description": "Font size for the text",
                "domain": {
                    "type": "numeric_range",
                    "values": [8, 72],
                    "importance": 0.6
                },
                "required": True
            },
            {
                "name": "page_num",
                "description": "Page number to insert at (1-indexed)",
                "domain": {
                    "type": "numeric_range",
                    "values": [1, 1],  # Will be updated based on document
                    "importance": 0.8,
                    "data_dependent": True
                },
                "required": True
            }
        ]
    },
    {
        "name": "add_watermark",
        "description": "Add a watermark to all pages",
        "arguments": [
            {
                "name": "watermark_text",
                "description": "Text for the watermark",
                "domain": {
                    "type": "string",
                    "importance": 0.9
                },
                "required": True
            },
            {
                "name": "transparency",
                "description": "Transparency level (0-1)",
                "domain": {
                    "type": "numeric_range",
                    "values": [0.0, 1.0],
                    "importance": 0.6
                },
                "required": True
            }
        ]
    },
    {
        "name": "add_password",
        "description": "Password-protect the PDF",
        "arguments": [
            {
                "name": "password",
                "description": "Password for protection",
                "domain": {
                    "type": "string",
                    "importance": 0.9
                },
                "required": True
            }
        ]
    }
]