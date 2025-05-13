from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple

class BasePlugin(ABC):
    """Abstract base class for API plugins.
    
    This interface defines the contract that all API plugins must fulfill to work
    with the disambiguation system. It provides methods for tool discovery, execution,
    validation, and API-specific behaviors like domain updates and uncertainty context.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of the plugin."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the description of the plugin."""
        pass
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools provided by this plugin.
        
        Returns:
            List of tool definitions in dictionary format.
        """
        pass
    
    @abstractmethod
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            
        Returns:
            Result of the tool execution with at least the following keys:
            - success: Whether execution was successful
            - message: User-friendly message about the result
            - output: (optional) Output data from the tool
            - error: (optional) Error details if execution failed
        """
        pass
    
    @abstractmethod
    def validate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a tool call before execution.
        
        Args:
            tool_name: Name of the tool to validate
            parameters: Parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message), where error_message is None if valid
        """
        pass
    
    def get_domain_updates_from_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get updates to tool domains based on context.
        For example, page numbers might depend on the number of pages in a document.
        
        Args:
            context: Context data that may affect domain definitions
            
        Returns:
            Dictionary mapping "tool_name.arg_name" to updated domain information
        """
        return {}
    
    def get_uncertainty_context(self) -> Dict[str, Any]:
        """
        Get API-specific context for uncertainty calculation.
        This allows each API to provide custom data for uncertainty calculations.
        
        Returns:
            Dictionary of context data for uncertainty calculations
        """
        return {}
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """
        Get API-specific prompt templates.
        
        Returns:
            Dictionary mapping template names to template strings
        """
        return {}