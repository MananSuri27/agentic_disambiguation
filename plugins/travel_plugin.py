from typing import Dict, List, Any, Optional, Tuple, Union
import logging
from datetime import datetime
from plugins.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

class TravelAPI:
    """Travel API for handling flight bookings, credit cards, and related operations."""
    
    def __init__(self):
        """Initialize the Travel API with default values."""
        self.credit_card_list = {}
        self.booking_record = {}
        self.access_token = None
        self.token_type = None
        self.token_expires_in = None
        self.token_scope = None
        self.user_first_name = None
        self.user_last_name = None
        self.budget_limit = None
        self._api_description = "This tool belongs to the travel system, which allows users to book flights, manage credit cards, and view budget information."
        self._random = None  # Will be initialized later
    
    def _load_scenario(self, scenario: Dict[str, Any]):
        """
        Load a scenario with predefined data.
        
        Args:
            scenario: Dictionary containing scenario data
        """
        import random
        
        self._random = random.Random(scenario.get("random_seed", 141053))
        self.credit_card_list = scenario.get("credit_card_list", {})
        self.booking_record = scenario.get("booking_record", {})
        self.access_token = scenario.get("access_token", None)
        self.token_type = scenario.get("token_type", None)
        self.token_expires_in = scenario.get("token_expires_in", None)
        self.token_scope = scenario.get("token_scope", None)
        self.user_first_name = scenario.get("user_first_name", None)
        self.user_last_name = scenario.get("user_last_name", None)
        self.budget_limit = scenario.get("budget_limit", None)
    
    def authenticate_travel(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        grant_type: str,
        user_first_name: str,
        user_last_name: str,
    ) -> Dict[str, Union[int, str]]:
        """
        Authenticate the user with the travel API

        Args:
            client_id: The client applications client_id supplied by App Management
            client_secret: The client applications client_secret supplied by App Management
            refresh_token: The refresh token obtained from the initial authentication
            grant_type: The grant type of the authentication request. Here are the options: read_write, read, write
            user_first_name: The first name of the user
            user_last_name: The last name of the user
        Returns:
            Dictionary containing authentication results including:
            - expires_in: The number of time it can use until the access token expires
            - access_token: The access token to be used in the Authorization header of future requests
            - token_type: The type of token
            - scope: The scope of the token
        """
        import random
        if not self._random:
            self._random = random.Random(141053)
            
        self.token_expires_in = 2
        self.access_token = str(self._random.randint(100000, 999999))  # 6 digits
        self.token_type = "Bearer"
        self.token_scope = grant_type
        self.user_first_name = user_first_name
        self.user_last_name = user_last_name
        return {
            "expires_in": 2,
            "access_token": self.access_token,
            "token_type": "Bearer",
            "scope": grant_type,
        }
    
    def travel_get_login_status(self) -> Dict[str, bool]:
        """
        Get the status of the login

        Returns:
            Dictionary containing the login status
        """
        is_not_loggedin = self.token_expires_in is None or self.token_expires_in == 0
        return {"status": not is_not_loggedin}
    
    def get_budget_fiscal_year(
        self,
        lastModifiedAfter: Optional[str] = None,
        includeRemoved: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Get the budget fiscal year

        Args:
            lastModifiedAfter: [Optional] Use this field if you only want Fiscal Years that were changed after the supplied date.
            includeRemoved: [Optional] If true, the service will return all Fiscal Years, including those that were previously removed.
        Returns:
            Dictionary containing the budget fiscal year
        """
        return {"budget_fiscal_year": "2018"}
    
    def register_credit_card(
        self,
        access_token: str,
        card_number: str,
        expiration_date: str,
        cardholder_name: str,
        card_verification_number: int,
    ) -> Dict[str, Union[str, Dict[str, str]]]:
        """
        Register a credit card

        Args:
            access_token: The access token obtained from the authenticate method
            card_number: The credit card number
            expiration_date: The expiration date of the credit card in the format MM/YYYY
            cardholder_name: The name of the cardholder
            card_verification_number: The card verification number
        Returns:
            Dictionary containing the card_id or error message
        """
        import random
        if not self._random:
            self._random = random.Random(141053)
            
        if self.token_expires_in is None:
            return {"error": "Token not initialized"}
        if self.token_expires_in == 0:
            return {"error": "Token expired"}
        if access_token != self.access_token:
            if self.token_expires_in is not None:
                self.token_expires_in -= 1
            return {"error": "Invalid access token"}
        if card_number in self.credit_card_list:
            return {"error": "Card already registered"}
        card_id = str(self._random.randint(100000000000, 999999999999))  # 12 digits
        self.credit_card_list[card_id] = {
            "card_number": card_number,
            "expiration_date": expiration_date,
            "cardholder_name": cardholder_name,
            "card_verification_number": card_verification_number,
            "balance": self._random.randint(10000, 99999),  # 5 digits
        }
        return {"card_id": card_id}
    
    def get_flight_cost(
        self, travel_from: str, travel_to: str, travel_date: str, travel_class: str
    ) -> Dict[str, List[float]]:
        """
        Get the list of cost of a flight in USD based on location, date, and class

        Args:
            travel_from: The 3 letter code of the departing airport
            travel_to: The 3 letter code of the arriving airport
            travel_date: The date of the travel in the format 'YYYY-MM-DD'
            travel_class: The class of the travel. Options are: economy, business, first.
        Returns:
            Dictionary containing a list of flight costs
        """
        base_costs = {
            ("SFO", "LAX"): 200,
            ("SFO", "JFK"): 500,
            ("SFO", "ORD"): 400,
            ("SFO", "BOS"): 450,
            ("LAX", "SFO"): 100,
            ("LAX", "JFK"): 600,
            ("LAX", "ORD"): 500,
            ("LAX", "BOS"): 550,
            ("JFK", "ORD"): 300,
            ("JFK", "BOS"): 250,
            # Add more routes as needed
        }

        # Get the base cost, raise an error if the route is not available
        travel_pair = (travel_from, travel_to)
        if travel_pair in base_costs:
            base_cost = base_costs[travel_pair]
        else:
            return {"error": "No available route for the given airports."}

        # Determine the multiplier based on the travel class
        if travel_class == "economy":
            factor = 1
        elif travel_class == "business":
            factor = 2
        elif travel_class == "first":
            factor = 5
        else:
            return {"error": "Invalid travel class. Options are: economy, business, first."}

        # Determine the multiplier based on the travel date
        digit_sum = sum(int(char) for char in travel_date if char.isdigit())
        travel_date_multiplier = 2 if digit_sum % 2 == 0 else 1

        # Calculate the total cost
        travel_cost = float(base_cost * factor * travel_date_multiplier)
        return {"travel_cost_list": [travel_cost]}
    
    def get_credit_card_balance(
        self, access_token: str, card_id: str
    ) -> Dict[str, Union[float, str]]:
        """
        Get the balance of a credit card
        
        Args:
            access_token: The access token obtained from the authenticate
            card_id: The ID of the credit card
        Returns:
            Dictionary containing the card balance or error message
        """
        if self.token_expires_in == 0:
            return {"error": "Token expired"}
        if access_token != self.access_token:
            self.token_expires_in -= 1
            return {"error": "Invalid access token"}
        if card_id not in self.credit_card_list:
            return {
                "error": "Card not registered. Here are a list of card_id's: "
                + str(list(self.credit_card_list.keys()))
            }
        return {"card_balance": self.credit_card_list[card_id]["balance"]}
    
    def book_flight(
        self,
        access_token: str,
        card_id: str,
        travel_date: str,
        travel_from: str,
        travel_to: str,
        travel_class: str,
        travel_cost: float,
    ) -> Dict[str, Union[str, bool]]:
        """
        Book a flight given the travel information. From and To should be the airport codes in the IATA format.

        Args:
            access_token: The access token obtained from the authenticate
            card_id: The ID of the credit card to use for the booking
            travel_date: The date of the travel in the format YYYY-MM-DD
            travel_from: The location the travel is from
            travel_to: The location the travel is to
            travel_class: The class of the travel
            travel_cost: The cost of the travel
        Returns:
            Dictionary containing booking information or error message
        """
        import random
        if not self._random:
            self._random = random.Random(141053)
            
        if self.token_expires_in == 0:
            return {"booking_status": False, "error": "Token expired"}
        if access_token != self.access_token:
            self.token_expires_in -= 1
            return {"booking_status": False, "error": "Invalid access token"}
        if card_id not in self.credit_card_list:
            return {"booking_status": False, "error": "Card not registered"}
        if "balance" not in self.credit_card_list[card_id]:
            return {"booking_status": False, "error": "Balance not found"}
        if self.credit_card_list[card_id]["balance"] < travel_cost:
            return {"booking_status": False, "error": "Insufficient funds"}
        if (
            self.budget_limit is not None
            and self.credit_card_list[card_id]["balance"] < self.budget_limit
        ):
            return {
                "booking_status": False,
                "error": "Balance is less than budget limit",
            }
        travel_cost = float(travel_cost)
        self.credit_card_list[card_id]["balance"] -= travel_cost
        booking_id = str(self._random.randint(1000000, 9999999))  # 7 digits
        transaction_id = str(self._random.randint(10000000, 99999999))  # 8 digits
        self.booking_record[booking_id] = {
            "card_id": card_id,
            "travel_date": travel_date,
            "travel_from": travel_from,
            "travel_to": travel_to,
            "travel_class": travel_class,
            "travel_cost": travel_cost,
            "transaction_id": transaction_id,
        }
        return {
            "booking_id": booking_id,
            "transaction_id": transaction_id,
            "booking_status": True,
        }
    
    def retrieve_invoice(
        self,
        access_token: str,
        booking_id: Optional[str] = None,
        insurance_id: Optional[str] = None,
    ) -> Dict[str, Union[Dict[str, Union[str, float]], str]]:
        """
        Retrieve the invoice for a booking

        Args:
            access_token: The access token obtained from the authenticate
            booking_id: [Optional] The ID of the booking
            insurance_id: [Optional] The ID of the insurance
        Returns:
            Dictionary containing invoice information or error message
        """
        if self.token_expires_in == 0:
            return {"error": "Token expired"}
        if access_token != self.access_token:
            self.token_expires_in -= 1
            return {"error": "Invalid access token"}
        if booking_id not in self.booking_record:
            return {"error": "Booking not found"}
        invoice = {
            "booking_id": booking_id,
            "travel_date": self.booking_record[booking_id]["travel_date"],
            "travel_from": self.booking_record[booking_id]["travel_from"],
            "travel_to": self.booking_record[booking_id]["travel_to"],
            "travel_class": self.booking_record[booking_id]["travel_class"],
            "travel_cost": self.booking_record[booking_id]["travel_cost"],
            "transaction_id": self.booking_record[booking_id]["transaction_id"],
        }
        return {"invoice": invoice}
    
    def list_all_airports(self) -> Dict[str, List[str]]:
        """
        List all available airports

        Returns:
            Dictionary containing a list of all available airports
        """
        airports = [
            "RMS", "SBK", "MPC", "SVP", "SHD", "CDG", "LHR", "SSV", "OKD", "WLB",
            "PEK", "HND", "HKG", "CIA", "CRH", "ATV", "PHV", "GFD", "SFO", "LAX",
            "JFK", "ORD", "BOS",
        ]
        return {"airports": airports}
    
    def cancel_booking(
        self, access_token: str, booking_id: str
    ) -> Dict[str, Union[bool, str]]:
        """
        Cancel a booking

        Args:
            access_token: The access token obtained from the authenticate
            booking_id: The ID of the booking
        Returns:
            Dictionary containing cancellation status or error message
        """
        if self.token_expires_in == 0:
            return {"cancel_status": False, "error": "Token expired"}
        if access_token != self.access_token:
            self.token_expires_in -= 1
            return {"cancel_status": False, "error": "Invalid access token"}
        if booking_id not in self.booking_record:
            return {"cancel_status": False, "error": "Booking not found"}
        card_id = self.booking_record[booking_id]["card_id"]
        travel_cost = self.booking_record[booking_id]["travel_cost"]
        self.credit_card_list[card_id]["balance"] += travel_cost
        del self.booking_record[booking_id]
        return {"cancel_status": True}
    
    def compute_exchange_rate(
        self, base_currency: str, target_currency: str, value: float
    ) -> Dict[str, float]:
        """
        Compute the exchange rate between two currencies

        Args:
            base_currency: The base currency. [Enum]: USD, RMB, EUR, JPY, GBP, CAD, AUD, INR, RUB, BRL, MXN
            target_currency: The target currency. [Enum]: USD, RMB, EUR, JPY, GBP, CAD, AUD, INR, RUB, BRL, MXN
            value: The value to convert
        Returns:
            Dictionary containing the exchanged value
        """
        exchange_rates = {
            ("USD", "RMB"): 7,
            ("USD", "EUR"): 0.8,
            ("USD", "JPY"): 110,
            ("USD", "GBP"): 0.7,
            ("USD", "CAD"): 1.3,
            ("USD", "AUD"): 1.4,
            ("USD", "INR"): 70,
            ("USD", "RUB"): 60,
            ("USD", "BRL"): 3.8,
            ("USD", "MXN"): 20
        }
        for key, val in exchange_rates.items():
            if base_currency == key[0] and target_currency == key[1]:
                return {"exchanged_value": value * val}
            elif base_currency == key[1] and target_currency == key[0]:
                return {"exchanged_value": round(value / val, 2)}
        return {"error": "No available exchange rate for the given currencies."}
    
    def verify_traveler_information(
        self, first_name: str, last_name: str, date_of_birth: str, passport_number: str
    ) -> Dict[str, Union[bool, str]]:
        """
        Verify the traveler information

        Args:
            first_name: The first name of the traveler
            last_name: The last name of the traveler
            date_of_birth: The date of birth of the traveler in the format YYYY-MM-DD
            passport_number: The passport number of the traveler
        Returns:
            Dictionary containing verification status or error message
        """
        if self.user_first_name != first_name or self.user_last_name != last_name:
            return {
                "verification_status": False,
                "verification_failure": "Cannot book flight information for another user."
                + f"Expected {self.user_first_name} {self.user_last_name}, got {first_name} {last_name}",
            }

        # Calculate age
        try:
            birth_date = datetime.strptime(date_of_birth, "%Y-%m-%d")
            today = datetime.today()
            age = (
                today.year
                - birth_date.year
                - ((today.month, today.day) < (birth_date.month, birth_date.day))
            )
        except ValueError:
            return {
                "verification_status": False,
                "verification_failure": "Invalid date of birth format. Please use YYYY-MM-DD.",
            }

        # Check if the traveler is at least 18 years old
        if age < 18:
            return {
                "verification_status": False,
                "verification_failure": "Traveler must be at least 18 years old.",
            }

        # Check if the passport number starts with 'US' (assuming this indicates a US passport)
        if not passport_number.startswith("US"):
            return {
                "verification_status": False,
                "verification_failure": "Passport must be issued by the United States.",
            }

        # If all checks pass
        return {"verification_status": True}
    
    def set_budget_limit(
        self, access_token: str, budget_limit: float
    ) -> Dict[str, Union[float, str]]:
        """
        Set the budget limit for the user

        Args:
            access_token: The access token obtained from the authentication process or initial configuration.
            budget_limit: The budget limit to set in USD
        Returns:
            Dictionary containing the budget limit or error message
        """
        if self.token_expires_in == 0:
            return {"error": "Token expired"}
        if access_token != self.access_token:
            self.token_expires_in -= 1
            return {"error": "Invalid access token"}
        budget_limit = float(budget_limit)
        self.budget_limit = budget_limit
        return {"budget_limit": budget_limit}
    
    def get_nearest_airport_by_city(self, location: str) -> Dict[str, str]:
        """
        Get the nearest airport to the given location

        Args:
            location: The name of the location. [Enum]: Rivermist, Stonebrook, Maplecrest, Silverpine, Shadowridge, London, Paris, Sunset Valley, Oakendale, Willowbend, Crescent Hollow, Autumnville, Pinehaven, Greenfield, San Francisco, Los Angeles, New York, Chicago, Boston, Beijing, Hong Kong, Rome, Tokyo
        Returns:
            Dictionary containing the nearest airport
        """
        airport_map = {
            "Rivermist": "RMS",
            "Stonebrook": "SBK",
            "Maplecrest": "MPC",
            "Silverpine": "SVP",
            "Shadowridge": "SHD",
            "London": "LHR",
            "Paris": "CDG",
            "Sunset Valley": "SSV",
            "Oakendale": "OKD",
            "Willowbend": "WLB",
            "Crescent Hollow": "CRH",
            "Autumnville": "ATV",
            "Pinehaven": "PHV",
            "Greenfield": "GFD",
            "San Francisco": "SFO",
            "Los Angeles": "LAX",
            "New York": "JFK",
            "Chicago": "ORD",
            "Boston": "BOS",
            "Beijing": "PEK",
            "Hong Kong": "HKG",
            "Rome": "CIA",
            "Tokyo": "HND",
        }

        return {"nearest_airport": airport_map.get(location, "Unknown")}
    
    def purchase_insurance(
        self,
        access_token: str,
        insurance_type: str,
        booking_id: str,
        insurance_cost: float,
        card_id: str,
    ) -> Dict[str, Union[str, bool]]:
        """
        Purchase insurance

        Args:
            access_token: The access token obtained from the authenticate
            insurance_type: The type of insurance to purchase
            insurance_cost: The cost of the insurance
            booking_id: The ID of the booking
            card_id: The ID of the credit card to use for the
        Returns:
            Dictionary containing insurance information or error message
        """
        import random
        if not self._random:
            self._random = random.Random(141053)
            
        if self.token_expires_in == 0:
            return {"insurance_status": False, "error": "Token expired"}
        if access_token != self.access_token:
            self.token_expires_in -= 1
            return {"insurance_status": False, "error": "Invalid access token"}
        if self.budget_limit is not None and self.budget_limit < insurance_cost:
            return {"insurance_status": False, "error": "Exceeded budget limit"}
        if booking_id not in self.booking_record:
            return {"insurance_status": False, "error": "Booking not found"}
        if card_id not in self.credit_card_list:
            return {"insurance_status": False, "error": "Credit card not registered"}
        self.credit_card_list[card_id]["balance"] -= insurance_cost
        return {
            "insurance_id": str(self._random.randint(100000000, 999999999)),  # 9 digits
            "insurance_status": True,
        }
    
    def contact_customer_support(self, booking_id: str, message: str) -> Dict[str, str]:
        """
        Contact travel booking customer support, get immediate support on an issue with an online call.

        Args:
            booking_id: The ID of the booking
            message: The message to send to customer support
        Returns:
            Dictionary containing the customer support message or error message
        """
        if booking_id not in self.booking_record:
            return {"error": "Booking not found"}
        return {
            "customer_support_message": "Thank you for contacting customer support. We will get back to you shortly. "
            + message
        }
    
    def get_all_credit_cards(self) -> Dict[str, Dict[str, Union[str, int, float]]]:
        """
        Get all registered credit cards

        Returns:
            Dictionary containing all registered credit cards
        """
        return {"credit_card_list": self.credit_card_list}


class TravelPlugin(BasePlugin):
    """
    Plugin for travel-related operations.
    
    This plugin provides tools for booking flights, managing credit cards,
    and performing various travel-related operations.
    """
    
    def __init__(self):
        """Initialize the travel plugin."""
        self.travel_api = TravelAPI()
        self._name = "travel"
        self._description = "Plugin for travel-related operations, including flight bookings, credit card management, and travel information."
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
        """Generate tool definitions for the travel plugin."""
        return [
            {
                "name": "authenticate_travel",
                "description": "Authenticate the user with the travel API",
                "arguments": [
                    {
                        "name": "client_id",
                        "description": "The client applications client_id supplied by App Management",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "client_secret",
                        "description": "The client applications client_secret supplied by App Management",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "refresh_token",
                        "description": "The refresh token obtained from the initial authentication",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "grant_type",
                        "description": "The grant type of the authentication request (read_write, read, write)",
                        "domain": {
                            "type": "finite",
                            "values": ["read_write", "read", "write"],
                            "importance": 0.7
                        },
                        "required": True
                    },
                    {
                        "name": "user_first_name",
                        "description": "The first name of the user",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "user_last_name",
                        "description": "The last name of the user",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "travel_get_login_status",
                "description": "Get the status of the login",
                "arguments": []
            },
            {
                "name": "get_budget_fiscal_year",
                "description": "Get the budget fiscal year",
                "arguments": [
                    {
                        "name": "lastModifiedAfter",
                        "description": "Use this field if you only want Fiscal Years that were changed after the supplied date",
                        "domain": {
                            "type": "string",
                            "importance": 0.5
                        },
                        "required": False,
                        "default": None
                    },
                    {
                        "name": "includeRemoved",
                        "description": "If true, the service will return all Fiscal Years, including those that were previously removed",
                        "domain": {
                            "type": "string",
                            "importance": 0.5
                        },
                        "required": False,
                        "default": None
                    }
                ]
            },
            {
                "name": "register_credit_card",
                "description": "Register a credit card",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate method",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "card_number",
                        "description": "The credit card number",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "expiration_date",
                        "description": "The expiration date of the credit card in the format MM/YYYY",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "cardholder_name",
                        "description": "The name of the cardholder",
                        "domain": {
                            "type": "string",
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "card_verification_number",
                        "description": "The card verification number",
                        "domain": {
                            "type": "numeric_range",
                            "values": [100, 999],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_flight_cost",
                "description": "Get the list of cost of a flight in USD based on location, date, and class",
                "arguments": [
                    {
                        "name": "travel_from",
                        "description": "The 3 letter code of the departing airport",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "travel_to",
                        "description": "The 3 letter code of the arriving airport",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "travel_date",
                        "description": "The date of the travel in the format 'YYYY-MM-DD'",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "travel_class",
                        "description": "The class of the travel. Options are: economy, business, first",
                        "domain": {
                            "type": "finite",
                            "values": ["economy", "business", "first"],
                            "importance": 0.8
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_credit_card_balance",
                "description": "Get the balance of a credit card",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "card_id",
                        "description": "The ID of the credit card",
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
                "name": "book_flight",
                "description": "Book a flight given the travel information",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "card_id",
                        "description": "The ID of the credit card to use for the booking",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "travel_date",
                        "description": "The date of the travel in the format YYYY-MM-DD",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "travel_from",
                        "description": "The location the travel is from (3-letter airport code)",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "travel_to",
                        "description": "The location the travel is to (3-letter airport code)",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "travel_class",
                        "description": "The class of the travel",
                        "domain": {
                            "type": "finite",
                            "values": ["economy", "business", "first"],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "travel_cost",
                        "description": "The cost of the travel",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 10000],
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "retrieve_invoice",
                "description": "Retrieve the invoice for a booking",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "booking_id",
                        "description": "The ID of the booking",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": False,
                        "default": None
                    },
                    {
                        "name": "insurance_id",
                        "description": "The ID of the insurance",
                        "domain": {
                            "type": "string",
                            "importance": 0.7,
                            "data_dependent": True
                        },
                        "required": False,
                        "default": None
                    }
                ]
            },
            {
                "name": "list_all_airports",
                "description": "List all available airports",
                "arguments": []
            },
            {
                "name": "cancel_booking",
                "description": "Cancel a booking",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "booking_id",
                        "description": "The ID of the booking",
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
                "name": "compute_exchange_rate",
                "description": "Compute the exchange rate between two currencies",
                "arguments": [
                    {
                        "name": "base_currency",
                        "description": "The base currency",
                        "domain": {
                            "type": "finite",
                            "values": ["USD", "RMB", "EUR", "JPY", "GBP", "CAD", "AUD", "INR", "RUB", "BRL", "MXN"],
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "target_currency",
                        "description": "The target currency",
                        "domain": {
                            "type": "finite",
                            "values": ["USD", "RMB", "EUR", "JPY", "GBP", "CAD", "AUD", "INR", "RUB", "BRL", "MXN"],
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "value",
                        "description": "The value to convert",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 1000000],
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "verify_traveler_information",
                "description": "Verify the traveler information",
                "arguments": [
                    {
                        "name": "first_name",
                        "description": "The first name of the traveler",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "last_name",
                        "description": "The last name of the traveler",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "date_of_birth",
                        "description": "The date of birth of the traveler in the format YYYY-MM-DD",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "passport_number",
                        "description": "The passport number of the traveler",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "set_budget_limit",
                "description": "Set the budget limit for the user",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "budget_limit",
                        "description": "The budget limit to set in USD",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 10000],
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_nearest_airport_by_city",
                "description": "Get the nearest airport to the given location",
                "arguments": [
                    {
                        "name": "location",
                        "description": "The name of the location",
                        "domain": {
                            "type": "finite",
                            "values": [
                                "Rivermist", "Stonebrook", "Maplecrest", "Silverpine", "Shadowridge", 
                                "London", "Paris", "Sunset Valley", "Oakendale", "Willowbend", 
                                "Crescent Hollow", "Autumnville", "Pinehaven", "Greenfield", 
                                "San Francisco", "Los Angeles", "New York", "Chicago", "Boston", 
                                "Beijing", "Hong Kong", "Rome", "Tokyo"
                            ],
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "purchase_insurance",
                "description": "Purchase insurance for a booking",
                "arguments": [
                    {
                        "name": "access_token",
                        "description": "The access token obtained from the authenticate",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "insurance_type",
                        "description": "The type of insurance to purchase",
                        "domain": {
                            "type": "finite",
                            "values": ["basic", "premium", "deluxe"],
                            "importance": 0.8
                        },
                        "required": True
                    },
                    {
                        "name": "booking_id",
                        "description": "The ID of the booking",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "insurance_cost",
                        "description": "The cost of the insurance",
                        "domain": {
                            "type": "numeric_range",
                            "values": [0, 1000],
                            "importance": 0.9
                        },
                        "required": True
                    },
                    {
                        "name": "card_id",
                        "description": "The ID of the credit card to use for the insurance purchase",
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
                "name": "contact_customer_support",
                "description": "Contact travel booking customer support",
                "arguments": [
                    {
                        "name": "booking_id",
                        "description": "The ID of the booking",
                        "domain": {
                            "type": "string",
                            "importance": 0.9,
                            "data_dependent": True
                        },
                        "required": True
                    },
                    {
                        "name": "message",
                        "description": "The message to send to customer support",
                        "domain": {
                            "type": "string",
                            "importance": 0.9
                        },
                        "required": True
                    }
                ]
            },
            {
                "name": "get_all_credit_cards",
                "description": "Get all registered credit cards",
                "arguments": []
            }
        ]
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Get the list of tools provided by this plugin."""
        return self._tools
    
    def initialize_from_config(self, config_data: Dict[str, Any]) -> bool:
        """Initialize the travel API from configuration data."""
        if "TravelAPI" in config_data:
            travel_config = config_data["TravelAPI"]
            self.travel_api._load_scenario(travel_config)
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
            # Call the corresponding method on the travel API
            if hasattr(self.travel_api, tool_name):
                api_method = getattr(self.travel_api, tool_name)
                result = api_method(**parameters)
                
                # Check if the result indicates an error
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
            else:
                return {
                    "success": False,
                    "message": f"Unknown tool: {tool_name}",
                    "error": "UNKNOWN_TOOL"
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
                
                # Skip empty values for optional parameters
                if value is None and not arg_def.get("required", True):
                    continue
                    
                # Validate based on domain type
                domain = arg_def.get("domain", {})
                domain_type = domain.get("type", "string")
                
                if domain_type == "numeric_range":
                    try:
                        val = float(value)
                        start, end = domain.get("values", [0, 1000000])
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
        if "initial_config" in context and "TravelAPI" in context["initial_config"]:
            self.initialize_from_config(context["initial_config"])
        
        # Update card_id domains based on available credit cards
        card_ids = list(self.travel_api.credit_card_list.keys())
        if card_ids:
            card_id_fields = [
                "get_credit_card_balance.card_id",
                "book_flight.card_id",
                "purchase_insurance.card_id"
            ]
            for field in card_id_fields:
                updates[field] = {
                    "type": "finite",
                    "values": card_ids
                }
        
        # Update booking_id domains based on available bookings
        booking_ids = list(self.travel_api.booking_record.keys())
        if booking_ids:
            booking_id_fields = [
                "retrieve_invoice.booking_id",
                "cancel_booking.booking_id",
                "purchase_insurance.booking_id",
                "contact_customer_support.booking_id"
            ]
            for field in booking_id_fields:
                updates[field] = {
                    "type": "finite",
                    "values": booking_ids
                }
        
        # Get list of airports for travel domains
        airports = ["SFO", "LAX", "JFK", "ORD", "BOS", "RMS", "SBK", "MPC", "SVP", "SHD", "CDG", "LHR", "SSV", "OKD", "WLB", "PEK", "HND", "HKG", "CIA", "CRH", "ATV", "PHV", "GFD"]
        
        if airports:
            travel_fields = [
                "get_flight_cost.travel_from",
                "get_flight_cost.travel_to",
                "book_flight.travel_from", 
                "book_flight.travel_to"
            ]
            for field in travel_fields:
                updates[field] = {
                    "type": "finite",
                    "values": airports
                }
        
        return updates
    
    def get_uncertainty_context(self) -> Dict[str, Any]:
        """Get travel-specific context for uncertainty calculation."""
        context = {
            "authenticated": self.travel_api.access_token is not None,
            "has_credit_cards": len(self.travel_api.credit_card_list) > 0,
            "has_bookings": len(self.travel_api.booking_record) > 0
        }
        
        if context["has_credit_cards"]:
            context["available_card_ids"] = list(self.travel_api.credit_card_list.keys())
        
        if context["has_bookings"]:
            context["available_booking_ids"] = list(self.travel_api.booking_record.keys())
        
        return context
    
    def get_prompt_templates(self) -> Dict[str, str]:
        """Get travel-specific prompt templates."""
        return {
            "tool_selection": """
You are an AI assistant that helps users with travel-related operations.

Conversation history:
{conversation_history}

User query: "{user_query}"

Available tools:
{tool_descriptions}

Please analyze the user's query and determine which tool(s) should be called to fulfill the request.
For each tool, specify all required parameters. If a parameter is uncertain, use "<UNK>" as the value.

Think through this step by step:
1. What is the user trying to do with the travel system?
2. Which travel operation(s) are needed to complete this task?
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
You are an AI assistant that helps users with travel-related operations.

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