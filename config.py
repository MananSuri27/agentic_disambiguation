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
    "data_dir": "/fs/nexus-scratch/manans/disambiguation/data/simulation_test_samples",  # Directory for simulation data
    "results_dir": "simulation_results_test_base",  # Directory for simulation results
    "log_dir": "logs",  # Directory for logs
    "max_turns": 10  # Maximum number of conversation turns
}

