#!/usr/bin/env python
"""
Test script for the Twitter plugin integration.
"""

import sys
import os
import logging
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plugin_manager import PluginManager
from core.tool_registry import ToolRegistry
from plugins.twitter_plugin import TwitterPlugin

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_twitter_plugin_initialization():
    """Test initializing the Twitter plugin."""
    plugin = TwitterPlugin()
    
    logger.info(f"Plugin name: {plugin.name}")
    logger.info(f"Plugin description: {plugin.description}")
    
    tools = plugin.get_tools()
    logger.info(f"Number of tools: {len(tools)}")
    
    # Print tool names
    tool_names = [tool["name"] for tool in tools]
    logger.info(f"Tool names: {tool_names}")
    
    return plugin

def test_twitter_plugin_with_scenario():
    """Test the Twitter plugin with a specific scenario."""
    plugin = TwitterPlugin()
    
    # Create a test scenario
    test_scenario = {
        "username": "testuser",
        "password": "testpass",
        "authenticated": False,
        "tweets": {
            "0": {
                "id": 0,
                "username": "alice",
                "content": "Hello Twitter!",
                "tags": ["#hello", "#twitter"],
                "mentions": []
            },
            "1": {
                "id": 1,
                "username": "bob",
                "content": "Testing the Twitter API",
                "tags": ["#testing", "#api"],
                "mentions": ["@alice"]
            }
        },
        "comments": {
            "0": [
                {"username": "bob", "content": "Nice first tweet!"}
            ]
        },
        "retweets": {
            "bob": [0]
        },
        "following_list": ["alice", "bob", "charlie"],
        "tweet_counter": 2
    }
    
    # Initialize the plugin with the test scenario
    plugin.twitter_api._load_scenario(test_scenario)
    
    # Test authentication
    auth_result = plugin.execute_tool("authenticate_twitter", {
        "username": "testuser",
        "password": "testpass"
    })
    logger.info(f"Authentication result: {auth_result}")
    
    # Test getting login status
    status_result = plugin.execute_tool("posting_get_login_status", {})
    logger.info(f"Login status: {status_result}")
    
    # Test posting a tweet
    tweet_result = plugin.execute_tool("post_tweet", {
        "content": "Testing the Twitter plugin integration",
        "tags": ["#testing", "#integration"],
        "mentions": ["@developer"]
    })
    logger.info(f"Post tweet result: {tweet_result}")
    
    # Test getting a tweet
    get_tweet_result = plugin.execute_tool("get_tweet", {"tweet_id": 0})
    logger.info(f"Get tweet result: {get_tweet_result}")
    
    # Test searching tweets
    search_result = plugin.execute_tool("search_tweets", {"keyword": "testing"})
    logger.info(f"Search tweets result: {search_result}")
    
    # Test getting domain updates
    domain_updates = plugin.get_domain_updates_from_context({"initial_config": {"TwitterAPI": test_scenario}})
    logger.info(f"Domain updates: {domain_updates}")
    
    return plugin

def test_plugin_manager_integration():
    """Test integrating the Twitter plugin with the plugin manager."""
    # Initialize plugin manager
    plugin_manager = PluginManager()
    
    # Register the Twitter plugin
    plugin = TwitterPlugin()
    success = plugin_manager.register_plugin(plugin)
    logger.info(f"Plugin registration success: {success}")
    
    # Initialize tool registry
    tool_registry = ToolRegistry(plugin_manager)
    
    # Get tool descriptions
    descriptions = tool_registry.get_tool_descriptions()
    logger.info(f"Tool descriptions sample: {descriptions[:200]}...")  # Show just the beginning
    
    # Test getting a specific tool
    tool = tool_registry.get_tool("post_tweet")
    if tool:
        logger.info(f"post_tweet tool arguments: {[arg.name for arg in tool.arguments]}")
    else:
        logger.error("post_tweet tool not found")
    
    return plugin_manager, tool_registry

def main():
    """Main test function."""
    logger.info("Testing Twitter plugin initialization...")
    plugin = test_twitter_plugin_initialization()
    
    logger.info("\nTesting Twitter plugin with scenario...")
    plugin_with_scenario = test_twitter_plugin_with_scenario()
    
    logger.info("\nTesting plugin manager integration...")
    plugin_manager, tool_registry = test_plugin_manager_integration()
    
    logger.info("\nAll tests completed.")

if __name__ == "__main__":
    main()