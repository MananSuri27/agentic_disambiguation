from typing import Dict, List, Any, Optional, Tuple, Union
import logging
import copy
from plugins.base_plugin import BasePlugin
from copy import deepcopy

logger = logging.getLogger(__name__)

# Default state for MessageAPI
DEFAULT_STATE = {
    "generated_ids": set(),
    "user_count": 4,
    "user_map": {
        "Alice": "USR001",
        "Bob": "USR002",
        "Catherine": "USR003",
        "Daniel": "USR004",
    },
    "inbox": [
        {
            "USR002": "My name is Alice. I want to connect.",
        },
        {
            "USR003": "Could you upload the file?",
        },
        {
            "USR004": "Could you upload the file?",
        },
    ],
    "message_count": 3,
    "current_user": None,
}


class MessageAPI:
    """
    A class representing a Message API for managing user interactions in a workspace.

    This class provides methods for user management, messaging, and message retrieval
    within a specific workspace. It maintains user information, sent messages, and
    received messages for each user.
    """

    def __init__(self):
        """
        Initialize the MessageAPI with a workspace ID.
        """
        self.generated_ids = DEFAULT_STATE["generated_ids"].copy()
        self.user_count = DEFAULT_STATE["user_count"]
        self.user_map = DEFAULT_STATE["user_map"].copy()
        self.inbox = deepcopy(DEFAULT_STATE["inbox"])
        self.message_count = DEFAULT_STATE["message_count"]
        self.current_user = DEFAULT_STATE["current_user"]
        self._api_description = "This tool belongs to the Message API, which is used to manage user interactions in a workspace."
        self._random = __import__('random').Random(200191)

    def _load_scenario(self, scenario: dict) -> None:
        """
        Load a scenario into the MessageAPI.

        Args:
            scenario (Dict): A dictionary containing message data.
        """
        DEFAULT_STATE_COPY = deepcopy(DEFAULT_STATE)
        self._random = __import__('random').Random(scenario.get("random_seed", 200191))
        self.generated_ids = set(scenario.get(
            "generated_ids", DEFAULT_STATE_COPY["generated_ids"]
        ))
        self.user_count = scenario.get("user_count", DEFAULT_STATE_COPY["user_count"])
        self.user_map = scenario.get("user_map", DEFAULT_STATE_COPY["user_map"])
        self.inbox = scenario.get("inbox", DEFAULT_STATE_COPY["inbox"])
        self.message_count = scenario.get(
            "message_count", DEFAULT_STATE_COPY["message_count"]
        )
        self.current_user = scenario.get("current_user", DEFAULT_STATE_COPY["current_user"])

    def _generate_id(self):
        """
        Generate a unique ID for a message.

        Returns:
            new_id (int): A unique ID for a message.
        """
        new_id = self._random.randint(
            10000, 99999
        )  # first 5 mapped by initial configuration.
        while new_id in self.generated_ids:
            new_id = self._random.randint(10000, 99999)
        self.generated_ids.add(new_id)
        return {"new_id": new_id}

    def list_users(self) -> Dict[str, List[str]]:
        """
        List all users in the workspace.

        Returns:
          user_list (List[str]): List of all users in the workspace.
        """
        return {"user_list": list(self.user_map.keys())}

    def get_user_id(self, user: str) -> Dict[str, Optional[str]]:
        """
        Get user ID from user name.

        Args:
            user (str): User name of the user.

        Returns:
            user_id (str): User ID of the user
        """
        if user not in self.user_map:
            return {"error": f"User '{user}' not found in the workspace."}
        return {"user_id": self.user_map.get(user)}

    def message_login(self, user_id: str) -> Dict[str, Union[str, bool]]:
        """
        Log in a user with the given user ID to messeage application.

        Args:
            user_id (str): User ID of the user to log in.

        Returns:
            login_status (bool): True if login was successful, False otherwise.
            message (str): A message describing the result of the login attempt.
        """
        if user_id not in [id for id in self.user_map.values()]:
            return {"login_status": False, "message": f"User ID '{user_id}' not found."}
        self.current_user = user_id
        return {
            "login_status": True,
            "message": f"User '{user_id}' logged in successfully.",
        }

    def message_get_login_status(self) -> Dict[str, bool]:
        """
        Get the login status of the current user.

        Returns:
            login_status (bool): True if the current user is logged in, False otherwise.
        """
        return {"login_status": bool(self.current_user)}

    def send_message(self, receiver_id: str, message: str) -> Dict[str, Union[str, bool]]:
        """
        Send a message to a user.
        Args:
            receiver_id (str): User ID of the user to send the message to.
            message (str): Message to be sent.
        Returns:
            sent_status (bool): True if the message was sent successfully, False otherwise.
            message_id (int): ID of the sent message.
            message (str): A message describing the result of the send attempt.
        """
        # Check if there is a current user logged in
        if not self.current_user:
            return {"error": "No user is currently logged in."}
        # Validate receiver existence
        if receiver_id not in self.user_map.values():
            return {"error": f"Receiver ID '{receiver_id}' not found."}
        # Generate a unique message ID
        message_id = self._generate_id()
        # Store the message in the inbox
        self.inbox.append({receiver_id: message})
        self.message_count += 1
        return {
            "sent_status": True,
            "message_id": message_id,
            "message": f"Message sent to '{receiver_id}' successfully.",
        }

    def delete_message(self, receiver_id: str) -> Dict[str, Union[bool, str]]:
        """
        Delete the latest message sent to a receiver.
        Args:
            receiver_id (str): User ID of the user to send the message to.
        Returns:
            deleted_status (bool): True if the message was deleted successfully, False otherwise.
            message_id (int): ID of the deleted message.
            message (str): A message describing the result of the deletion attempt.
        """
        if not self.current_user:
            return {"error": "No user is currently logged in."}

        # Loop through the inbox in reverse order to find the first message sent to the receiver
        for message in self.inbox[::-1]:
            receiver, _ = list(message.items())[0]
            if receiver == receiver_id:
                self.inbox.remove(message)
                return {
                    "deleted_status": True,
                    "message_id": receiver,
                    "message": f"Receiver {receiver_id}'s first message deleted successfully.",
                }
        return {"error": f"Receiver ID {receiver_id} not found."}

    def view_messages_sent(self) -> Dict[str, Union[Dict[str, List[str]], str]]:
        """
        View all historical messages sent by the current user.

        Returns:
            messages (Dict): Dictionary of messages grouped by receiver An example of the messages dictionary is {"USR001":["Hello"],"USR002":["World"]}.
        """
        if not self.current_user:
            return {"error": "No user is currently logged in."}
        # Dictionary to collect messages grouped by receiver
        sent_messages = {}
        # Loop through the inbox and collect messages sent by the current user
        for message in self.inbox:
            receiver, message_content = list(message.items())[0]
            if receiver not in sent_messages:
                sent_messages[receiver] = [message_content]
            else:
                sent_messages[receiver].append(message_content)
        return {"messages": sent_messages}

    def add_contact(self, user_name: str) -> Dict[str, Union[bool, str]]:
        """
        Add a contact to the workspace.
        Args:
            user_name (str): User name of contact to be added.
        Returns:
            added_status (bool): True if the contact was added successfully, False otherwise.
            user_id (str): User ID of the added contact.
            message (str): A message describing the result of the addition attempt.
        """
        if user_name in self.user_map:
            return {"error": f"User name '{user_name}' already exists."}
        self.user_count += 1
        user_id = f"USR{str(self.user_count).zfill(3)}"
        if user_id in self.user_map.values():
            return {"error": f"User ID '{user_id}' already exists."}
        self.user_map[user_name] = user_id
        return {
            "added_status": True,
            "user_id": user_id,
            "message": f"Contact '{user_name}' added successfully.",
        }

    def search_messages(
        self, keyword: str
    ) -> Dict[str, Union[List[Dict[str, Union[str, List[str]]]], str]]:
        """
        Search for messages containing a specific keyword.
        Args:
            keyword (str): The keyword to search for in messages.
        Returns:
            results (List[Dict]): List of dictionaries containing matching messages.
                - receiver_id (str): User ID of the receiver of the message.
                - message (str): The message containing the keyword.
        """
        if not self.current_user:
            return {"error": "No user is currently logged in."}
        keyword_lower = keyword.lower()
        results = []
        # Iterate through the inbox to search for the keyword in messages
        for message_data in self.inbox:
            receiver_id, message_content = list(message_data.items())[0]
            if keyword_lower in message_content.lower():
                results.append(
                    {
                        "receiver_id": receiver_id,
                        "message": message_content,
                    }
                )
        return {"results": results}

    def get_message_stats(self) -> Dict[str, Union[Dict[str, int], str]]:
        """
        Get statistics about messages for the current user.
        Returns:
            stats (Dict): Dictionary containing message statistics.
                - received_count (int): Number of messages received by the current user.
                - total_contacts (int): Total number of contacts the user has interacted with.
        """
        if not self.current_user:
            return {"error": "No user is currently logged in."}
        sent_count = 0
        received_count = 0
        contacts = set()
        # Loop through the inbox to calculate stats
        for message_data in self.inbox:
            receiver_id, message_content = list(message_data.items())[0]
            received_count += 1
            contacts.add(receiver_id)
        total_contacts = len(contacts)
        return {
            "stats": {
                "received_count": received_count,
                "total_contacts": total_contacts,
            }
        }


class MessagePlugin(BasePlugin):
    """Plugin for the Message API.
    
    This plugin provides tools for interacting with a messaging system, allowing
    users to perform actions like logging in, sending messages, and managing contacts.
    """
    
    def __init__(self):
        """Initialize the Message API plugin."""
        self.message_api = MessageAPI()
        self._name = "message"
        self._description = "Plugin for message API operations"
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
        """Generate tool definitions for the Message plugin."""
        return [
            {
                "name": "list_users",
                "description": "List all users in the workspace",
                "arguments": []
            },
            {
                "name": "get_user_id",
                "description": "Get the user ID for a given username",
                "arguments": [
                    {
                        "name": "user",
                        "description": "Username to look up",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "message_login",
                "description": "Log in a user with the given user ID",
                "arguments": [
                    {
                        "name": "user_id",
                        "description": "User ID of the user to log in",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "message_get_login_status",
                "description": "Get the login status of the current user",
                "arguments": []
            },
            {
                "name": "send_message",
                "description": "Send a message to another user",
                "arguments": [
                    {
                        "name": "receiver_id",
                        "description": "User ID of the message recipient",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "message",
                        "description": "Message content to send",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "delete_message",
                "description": "Delete the latest message sent to a receiver",
                "arguments": [
                    {
                        "name": "receiver_id",
                        "description": "User ID of the receiver whose message to delete",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "view_messages_sent",
                "description": "View all historical messages sent by the current user",
                "arguments": []
            },
            {
                "name": "add_contact",
                "description": "Add a new contact to the workspace",
                "arguments": [
                    {
                        "name": "user_name",
                        "description": "User name of contact to be added",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "search_messages",
                "description": "Search for messages containing a specific keyword",
                "arguments": [
                    {
                        "name": "keyword",
                        "description": "Keyword to search for in messages",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_message_stats",
                "description": "Get statistics about messages for the current user",
                "arguments": []
            }
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of tools provided by this plugin."""
        return self._tools
    
    def initialize_from_config(self, config_data: Dict[str, Any]) -> bool:
        """Initialize the message API from configuration data."""
        if "MessageAPI" in config_data:
            message_config = config_data["MessageAPI"]
            self.message_api._load_scenario(message_config)
            return True
        return False
    
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
            # Call the corresponding method on the message API
            message_method = getattr(self.message_api, tool_name)
            result = message_method(**parameters)
            
            # Handle different result formats
            if result is None:
                return {
                    "success": True,
                    "message": f"Successfully executed {tool_name}"
                }
            elif isinstance(result, dict) and "error" in result:
                return {
                    "success": False,
                    "message": result["error"],
                    "error": "OPERATION_FAILED"
                }
            else:
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
                
                # Skip validation for unknown values
                if value == "<UNK>":
                    continue
                    
                # Validate based on domain type
                domain = arg_def.get("domain", {})
                domain_type = domain.get("type", "string")
                
                if domain_type == "numeric_range":
                    try:
                        val = float(value)
                        start, end = domain.get("values", [float('-inf'), float('inf')])
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
        
        return True, None
    
    def get_domain_updates_from_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update tool domains based on context."""
        updates = {}
        
        # Initialize from config if available
        if "initial_config" in context and "MessageAPI" in context["initial_config"]:
            self.initialize_from_config(context["initial_config"])
        
        # Get current users for user domain
        users = list(self.message_api.user_map.keys())
        user_ids = list(self.message_api.user_map.values())
        
        # Update get_user_id domain
        updates["get_user_id.user"] = {
            "type": "finite",
            "values": users
        }
        
        # Update message_login domain
        updates["message_login.user_id"] = {
            "type": "finite",
            "values": user_ids
        }
        
        # Update send_message and delete_message domains
        updates["send_message.receiver_id"] = {
            "type": "finite",
            "values": user_ids
        }
        
        updates["delete_message.receiver_id"] = {
            "type": "finite",
            "values": user_ids
        }
        
        return updates
    
    def get_uncertainty_context(self) -> Dict[str, Any]:
        """Get message-specific context for uncertainty calculation."""
        try:
            return {
                "current_user": self.message_api.current_user,
                "is_logged_in": bool(self.message_api.current_user),
                "available_users": list(self.message_api.user_map.keys()),
                "available_user_ids": list(self.message_api.user_map.values())
            }
        except Exception as e:
            logger.error(f"Error getting uncertainty context: {e}")
            return {}
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """Get message-specific prompt templates."""
        return {
            "tool_selection": """
You are an AI assistant that helps users with message API operations.

Conversation history:
{conversation_history}

User query: "{user_query}"

Available tools:
{tool_descriptions}

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What is the user trying to do with the messaging system?
2. Which messaging operation(s) are needed to complete this task?
3. What parameters are needed for each operation?
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
You are an AI assistant that helps users with message API operations.

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