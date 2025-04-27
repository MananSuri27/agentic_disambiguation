from enum import Enum
from typing import Dict, List, Union, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)

class DomainType(Enum):
    """Enumeration for different types of argument domains."""
    FINITE = "finite"  # Finite set of values (e.g., enum)
    NUMERIC_RANGE = "numeric_range"  # Range of numbers (e.g., page numbers)
    STRING = "string"  # Any string
    BOOLEAN = "boolean"  # True or False
    LIST = "list"  # List of values
    CUSTOM = "custom"  # Custom domain with validation function

class ArgumentDomain:
    """Class representing the domain of an argument."""
    
    def __init__(
        self,
        domain_type: DomainType,
        values: Any = None,
        importance: float = 0.5,
        validator: Optional[Callable] = None,
        description: str = "",
        data_dependent: bool = False
    ):
        """
        Initialize an argument domain.
        
        Args:
            domain_type: Type of the domain
            values: Possible values for the domain (depends on domain_type)
            importance: Importance score (0-1) for this argument
            validator: Function to validate values for this domain
            description: Human-readable description of the domain
            data_dependent: Whether the domain depends on external data
        """
        self.domain_type = domain_type
        self.values = values
        self.importance = importance
        self.validator = validator
        self.description = description
        self.data_dependent = data_dependent
        
    def get_size(self) -> Union[int, float]:
        """Get the size of the domain."""
        if self.domain_type == DomainType.FINITE:
            return len(self.values)
        elif self.domain_type == DomainType.BOOLEAN:
            return 2
        elif self.domain_type == DomainType.NUMERIC_RANGE:
            # For numeric ranges, return the number of possible values
            start, end = self.values
            return max(1, end - start + 1)
        else:
            # For infinite domains like strings
            return float('inf')
    
    def is_valid(self, value: Any) -> bool:
        """Check if a value is valid for this domain."""

        if self.validator:
            return self.validator(value)
            
        if self.domain_type == DomainType.FINITE:
            return value in self.values
        elif self.domain_type == DomainType.NUMERIC_RANGE:
            start, end = self.values
            return isinstance(value, (int, float)) and start <= value <= end
        elif self.domain_type == DomainType.BOOLEAN:
            return isinstance(value, bool)
        elif self.domain_type == DomainType.LIST:
            # For lists, each element should be valid according to the element domain
            if not isinstance(value, list):
                return False
            element_domain = self.values
            return all(element_domain.is_valid(item) for item in value)
        else:
            # For string and custom domains, assume valid unless validator says otherwise
            return True
    
    def to_dict(self) -> Dict:
        """Convert the domain to a dictionary representation."""
        domain_dict = {
            "type": self.domain_type.value,
            "importance": self.importance,
            "description": self.description,
            "data_dependent": self.data_dependent
        }
        
        # Add domain-specific values
        if self.domain_type == DomainType.FINITE:
            domain_dict["values"] = self.values
        elif self.domain_type == DomainType.NUMERIC_RANGE:
            domain_dict["range"] = self.values
        elif self.domain_type == DomainType.LIST:
            domain_dict["element_domain"] = self.values.to_dict()
            
        return domain_dict

    def __str__(self) -> str:
        """String representation of the domain."""
        if self.domain_type == DomainType.FINITE:
            return f"One of: {', '.join(str(v) for v in self.values)}"
        elif self.domain_type == DomainType.NUMERIC_RANGE:
            start, end = self.values
            return f"Number between {start} and {end}"
        elif self.domain_type == DomainType.BOOLEAN:
            return "True or False"
        elif self.domain_type == DomainType.STRING:
            return "Any text string"
        elif self.domain_type == DomainType.LIST:
            return f"List of values, each: {self.values}"
        else:
            return self.description or "Custom domain"


class Argument:
    """Class representing a tool argument."""
    
    def __init__(
        self,
        name: str,
        domain: ArgumentDomain,
        description: str = "",
        required: bool = True,
        default: Any = None
    ):
        """
        Initialize an argument.
        
        Args:
            name: Name of the argument
            domain: Domain of valid values
            description: Human-readable description
            required: Whether the argument is required
            default: Default value if not provided
        """
        self.name = name
        self.domain = domain
        self.description = description
        self.required = required
        self.default = default
    
    def to_dict(self) -> Dict:
        """Convert the argument to a dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "domain": self.domain.to_dict()
        }


class Tool:
    """Class representing a tool in the system."""
    
    def __init__(
        self,
        name: str,
        description: str,
        arguments: List[Argument]
    ):
        """
        Initialize a tool.
        
        Args:
            name: Name of the tool
            description: Human-readable description
            arguments: List of arguments for the tool
        """
        self.name = name
        self.description = description
        self.arguments = arguments
        
        # Create a mapping of argument names to arguments for faster lookup
        self.argument_map = {arg.name: arg for arg in arguments}
    
    def to_dict(self) -> Dict:
        """Convert the tool to a dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [arg.to_dict() for arg in self.arguments]
        }
    
    def get_argument(self, name: str) -> Optional[Argument]:
        """Get an argument by name."""
        return self.argument_map.get(name)


class ToolRegistry:
    """Registry for tools in the system."""
    
    def __init__(self):
        """Initialize an empty tool registry."""
        self.tools: Dict[str, Tool] = {}
    
    def register_tool(self, tool: Tool) -> None:
        """Register a tool in the registry."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def get_all_tools(self) -> List[Tool]:
        """Get all registered tools."""
        return list(self.tools.values())
    
    def get_tool_descriptions(self) -> str:
        """Get a formatted string of all tool descriptions for LLM prompting."""
        descriptions = []
        
        for tool_name, tool in self.tools.items():
            tool_desc = f"Tool: {tool_name}\nDescription: {tool.description}\nArguments:"
            
            for arg in tool.arguments:
                arg_desc = f"  - {arg.name}: "
                if arg.description:
                    arg_desc += f" - {arg.description}"
                if not arg.required:
                    arg_desc += f" (Optional, default: {arg.default})"
                tool_desc += f"\n{arg_desc}"
            
            descriptions.append(tool_desc)
        
        return "\n\n".join(descriptions)
    
    def update_domain_from_data(self, data_context: Dict[str, Any]) -> None:
        """
        Update data-dependent domains based on the provided context.
        
        Args:
            data_context: Dictionary of context data (e.g., {"number_of_pages": 10})
        """
        for tool in self.tools.values():
            for arg in tool.arguments:
                if arg.domain.data_dependent:
                    if arg.name == "page_num" and "number_of_pages" in data_context:
                        arg.domain.values = (1, data_context["number_of_pages"])
                    elif arg.name in ["start", "end"] and "number_of_pages" in data_context:
                        arg.domain.values = (1, data_context["number_of_pages"])
                    # Add more data-dependent domain updates as needed