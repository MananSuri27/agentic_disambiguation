import os
import importlib
import yaml
import logging
from typing import Dict, List, Any, Optional
import sys

# Need to ensure the plugins directory is in the Python path
plugins_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugins')
if plugins_dir not in sys.path:
    sys.path.append(plugins_dir)

from plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

class PluginManager:
    """Manager for API plugins.
    
    This class handles loading, discovery, and management of API plugins.
    It serves as the central access point for all plugin-related operations.
    """
    
    def __init__(self, plugin_config_dir: str = "config/plugins"):
        """
        Initialize the plugin manager.
        
        Args:
            plugin_config_dir: Directory containing plugin configurations
        """
        self.plugin_config_dir = plugin_config_dir
        self.plugins: Dict[str, BasePlugin] = {}
        self.tool_to_plugin_map: Dict[str, str] = {}
        
        # Create the config directory if it doesn't exist
        os.makedirs(plugin_config_dir, exist_ok=True)
    
    def register_plugin(self, plugin: BasePlugin) -> bool:
        """
        Register a plugin directly (without loading from config).
        
        Args:
            plugin: Plugin instance to register
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Register the plugin by name
            self.plugins[plugin.name] = plugin
            
            # Update the tool-to-plugin map
            for tool in plugin.get_tools():
                tool_name = tool.get("name")
                if tool_name:
                    self.tool_to_plugin_map[tool_name] = plugin.name
                    
            logger.info(f"Successfully registered plugin: {plugin.name}")
            return True
        except Exception as e:
            logger.exception(f"Error registering plugin: {e}")
            return False
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load a plugin by name from configuration.
        
        Args:
            plugin_name: Name of the plugin to load
            
        Returns:
            True if successful, False otherwise
        """
        # Try to load plugin configuration
        config_path = os.path.join(self.plugin_config_dir, f"{plugin_name}.yaml")
        if not os.path.exists(config_path):
            logger.error(f"Plugin configuration not found: {config_path}")
            return False
            
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            module_path = config.get("module_path")
            class_name = config.get("class_name")
            
            if not module_path or not class_name:
                logger.error(f"Invalid plugin configuration: {config_path}")
                return False
                
            # Import the plugin module
            module = importlib.import_module(module_path)
            
            # Get the plugin class
            plugin_class = getattr(module, class_name)
            
            # Create an instance of the plugin
            plugin = plugin_class()
            
            # Register the plugin
            return self.register_plugin(plugin)
            
        except Exception as e:
            logger.exception(f"Error loading plugin {plugin_name}: {e}")
            return False
    
    def load_all_plugins(self) -> None:
        """Load all plugins from the configuration directory."""
        if not os.path.exists(self.plugin_config_dir):
            logger.warning(f"Plugin configuration directory not found: {self.plugin_config_dir}")
            return
            
        for filename in os.listdir(self.plugin_config_dir):
            if filename.endswith(".yaml"):
                plugin_name = os.path.splitext(filename)[0]
                self.load_plugin(plugin_name)
    
    def get_plugin(self, plugin_name: str) -> Optional[BasePlugin]:
        """
        Get a plugin by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(plugin_name)
    
    def get_plugin_for_tool(self, tool_name: str) -> Optional[BasePlugin]:
        """
        Get the plugin that provides a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Plugin instance or None if no plugin provides this tool
        """
        plugin_name = self.tool_to_plugin_map.get(tool_name)
        if plugin_name:
            return self.plugins.get(plugin_name)
        return None
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all tools from all loaded plugins.
        
        Returns:
            List of all tool definitions from all plugins
        """
        all_tools = []
        for plugin in self.plugins.values():
            all_tools.extend(plugin.get_tools())
        return all_tools
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool through its plugin.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters for the tool
            
        Returns:
            Result of the tool execution
        """
        plugin = self.get_plugin_for_tool(tool_name)
        if not plugin:
            return {
                "success": False,
                "message": f"No plugin found for tool: {tool_name}",
                "error": "PLUGIN_NOT_FOUND"
            }
            
        return plugin.execute_tool(tool_name, parameters)
    
    def get_all_prompt_templates(self) -> Dict[str, Dict[str, str]]:
        """
        Get all prompt templates from all loaded plugins.
        
        Returns:
            Dictionary mapping plugin names to their prompt templates
        """
        all_templates = {}
        for plugin_name, plugin in self.plugins.items():
            all_templates[plugin_name] = plugin.get_prompt_templates()
        return all_templates