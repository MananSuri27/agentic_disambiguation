from copy import deepcopy
from typing import Dict, List, Any, Optional, Union, Tuple
import logging
from plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

DEFAULT_STATE = {
    "ticket_queue": [],
    "ticket_counter": 1,
    "current_user": None,
}

class TicketSystem:
    """
    A class representing the Ticket API for managing support tickets.

    This class provides methods for creating, retrieving, and managing
    support tickets within a ticketing system. It maintains a queue of
    tickets and handles ticket-related operations such as creation,
    status updates, and retrieval.

    Attributes:
        ticket_queue (List[Dict[str, Union[int, str]]]): A list of ticket dictionaries.
        ticket_counter (int): A counter for generating unique ticket IDs.
        current_user (Optional[str]): The currently authenticated user.
    """

    def __init__(self):
        """
        Initialize the TicketSystem instance.
        """
        self.ticket_queue: List[Dict[str, Union[int, str]]] = []
        self.ticket_counter: int = 1
        self.current_user: Optional[str] = None
        self._api_description = "This tool belongs to the ticketing system that is part of a company, which allows users to create, view, and manage support business tickets."

    def _load_scenario(self, scenario: dict) -> None:
        """
        Load a scenario into the ticket queue.

        Args:
            scenario (Dict): A dictionary containing ticket data.
        """
        DEFAULT_STATE_COPY = deepcopy(DEFAULT_STATE)
        self.ticket_queue = scenario.get("ticket_queue", DEFAULT_STATE_COPY["ticket_queue"])
        self.ticket_counter = scenario.get(
            "ticket_counter", DEFAULT_STATE_COPY["ticket_counter"]
        )
        self.current_user = scenario.get("current_user", DEFAULT_STATE_COPY["current_user"])

    def create_ticket(
        self, title: str, description: str = "", priority: int = 1
    ) -> Dict[str, Union[int, str]]:
        """
        Create a ticket in the system and queue it.

        Args:
            title (str): Title of the ticket.
            description (str): Description of the ticket. Defaults to an empty string.
            priority (int): Priority of the ticket, from 1 to 5. Defaults to 1. 5 is the highest priority.

        Returns:
            id (int): Unique identifier of the ticket.
            title (str): Title of the ticket.
            description (str): Description of the ticket.
            status (str): Current status of the ticket.
            priority (int): Priority level of the ticket.
        """
        if not self.current_user:
            return {"error": "User not authenticated. Please log in to create a ticket."}
        if priority < 1 or priority > 5:
            return {"error": "Invalid priority. Priority must be between 1 and 5."}
        ticket = {
            "id": self.ticket_counter,
            "title": title,
            "description": description,
            "status": "Open",
            "priority": priority,
            "created_by": self.current_user,
        }
        self.ticket_queue.append(ticket)
        self.ticket_counter += 1
        return ticket

    def get_ticket(self, ticket_id: int) -> Dict[str, Union[int, str]]:
        """
        Get a specific ticket by its ID.

        Args:
            ticket_id (int): ID of the ticket to retrieve.

        Returns:
            id (int): Unique identifier of the ticket.
            title (str): Title of the ticket.
            description (str): Description of the ticket.
            status (str): Current status of the ticket.
            priority (int): Priority level of the ticket.
            created_by (str): Username of the ticket creator.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}
        return ticket

    def close_ticket(self, ticket_id: int) -> Dict[str, str]:
        """
        Close a ticket.

        Args:
            ticket_id (int): ID of the ticket to be closed.

        Returns:
            status (str): Status of the close operation.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}
        if ticket["status"] == "Closed":
            return {"error": f"Ticket with ID {ticket_id} is already closed."}
        ticket["status"] = "Closed"
        return {"status": f"Ticket {ticket_id} has been closed successfully."}

    def resolve_ticket(self, ticket_id: int, resolution: str) -> Dict[str, str]:
        """
        Resolve a ticket with a resolution.

        Args:
            ticket_id (int): ID of the ticket to be resolved.
            resolution (str): Resolution details for the ticket.

        Returns:
            status (str): Status of the resolve operation.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}
        if ticket["status"] == "Resolved":
            return {"error": f"Ticket with ID {ticket_id} is already resolved."}
        ticket["status"] = "Resolved"
        ticket["resolution"] = resolution
        return {"status": f"Ticket {ticket_id} has been resolved successfully."}

    def edit_ticket(
        self, ticket_id: int, updates: Dict[str, Optional[Union[str, int]]]
    ) -> Dict[str, str]:
        """
        Modify the details of an existing ticket.

        Args:
            ticket_id (int): ID of the ticket to be changed.
            updates (Dict): Dictionary containing the fields to be updated.
                - title (str) : [Optional] New title for the ticket.
                - description (str): [Optional] New description for the ticket.
                - status (str): [Optional] New status for the ticket.
                - priority (int): [Optional] New priority for the ticket.

        Returns:
            status (str): Status of the update operation.
        """
        ticket = self._find_ticket(ticket_id)
        if not ticket:
            return {"error": f"Ticket with ID {ticket_id} not found."}

        valid_fields = {"title", "description", "status", "priority"}
        invalid_fields = set(updates.keys()) - valid_fields
        if invalid_fields:
            return {"error": f"Invalid fields for update: {', '.join(invalid_fields)}"}

        for key, value in updates.items():
            if value is not None:
                ticket[key] = value

        return {"status": f"Ticket {ticket_id} has been updated successfully."}

    def _find_ticket(self, ticket_id: int) -> Optional[Dict[str, Union[int, str]]]:
        """
        Find a ticket by its ID.

        Args:
            ticket_id (int): ID of the ticket to find.

        Returns:
            id (int): Unique identifier of the ticket.
            title (str): Title of the ticket.
            description (str): Description of the ticket.
            status (str): Current status of the ticket.
            priority (int): Priority level of the ticket.
            created_by (str): Username of the ticket creator.
        """
        for ticket in self.ticket_queue:
            if ticket["id"] == ticket_id:
                return ticket
        return None

    def ticket_login(self, username: str, password: str) -> Dict[str, bool]:
        """
        Authenticate a user for ticket system.

        Args:
            username (str): Username of the user.
            password (str): Password of the user.

        Returns:
            success (bool): True if login was successful, False otherwise.
        """
        # In a real system, you would validate the credentials against a database
        if username and password:  # Simplified authentication
            self.current_user = username
            return {"success": True}
        return {"success": False}

    def ticket_get_login_status(self) -> Dict[str, bool]:
        """
        Get the username of the currently authenticated user.

        Returns:
            username (bool): True if a user is logged in, False otherwise.

        """
        return {"username": bool(self.current_user)}

    def logout(self) -> Dict[str, bool]:
        """
        Log out the current user.

        Returns:
            success (bool): True if logout was successful, False otherwise.
        """
        if self.current_user:
            self.current_user = None
            return {"success": True}
        return {"success": False}

    def get_user_tickets(
        self, status: Optional[str] = None
    ) -> List[Dict[str, Union[int, str]]]:
        """
        Get all tickets created by the current user, optionally filtered by status.

        Args:
            status (str): [Optional] Status to filter tickets by. If None, return all tickets.

        Returns:
            id (int): Unique identifier of the ticket.
            title (str): Title of the ticket.
            description (str): Description of the ticket.
            status (str): Current status of the ticket.
            priority (int): Priority level of the ticket.
            created_by (str): Username of the ticket
        """
        if not self.current_user:
            return [{"error": "User not authenticated. Please log in to view tickets."}]

        user_tickets = [
            ticket
            for ticket in self.ticket_queue
            if ticket["created_by"] == self.current_user
        ]

        if status:
            user_tickets = [
                ticket
                for ticket in user_tickets
                if ticket["status"].lower() == status.lower()
            ]

        return user_tickets


class TicketPlugin(BasePlugin):
    """Plugin for ticket-related operations.
    
    This plugin provides tools for creating, retrieving, and managing support tickets
    within a ticketing system.
    """
    
    def __init__(self):
        """Initialize the ticket plugin."""
        self.ticket_system = TicketSystem()
        self._name = "ticket"
        self._description = "Plugin for ticket-related operations"
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
        """Generate tool definitions for the ticket plugin."""
        return [
            {
                "name": "create_ticket",
                "description": "Create a new support ticket in the system",
                "arguments": [
                    {
                        "name": "title",
                        "description": "Title of the ticket",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "description",
                        "description": "Description of the ticket",
                        "domain": {
                            "type": "string",
                            "importance": 0.7
                        },
                        "required": False,
                        "default": ""
                    },
                    {
                        "name": "priority",
                        "description": "Priority of the ticket (1-5, where 5 is highest)",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 5],
                            "importance": 0.8
                        },
                        "required": False,
                        "default": 1
                    }
                ]
            },
            {
                "name": "get_ticket",
                "description": "Get a specific ticket by its ID",
                "arguments": [
                    {
                        "name": "ticket_id",
                        "description": "ID of the ticket to retrieve",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 10000],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "close_ticket",
                "description": "Close a specific ticket",
                "arguments": [
                    {
                        "name": "ticket_id",
                        "description": "ID of the ticket to close",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 10000],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "resolve_ticket",
                "description": "Resolve a ticket with a resolution message",
                "arguments": [
                    {
                        "name": "ticket_id",
                        "description": "ID of the ticket to resolve",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 10000],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "resolution",
                        "description": "Resolution details for the ticket",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "edit_ticket",
                "description": "Modify the details of an existing ticket",
                "arguments": [
                    {
                        "name": "ticket_id",
                        "description": "ID of the ticket to edit",
                        "domain": {
                            "type": "numeric_range",
                            "values": [1, 10000],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "updates",
                        "description": "Dictionary of fields to update (title, description, status, priority)",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "ticket_login",
                "description": "Authenticate a user for the ticket system",
                "arguments": [
                    {
                        "name": "username",
                        "description": "Username of the user",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "password",
                        "description": "Password of the user",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "ticket_get_login_status",
                "description": "Check if a user is currently logged in",
                "arguments": []
            },
            {
                "name": "logout",
                "description": "Log out the current user",
                "arguments": []
            },
            {
                "name": "get_user_tickets",
                "description": "Get all tickets created by the current user, optionally filtered by status",
                "arguments": [
                    {
                        "name": "status",
                        "description": "Status to filter tickets by (e.g., 'Open', 'Closed', 'Resolved')",
                        "domain": {
                            "type": "finite",
                            "values": ["Open", "Closed", "Resolved"],
                            "importance": 0.7
                        },
                        "required": False,
                        "default": None
                    }
                ]
            }
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of tools provided by this plugin."""
        return self._tools
    
    def initialize_from_config(self, config_data: Dict[str, Any]) -> bool:
        """Initialize the ticket system from configuration data."""
        if "TicketAPI" in config_data:
            ticket_config = config_data["TicketAPI"]
            self.ticket_system._load_scenario(ticket_config)
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
            # Handle special case for edit_ticket
            if tool_name == "edit_ticket" and "updates" in parameters:
                # If updates is a string, try to convert it to a dictionary
                updates_param = parameters["updates"]
                if isinstance(updates_param, str):
                    import json
                    try:
                        # Try to parse as JSON
                        updates_dict = json.loads(updates_param)
                        parameters["updates"] = updates_dict
                    except json.JSONDecodeError:
                        # If not valid JSON, try to parse as key-value pairs
                        updates_dict = {}
                        pairs = updates_param.split(',')
                        for pair in pairs:
                            if ':' in pair:
                                key, value = pair.split(':', 1)
                                updates_dict[key.strip()] = value.strip()
                        parameters["updates"] = updates_dict
            
            # Call the corresponding method on the ticket system
            method = getattr(self.ticket_system, tool_name)
            result = method(**parameters)
            
            # Handle different result formats
            if isinstance(result, dict) and "error" in result:
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
                
                # Validate based on domain type
                domain = arg_def.get("domain", {})
                domain_type = domain.get("type", "string")
                
                if domain_type == "numeric_range":
                    try:
                        val = float(value)
                        start, end = domain.get("values", [1, 10000])
                        if not (start <= val <= end):
                            return False, f"Value {value} for {arg_def['name']} is out of range [{start}, {end}]"
                    except (ValueError, TypeError):
                        return False, f"Invalid numeric value for {arg_def['name']}: {value}"
                
                elif domain_type == "finite":
                    if value not in domain.get("values", []):
                        values_str = ", ".join(str(v) for v in domain.get("values", []))
                        return False, f"Invalid value for {arg_def['name']}: {value}. Expected one of: {values_str}"
        
        return True, None
    
    def get_domain_updates_from_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update tool domains based on context."""
        updates = {}
        
        # Initialize from config if available
        if "initial_config" in context and hasattr(self, "initialize_from_config"):
            self.initialize_from_config(context["initial_config"])
        
        # Get current ticket IDs
        ticket_ids = [ticket["id"] for ticket in self.ticket_system.ticket_queue]
        
        if ticket_ids:
            min_id = min(ticket_ids) if ticket_ids else 1
            max_id = max(ticket_ids) if ticket_ids else 10000
            
            # Update ticket_id domains for all relevant tools
            for tool_name in ["get_ticket", "close_ticket", "resolve_ticket", "edit_ticket"]:
                updates[f"{tool_name}.ticket_id"] = {
                    "type": "numeric_range",
                    "values": [min_id, max_id]
                }
        
        return updates
    
    def get_uncertainty_context(self) -> Dict[str, Any]:
        """Get ticket-specific context for uncertainty calculation."""
        return {
            "user_logged_in": self.ticket_system.current_user is not None,
            "available_tickets": [ticket["id"] for ticket in self.ticket_system.ticket_queue]
        }
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """Get ticket-specific prompt templates."""
        return {
            "tool_selection": """
You are an AI assistant that helps users with ticket operations.

Conversation history:
{conversation_history}

User query: "{user_query}"

Available tools:
{tool_descriptions}

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What is the user trying to do with the ticket system?
2. Which ticket operation(s) are needed to complete this task?
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
You are an AI assistant that helps users with ticket operations.

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