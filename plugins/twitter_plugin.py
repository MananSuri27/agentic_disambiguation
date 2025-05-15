from typing import Dict, List, Any, Optional, Tuple, Union
import logging
import copy
from plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

# Define default state for TwitterAPI
DEFAULT_STATE = {
    "username": "john",
    "password": "john123",
    "authenticated": False,
    "tweets": {},
    "comments": {},
    "retweets": {},
    "following_list": ["alice", "bob"],
    "tweet_counter": 0,
}

class TwitterAPI:
    """Twitter API implementation."""
    
    def __init__(self):
        """Initialize a Twitter API instance."""
        self.username: str
        self.password: str
        self.authenticated: bool
        self.tweets: Dict[int, Dict[str, Union[int, str, List[str]]]]
        self.comments: Dict[int, List[Dict[str, str]]]
        self.retweets: Dict[str, List[int]]
        self.following_list: List[str]
        # tweet_counter is used to assign unique IDs to tweets
        self.tweet_counter: int
        self._api_description = "This tool belongs to the TwitterAPI, which provides core functionality for posting tweets, retweeting, commenting, and following users on Twitter."
        
        # Initialize with default state
        self._load_default_state()

    def _load_default_state(self):
        """Load the default state."""
        default_copy = copy.deepcopy(DEFAULT_STATE)
        self.username = default_copy["username"]
        self.password = default_copy["password"]
        self.authenticated = default_copy["authenticated"]
        self.tweets = default_copy["tweets"]
        self.comments = default_copy["comments"]
        self.retweets = default_copy["retweets"]
        self.following_list = default_copy["following_list"]
        self.tweet_counter = default_copy["tweet_counter"]

    def _load_scenario(self, scenario: dict) -> None:
        """
        Load a scenario into the TwitterAPI instance.
        Args:
            scenario (dict): A dictionary containing Twitter data.
        """
        DEFAULT_STATE_COPY = copy.deepcopy(DEFAULT_STATE)
        self.username = scenario.get("username", DEFAULT_STATE_COPY["username"])
        self.password = scenario.get("password", DEFAULT_STATE_COPY["password"])
        self.authenticated = scenario.get(
            "authenticated", DEFAULT_STATE_COPY["authenticated"]
        )
        self.tweets = scenario.get("tweets", DEFAULT_STATE_COPY["tweets"])
        self.tweets = {int(k): v for k, v in self.tweets.items()} # Convert tweet keys from string to int from loaded scenario
        self.comments = scenario.get("comments", DEFAULT_STATE_COPY["comments"])
        self.retweets = scenario.get("retweets", DEFAULT_STATE_COPY["retweets"])
        self.following_list = scenario.get(
            "following_list", DEFAULT_STATE_COPY["following_list"]
        )
        self.tweet_counter = scenario.get(
            "tweet_counter", DEFAULT_STATE_COPY["tweet_counter"]
        )

    def authenticate_twitter(self, username: str, password: str) -> Dict[str, bool]:
        """
        Authenticate a user with username and password.

        Args:
            username (str): Username of the user.
            password (str): Password of the user.
        Returns:
            authentication_status (bool): True if authenticated, False otherwise.
        """
        if username == self.username and password == self.password:
            self.authenticated = True
            return {"authentication_status": True}
        return {"authentication_status": False}

    def posting_get_login_status(self) -> Dict[str, Union[bool, str]]:
        """
        Get the login status of the current user.

        Returns:
            login_status (bool): True if the current user is logged in, False otherwise.
        """
        return {"login_status": bool(self.authenticated)}

    def post_tweet(
        self, content: str, tags: List[str] = [], mentions: List[str] = []
    ) -> Dict[str, Union[int, str, List[str]]]:
        """
        Post a tweet for the authenticated user.

        Args:
            content (str): Content of the tweet.
            tags (List[str]): [Optional] List of tags for the tweet. Tag name should start with #. This is only relevant if the user wants to add tags to the tweet.
            mentions (List[str]): [Optional] List of users mentioned in the tweet. Mention name should start with @. This is only relevant if the user wants to add mentions to the tweet.
        Returns:
            id (int): ID of the posted tweet.
            username (str): Username of the poster.
            content (str): Content of the tweet.
            tags (List[str]): List of tags associated with the tweet.
            mentions (List[str]): List of users mentioned in the tweet.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before posting."}

        tweet = {
            "id": self.tweet_counter,
            "username": self.username,
            "content": content,
            "tags": tags,
            "mentions": mentions,
        }
        self.tweets[self.tweet_counter] = tweet
        self.tweet_counter += 1
        return tweet

    def retweet(self, tweet_id: int) -> Dict[str, str]:
        """
        Retweet a tweet for the authenticated user.

        Args:
            tweet_id (int): ID of the tweet to retweet.
        Returns:
            retweet_status (str): Status of the retweet action.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before retweeting."}
                
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        if self.username not in self.retweets:
            self.retweets[self.username] = []

        if tweet_id in self.retweets[self.username]:
            return {"retweet_status": "Already retweeted"}

        self.retweets[self.username].append(tweet_id)
        return {"retweet_status": "Successfully retweeted"}

    def comment(self, tweet_id: int, comment_content: str) -> Dict[str, str]:
        """
        Comment on a tweet for the authenticated user.

        Args:
            tweet_id (int): ID of the tweet to comment on.
            comment_content (str): Content of the comment.
        Returns:
            comment_status (str): Status of the comment action.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before commenting."}

        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        if tweet_id not in self.comments:
            self.comments[tweet_id] = []

        self.comments[tweet_id].append(
            {"username": self.username, "content": comment_content}
        )
        return {"comment_status": "Comment added successfully"}

    def mention(self, tweet_id: int, mentioned_usernames: List[str]) -> Dict[str, str]:
        """
        Mention specified users in a tweet.

        Args:
            tweet_id (int): ID of the tweet where users are mentioned.
            mentioned_usernames (List[str]): List of usernames to be mentioned.
        Returns:
            mention_status (str): Status of the mention action.
        """
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        tweet = self.tweets[tweet_id]
        tweet["mentions"].extend(mentioned_usernames)

        return {"mention_status": "Users mentioned successfully"}

    def follow_user(self, username_to_follow: str) -> Dict[str, bool]:
        """
        Follow a user for the authenticated user.

        Args:
            username_to_follow (str): Username of the user to follow.
        Returns:
            follow_status (bool): True if followed, False if already following.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before following."}

        if username_to_follow in self.following_list:
            return {"follow_status": False}

        self.following_list.append(username_to_follow)
        return {"follow_status": True}

    def list_all_following(self) -> List[str]:
        """
        List all users that the authenticated user is following.

        Returns:
            following_list (List[str]): List of all users that the authenticated user is following.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before listing following."}

        return self.following_list

    def unfollow_user(self, username_to_unfollow: str) -> Dict[str, bool]:
        """
        Unfollow a user for the authenticated user.

        Args:
            username_to_unfollow (str): Username of the user to unfollow.
        Returns:
            unfollow_status (bool): True if unfollowed, False if not following.
        """
        if not self.authenticated:
            return {"error": "User not authenticated. Please authenticate before unfollowing."}

        if username_to_unfollow not in self.following_list:
            return {"unfollow_status": False}

        self.following_list.remove(username_to_unfollow)
        return {"unfollow_status": True}

    def get_tweet(self, tweet_id: int) -> Dict[str, Union[int, str, List[str]]]:
        """
        Retrieve a specific tweet.

        Args:
            tweet_id (int): ID of the tweet to retrieve.
        Returns:
            id (int): ID of the retrieved tweet.
            username (str): Username of the tweet's author.
            content (str): Content of the tweet.
            tags (List[str]): List of tags associated with the tweet.
            mentions (List[str]): List of users mentioned in the tweet.
        """
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}

        return self.tweets[tweet_id]

    def get_user_tweets(self, username: str) -> List[Dict[str, Union[int, str, List[str]]]]:
        """
        Retrieve all tweets from a specific user.

        Args:
            username (str): Username of the user whose tweets to retrieve.
        Returns:
            user_tweets (List[Dict]): List of dictionaries, each containing tweet information.
                - id (int): ID of the retrieved tweet.
                - username (str): Username of the tweet's author.
                - content (str): Content of the tweet.
                - tags (List[str]): List of tags associated with the tweet.
                - mentions (List[str]): List of users mentioned in the tweet.
        """
        return [tweet for tweet in self.tweets.values() if tweet["username"] == username]

    def search_tweets(self, keyword: str) -> List[Dict[str, Union[int, str, List[str]]]]:
        """
        Search for tweets containing a specific keyword.

        Args:
            keyword (str): Keyword to search for in the content of the tweets.
        Returns:
            matching_tweets (List[Dict]): List of dictionaries, each containing tweet information.
                - id (int): ID of the retrieved tweet.
                - username (str): Username of the tweet's author.
                - content (str): Content of the tweet.
                - tags (List[str]): List of tags associated with the tweet.
                - mentions (List[str]): List of users mentioned in the tweet.
        """
        return [
            tweet
            for tweet in self.tweets.values()
            if keyword.lower() in tweet["content"].lower()
            or keyword.lower() in [tag.lower() for tag in tweet["tags"]]
        ]

    def get_tweet_comments(self, tweet_id: int) -> List[Dict[str, str]]:
        """
        Retrieve all comments for a specific tweet.

        Args:
            tweet_id (int): ID of the tweet to retrieve comments for.
        Returns:
            comments (List[Dict]): List of dictionaries, each containing comment information.
                - username (str): Username of the commenter.
                - content (str): Content of the comment.
        """
        if tweet_id not in self.tweets:
            return {"error": f"Tweet with ID {tweet_id} not found."}
        return self.comments.get(tweet_id, [])

    def get_user_stats(self, username: str) -> Dict[str, int]:
        """
        Get statistics for a specific user.

        Args:
            username (str): Username of the user to get statistics for.
        Returns:
            tweet_count (int): Number of tweets posted by the user.
            following_count (int): Number of users the specified user is following.
            retweet_count (int): Number of retweets made by the user.
        """
        tweet_count = len(
            [tweet for tweet in self.tweets.values() if tweet["username"] == username]
        )
        following_count = len(self.following_list) if username == self.username else 0
        retweet_count = len(self.retweets.get(username, []))

        return {
            "tweet_count": tweet_count,
            "following_count": following_count,
            "retweet_count": retweet_count,
        }


class TwitterPlugin(BasePlugin):
    """Plugin for Twitter API operations.
    
    This plugin provides tools for interacting with Twitter, including 
    authentication, posting tweets, retweeting, commenting, and following users.
    """
    
    def __init__(self):
        """Initialize the Twitter plugin."""
        self.twitter_api = TwitterAPI()
        self._name = "twitter"
        self._description = "Plugin for Twitter operations"
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
        """Generate tool definitions for the Twitter plugin."""
        return [
            {
                "name": "authenticate_twitter",
                "description": "Authenticate a user with username and password",
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
                "name": "posting_get_login_status",
                "description": "Get the login status of the current user",
                "arguments": []
            },
            {
                "name": "post_tweet",
                "description": "Post a tweet for the authenticated user",
                "arguments": [
                    {
                        "name": "content",
                        "description": "Content of the tweet",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "tags",
                        "description": "List of tags for the tweet. Tag name should start with #",
                        "domain": {
                            "type": "list",
                            "importance": 0.2
                        },
                        "required": False,
                        "default": []
                    },
                    {
                        "name": "mentions",
                        "description": "List of users mentioned in the tweet. Mention name should start with @",
                        "domain": {
                            "type": "list",
                            "importance": 0.2
                        },
                        "required": False,
                        "default": []
                    }
                ]
            },
            {
                "name": "retweet",
                "description": "Retweet a tweet for the authenticated user",
                "arguments": [
                    {
                        "name": "tweet_id",
                        "description": "ID of the tweet to retweet",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 9999],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "comment",
                "description": "Comment on a tweet for the authenticated user",
                "arguments": [
                    {
                        "name": "tweet_id",
                        "description": "ID of the tweet to comment on",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 9999],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "comment_content",
                        "description": "Content of the comment",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "mention",
                "description": "Mention specified users in a tweet",
                "arguments": [
                    {
                        "name": "tweet_id",
                        "description": "ID of the tweet where users are mentioned",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 9999],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "mentioned_usernames",
                        "description": "List of usernames to be mentioned",
                        "domain": {
                            "type": "list",
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "follow_user",
                "description": "Follow a user for the authenticated user",
                "arguments": [
                    {
                        "name": "username_to_follow",
                        "description": "Username of the user to follow",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "list_all_following",
                "description": "List all users that the authenticated user is following",
                "arguments": []
            },
            {
                "name": "unfollow_user",
                "description": "Unfollow a user for the authenticated user",
                "arguments": [
                    {
                        "name": "username_to_unfollow",
                        "description": "Username of the user to unfollow",
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
                "name": "get_tweet",
                "description": "Retrieve a specific tweet",
                "arguments": [
                    {
                        "name": "tweet_id",
                        "description": "ID of the tweet to retrieve",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 9999],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_user_tweets",
                "description": "Retrieve all tweets from a specific user",
                "arguments": [
                    {
                        "name": "username",
                        "description": "Username of the user whose tweets to retrieve",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "search_tweets",
                "description": "Search for tweets containing a specific keyword",
                "arguments": [
                    {
                        "name": "keyword",
                        "description": "Keyword to search for in the content of the tweets",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_tweet_comments",
                "description": "Retrieve all comments for a specific tweet",
                "arguments": [
                    {
                        "name": "tweet_id",
                        "description": "ID of the tweet to retrieve comments for",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 9999],
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_user_stats",
                "description": "Get statistics for a specific user",
                "arguments": [
                    {
                        "name": "username",
                        "description": "Username of the user to get statistics for",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            }
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of tools provided by this plugin."""
        return self._tools
    
    def initialize_from_config(self, config_data: Dict[str, Any]) -> bool:
        """Initialize the Twitter API from configuration data."""
        if "TwitterAPI" in config_data:
            twitter_config = config_data["TwitterAPI"]
            self.twitter_api._load_scenario(twitter_config)
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
            # Call the corresponding method on the Twitter API
            api_method = getattr(self.twitter_api, tool_name)
            result = api_method(**parameters)
            
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
                
                # Validate based on domain type
                domain = arg_def.get("domain", {})
                domain_type = domain.get("type", "string")
                
                if domain_type == "numeric_range":
                    try:
                        val = int(value)
                        start, end = domain.get("values", [0, 9999])
                        if not (start <= val <= end):
                            return False, f"Value {value} for {arg_def['name']} is out of range [{start}, {end}]"
                    except (ValueError, TypeError):
                        return False, f"Invalid numeric value for {arg_def['name']}: {value}"
                
                elif domain_type == "list" and not isinstance(value, list):
                    return False, f"Invalid list value for {arg_def['name']}: {value}"
        
        return True, None
    
    def get_domain_updates_from_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update tool domains based on context."""
        updates = {}
        
        # Initialize from config if available
        if "initial_config" in context and hasattr(self, "initialize_from_config"):
            self.initialize_from_config(context["initial_config"])
        
        # Update tweet ID ranges based on available tweets
        if hasattr(self.twitter_api, "tweets") and self.twitter_api.tweets:
            tweet_ids = list(self.twitter_api.tweets.keys())
            min_id = min(tweet_ids) if tweet_ids else 0
            max_id = max(tweet_ids) if tweet_ids else 9999
            
            # Update domains for tweet_id arguments
            for tool_name in ["retweet", "comment", "mention", "get_tweet", "get_tweet_comments"]:
                updates[f"{tool_name}.tweet_id"] = {
                    "type": "numeric_range",
                    "values": [min_id, max_id]
                }
        
        # Update username_to_unfollow domain with current following list
        if hasattr(self.twitter_api, "following_list") and self.twitter_api.following_list:
            updates["unfollow_user.username_to_unfollow"] = {
                "type": "finite",
                "values": self.twitter_api.following_list
            }
        
        return updates
    
    def get_uncertainty_context(self) -> Dict[str, Any]:
        """Get Twitter-specific context for uncertainty calculation."""
        context = {}
        
        if hasattr(self.twitter_api, "authenticated"):
            context["authenticated"] = self.twitter_api.authenticated
        
        if hasattr(self.twitter_api, "username"):
            context["current_username"] = self.twitter_api.username
        
        if hasattr(self.twitter_api, "tweets"):
            context["available_tweets"] = list(self.twitter_api.tweets.keys())
        
        if hasattr(self.twitter_api, "following_list"):
            context["following_list"] = self.twitter_api.following_list
        
        return context
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """Get Twitter-specific prompt templates."""
        return {
            "tool_selection": """
You are an AI assistant that helps users with Twitter operations.

Conversation history:
{conversation_history}

User query: "{user_query}"

Available tools:
{tool_descriptions}

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What is the user trying to do with Twitter?
2. Which Twitter operation(s) are needed to complete this task?
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
You are an AI assistant that helps users with Twitter operations.

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