from typing import Dict, List, Any, Union, Optional
import abc
import json


class LLMProvider(abc.ABC):
    """Abstract base class for LLM providers."""
    
    @abc.abstractmethod
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """
        Generate text from the LLM.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        pass
    
    @abc.abstractmethod
    def generate_json(
        self,
        prompt: str,
        response_model: Dict[str, Any],
        max_tokens: int = 1000,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Generate structured JSON from the LLM.
        
        Args:
            prompt: Input prompt
            response_model: Expected structure of the response
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated JSON as a dictionary
        """
        pass
        
    def generate_tool_calls(
        self,
        user_query: str,
        tool_descriptions: str,
        conversation_history: List[Dict[str, Any]] = None,
        max_tokens: int = 2000
    ) -> List[Dict[str, Any]]:
        """
        Generate tool calls from a user query.
        
        Args:
            user_query: User's query
            tool_descriptions: Descriptions of available tools
            conversation_history: Optional conversation history
            max_tokens: Maximum tokens to generate
            
        Returns:
            List of tool call dictionaries
        """
        # Format conversation history if provided
        formatted_history = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "unknown")
                message = turn.get("message", "")
                history_lines.append(f"{role.capitalize()}: {message}")
            formatted_history = "\n".join(history_lines)
            formatted_history = f"Conversation history:\n{formatted_history}\n\n"
            
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing the appropriate tool calls.

{formatted_history}Available tools:
{tool_descriptions}

User query: "{user_query}"

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What is the user trying to accomplish?
2. Which tool(s) are needed to complete this task?
3. What parameters are needed for each tool?
4. Which parameters can be determined from the query, and which are uncertain?

Return your response as a JSON object with the following structure:
{{
  "reasoning": "Your step-by-step reasoning about what tools to use and why",
  "tool_calls": [
    {{
      "tool_name": "name_of_tool",
      "arguments": {{
        "arg1": "value1",
        "arg2": "<UNK>"
      }}
    }}
  ]
}}
"""
        
        response = self.generate_json(
            prompt=prompt,
            response_model={
                "reasoning": "string",
                "tool_calls": [
                    {
                        "tool_name": "string",
                        "arguments": {}
                    }
                ]
            },
            max_tokens=max_tokens,
            temperature=0.2
        )
        
        return response.get("tool_calls", [])
        
    def generate_reasoning(
        self,
        user_query: str,
        conversation_history: List[Dict[str, Any]],
        tool_descriptions: str,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Generate reasoning about what tools might be needed for a user query.
        
        Args:
            user_query: Current user query
            conversation_history: Prior conversation context
            tool_descriptions: Descriptions of available tools
            max_tokens: Maximum tokens to generate
            
        Returns:
            Dictionary with reasoning and potential tool calls
        """
        # Format conversation history
        formatted_history = ""
        if conversation_history:
            history_lines = []
            for turn in conversation_history:
                role = turn.get("role", "unknown")
                message = turn.get("message", "")
                history_lines.append(f"{role.capitalize()}: {message}")
            formatted_history = "\n".join(history_lines)
            
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing the appropriate tool calls.

Conversation history:
{formatted_history}

Current user query: "{user_query}"

Available tools:
{tool_descriptions}

Please reason step-by-step about what the user is asking for:
1. What is the user trying to accomplish?
2. What information do we already have from the conversation history?
3. What tools would help accomplish this task?
4. What parameters are needed for each tool?
5. Do we have enough information to execute these tools, or do we need to ask clarifying questions?

Think carefully about each step before proceeding to the next one.

After your reasoning, select the appropriate tool(s) to call.

Tool calls should be formatted as:
{{
  "tool_name": "name_of_tool",
  "arguments": {{
    "arg1": "value1",
    "arg2": "<UNK>" if uncertain
  }}
}}

Return your response as a JSON object with the following structure:
{{
  "reasoning": "Your step-by-step reasoning about what tools to use and why",
  "tool_calls": [
    {{
      "tool_name": "name_of_tool",
      "arguments": {{
        "arg1": "value1",
        "arg2": "<UNK>"
      }}
    }}
  ]
}}
"""
        
        response = self.generate_json(
            prompt=prompt,
            response_model={
                "reasoning": "string",
                "tool_calls": [
                    {
                        "tool_name": "string",
                        "arguments": {}
                    }
                ]
            },
            max_tokens=max_tokens,
            temperature=0.2
        )
        
        return response
    
#     def generate_tool_calls(
#         self,
#         user_query: str,
#         tool_descriptions: str,
#         max_tokens: int = 2000
#     ) -> List[Dict[str, Any]]:
#         """
#         Generate tool calls from a user query.
        
#         Args:
#             user_query: User's query
#             tool_descriptions: Descriptions of available tools
#             max_tokens: Maximum tokens to generate
            
#         Returns:
#             List of tool call dictionaries
#         """
#         prompt = f"""
# You are an AI assistant that helps users by understanding their queries and executing the appropriate tool calls.

# Available tools:
# {tool_descriptions}

# User query: "{user_query}"

# Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
# For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

# Think through this step by step:
# 1. What is the user trying to accomplish?
# 2. Which tool(s) are needed to complete this task?
# 3. What parameters are needed for each tool?
# 4. Which parameters can be determined from the query, and which are uncertain?

# Return your response as a JSON object with the following structure:
# {{
#   "reasoning": "Your step-by-step reasoning about what tools to use and why",
#   "tool_calls": [
#     {{
#       "tool_name": "name_of_tool",
#       "arguments": {{
#         "arg1": "value1",
#         "arg2": "<UNK>"
#       }}
#     }}
#   ]
# }}
# """
        
#         response = self.generate_json(
#             prompt=prompt,
#             response_model={
#                 "reasoning": "string",
#                 "tool_calls": [
#                     {
#                         "tool_name": "string",
#                         "arguments": {}
#                     }
#                 ]
#             },
#             max_tokens=max_tokens,
#             temperature=0.2
#         )
        
#         return response.get("tool_calls", [])
    
    def update_tool_calls_from_error(
        self,
        user_query: str,
        tool_calls: List[Dict[str, Any]],
        error: Dict[str, Any],
        tool_descriptions: str,
        max_tokens: int = 2000
    ) -> List[Dict[str, Any]]:
        """
        Update tool calls based on an error.
        
        Args:
            user_query: Original user query
            tool_calls: Current tool calls
            error: Error information
            tool_descriptions: Descriptions of available tools
            max_tokens: Maximum tokens to generate
            
        Returns:
            Updated list of tool call dictionaries
        """
        prompt = f"""
You are an AI assistant that helps users by understanding their queries and executing the appropriate tool calls.

Available tools:
{tool_descriptions}

User query: "{user_query}"

Current tool calls:
{json.dumps(tool_calls, indent=2)}

Error:
{json.dumps(error, indent=2)}

Please update the tool calls to fix the error. Consider what went wrong and how to correct it.

Return your response as a JSON object with the following structure:
{{
  "reasoning": "Your reasoning about what went wrong and how to fix it",
  "updated_tool_calls": [
    {{
      "tool_name": "name_of_tool",
      "arguments": {{
        "arg1": "value1",
        "arg2": "value2"
      }}
    }}
  ]
}}
"""
        
        response = self.generate_json(
            prompt=prompt,
            response_model={
                "reasoning": "string",
                "updated_tool_calls": [
                    {
                        "tool_name": "string",
                        "arguments": {}
                    }
                ]
            },
            max_tokens=max_tokens,
            temperature=0.2
        )
        
        return response.get("updated_tool_calls", tool_calls)