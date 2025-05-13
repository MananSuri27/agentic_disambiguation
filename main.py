#!/usr/bin/env python
"""
Main entry point for the agentic disambiguation system.
"""

import argparse
import logging
import os
import copy
import uuid
import json
import sys
from typing import Dict, List, Any, Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.plugin_manager import PluginManager
from core.tool_registry import ToolRegistry
from core.uncertainty import UncertaintyCalculator, ToolCall
from core.question_generation import QuestionGenerator, ClarificationQuestion
from core.tool_executor import ToolExecutor

from llm.provider import LLMProvider
from llm.ollama import OllamaProvider
from llm.simulation import UserSimulator

from simulation.mock_api import MockAPIClient
from simulation.evaluation import SimulationEvaluator, SimulationVisualizer
from simulation.data_loader import SimulationDataLoader

from utils.logger import setup_logger
from utils.json_utils import save_json

import config

logger = None  # Will be initialized in main

def initialize_llm_provider(llm_config: Dict[str, Any]) -> LLMProvider:
    """
    Initialize the LLM provider from configuration.
    
    Args:
        llm_config: LLM configuration
        
    Returns:
        Initialized LLM provider
    """
    provider_type = llm_config.get("provider", "ollama")
    
    if provider_type == "ollama":
        return OllamaProvider(
            model_name=llm_config.get("model", "llama3"),
            base_url=llm_config.get("api_base", "http://localhost:11434"),
            json_mode=True
        )
    else:
        # Default to Ollama
        return OllamaProvider()

def initialize_components(active_plugins: List[str]) -> Tuple[PluginManager, ToolRegistry, LLMProvider, UncertaintyCalculator, QuestionGenerator]:
    """
    Initialize system components.
    
    Args:
        active_plugins: List of plugin names to activate
        
    Returns:
        Tuple of (plugin_manager, tool_registry, llm_provider, uncertainty_calculator, question_generator)
    """
    # Initialize the plugin manager
    plugin_manager = PluginManager(plugin_config_dir="config/plugins")
    
    # Load the specified plugins
    for plugin_name in active_plugins:
        success = plugin_manager.load_plugin(plugin_name)
        if not success and plugin_name == "document":
            # If loading from config fails, try registering the document plugin directly
            from plugins.document_plugin import DocumentPlugin
            plugin = DocumentPlugin()
            plugin_manager.register_plugin(plugin)
    
    # Initialize the tool registry with the plugin manager
    tool_registry = ToolRegistry(plugin_manager)
    
    # Initialize the LLM provider
    llm_provider = initialize_llm_provider(config.LLM_CONFIG)
    
    # Initialize the uncertainty calculator
    uncertainty_calculator = UncertaintyCalculator(tool_registry, plugin_manager)
    
    # Initialize the question generator
    question_generator = QuestionGenerator(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        uncertainty_calculator=uncertainty_calculator,
        plugin_manager=plugin_manager
    )
    
    return plugin_manager, tool_registry, llm_provider, uncertainty_calculator, question_generator

def generate_output_filename(input_filename: str) -> str:
    """
    Generate output filename by appending _RESULT to the input filename.
    
    Args:
        input_filename: Original input filename
        
    Returns:
        Output filename
    """
    # Extract the filename without extension and the extension
    base = os.path.basename(input_filename)
    name, ext = os.path.splitext(base)
    
    # Create new filename with _RESULT suffix
    output_filename = f"{name}_RESULT{ext}"
    
    return output_filename

def run_simulation(
    simulation_data: Dict[str, Any],
    plugin_manager: PluginManager,
    tool_registry: ToolRegistry,
    llm_provider: LLMProvider,
    uncertainty_calculator: UncertaintyCalculator,
    question_generator: QuestionGenerator,
    question_config: Dict[str, Any],
    simulation_config: Dict[str, Any],
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run a disambiguation simulation with multi-turn support using the ReactAgent.
    
    Args:
        simulation_data: Simulation data
        plugin_manager: Plugin manager
        tool_registry: Tool registry
        llm_provider: LLM provider
        uncertainty_calculator: Uncertainty calculator
        question_generator: Question generator
        question_config: Question generation configuration
        simulation_config: Simulation configuration
        verbose: Whether to print verbose output
        
    Returns:
        Simulation results
    """
    # Extract simulation data
    user_query = simulation_data.get("user_query", "")
    user_intent = simulation_data.get("user_intent", "")
    ground_truth = simulation_data
    
    # Extract API-specific context and pass it to the relevant plugins
    context = {
        k: v for k, v in simulation_data.items() 
        if k not in ["user_query", "user_intent", "ground_truth_tool_calls", "potential_follow_ups"]
    }
    
    # Update tool registry with data-dependent domains
    tool_registry.update_domain_from_data(context)
    
    # Initialize tool executor
    tool_executor = ToolExecutor(tool_registry, plugin_manager)
    
    # Initialize the React Agent
    from core.react_agent import ReactAgent
    agent = ReactAgent(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        uncertainty_calculator=uncertainty_calculator,
        question_generator=question_generator,
        tool_executor=tool_executor,
        plugin_manager=plugin_manager,
        config=question_config
    )
    
    # Initialize user simulator
    user_simulator = UserSimulator(
        llm_provider=llm_provider,
        ground_truth=ground_truth,
        user_intent=user_intent
    )
    
    # Initialize conversation tracking
    conversation = []
    all_tool_calls = []
    all_execution_results = []
    
    # Add initial user query to conversation
    conversation.append({
        "role": "user",
        "message": user_query,
        "type": "initial"
    })
    
    # Main simulation loop
    turn_count = 0
    max_turns = simulation_config.get("max_turns", 10)
    current_user_input = user_query
    
    # Process the initial query
    while turn_count < max_turns:
        turn_count += 1
        logger.info(f"Turn {turn_count} of {max_turns}")
        
        # Process the current user input through the agent
        is_initial = (turn_count == 1)
        
        # Process the user input
        agent_response = agent.process_user_input(current_user_input, is_initial=is_initial)
        
        # Add agent response to conversation
        conversation.append(agent_response["agent_message"])
        
        # If the agent is asking for clarification
        if agent_response.get("requires_clarification", False):
            # Get user response to clarification
            user_response = user_simulator.get_response_to_question(agent_response["agent_message"]["message"])
            logger.info(f"User response to clarification: {user_response}")
            
            # Add user response to conversation
            conversation.append({
                "role": "user",
                "message": user_response,
                "type": "clarification_response"
            })
            
            # Process the clarification response
            clarification_response = agent.process_clarification_response(
                user_response,
                agent_response.get("potential_tool_calls", [])
            )
            
            # Add agent response to conversation
            conversation.append(clarification_response["agent_message"])
            
            # Track tool calls and execution results
            if "tool_calls" in clarification_response:
                all_tool_calls.extend(clarification_response["tool_calls"])
            if "execution_results" in clarification_response:
                all_execution_results.extend(clarification_response["execution_results"])
        else:
            # Track tool calls and execution results from direct processing
            if "tool_calls" in agent_response:
                all_tool_calls.extend(agent_response["tool_calls"])
            if "execution_results" in agent_response:
                all_execution_results.extend(agent_response["execution_results"])
        
        # Check if the conversation should end
        if agent.should_end_conversation() or turn_count >= max_turns:
            logger.info("Agent indicated conversation should end or max turns reached.")
            break
        
        # Get user's next request
        next_user_input = user_simulator.get_next_request(agent.get_conversation_history())
        
        if next_user_input is None or next_user_input.strip() == "":
            logger.info("User simulator has no more requests.")
            break
        
        # Add follow-up request to conversation
        logger.info(f"User follow-up request: {next_user_input}")
        conversation.append({
            "role": "user",
            "message": next_user_input,
            "type": "follow_up"
        })
        
        # Update current user input for next loop
        current_user_input = next_user_input
    
    # Prepare simulation result
    result = {
        "simulation_id": str(uuid.uuid4()),
        "user_query": user_query,
        "final_tool_calls": all_tool_calls,
        "execution_results": all_execution_results,
        "conversation": conversation,
        "questions": agent.question_history,
        "turns": turn_count,
        "success": all(result.get("success", False) for result in all_execution_results) if all_execution_results else False
    }
    
    # Add evaluation metrics if we have ground truth
    if "ground_truth_tool_calls" in simulation_data:
        evaluator = SimulationEvaluator()
        evaluation_metrics = evaluator.evaluate_simulation(simulation_data, result)
        result["evaluation"] = evaluation_metrics
    
    # If verbose, print conversation
    if verbose:
        visualizer = SimulationVisualizer()
        print("\n" + "="*80)
        print("CONVERSATION:")
        print(visualizer.visualize_conversation(conversation))
        print("\n" + "="*80)
        print("TOOL CALLS:")
        print(visualizer.visualize_tool_calls(all_tool_calls, "Final Tool Calls"))
        if "evaluation" in result:
            print("\n" + "="*80)
            print("EVALUATION:")
            print(visualizer.visualize_metrics(result["evaluation"]))
        print("\n" + "="*80)
    
    return result


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Agentic Disambiguation System")
    parser.add_argument("--data", type=str, help="Path to simulation data file")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    parser.add_argument("--output", type=str, help="Path to output file")
    parser.add_argument("--plugins", type=str, default="document", 
                        help="Comma-separated list of plugins to activate (default: document)")
    args = parser.parse_args()
    
    # Setup logging
    global logger
    log_dir = config.SIMULATION_CONFIG.get("log_dir", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "simulation.log")
    logger = setup_logger(log_file=log_file)
    
    # Parse the plugins argument
    active_plugins = [p.strip() for p in args.plugins.split(",")]
    
    # Initialize components
    plugin_manager, tool_registry, llm_provider, uncertainty_calculator, question_generator = \
        initialize_components(active_plugins)
    
    # Load simulation data
    data_loader = SimulationDataLoader(config.SIMULATION_CONFIG.get("data_dir", "simulation_data"))
    
    if args.data:
        # Run single simulation
        simulation_data = data_loader.load_simulation_data(args.data)
        
        # Run simulation
        result = run_simulation(
            simulation_data=simulation_data,
            plugin_manager=plugin_manager,
            tool_registry=tool_registry,
            llm_provider=llm_provider,
            uncertainty_calculator=uncertainty_calculator,
            question_generator=question_generator,
            question_config=config.QUESTION_CONFIG,
            simulation_config=config.SIMULATION_CONFIG,
            verbose=args.verbose
        )
        
        # Save result
        results_dir = config.SIMULATION_CONFIG.get("results_dir", "simulation_results")
        os.makedirs(results_dir, exist_ok=True)
        
        if args.output:
            output_path = args.output
        else:
            # Generate output filename based on input filename
            output_filename = generate_output_filename(args.data)
            output_path = os.path.join(results_dir, output_filename)
        
        save_json(result, output_path, pretty=True)
        logger.info(f"Saved result to {output_path}")
        
    else:
        # Run all simulations in the data directory
        simulation_files = data_loader.list_simulation_files()
        
        if not simulation_files:
            logger.error("No simulation files found")
            return
        
        results = []
        
        for file_path in simulation_files:
            logger.info(f"Running simulation for {file_path}")
            
            simulation_data = data_loader.load_simulation_data(file_path)
            
            # Run simulation
            result = run_simulation(
                simulation_data=simulation_data,
                plugin_manager=plugin_manager,
                tool_registry=tool_registry,
                llm_provider=llm_provider,
                uncertainty_calculator=uncertainty_calculator,
                question_generator=question_generator,
                question_config=config.QUESTION_CONFIG,
                simulation_config=config.SIMULATION_CONFIG,
                verbose=args.verbose
            )
            
            # Save result
            results_dir = config.SIMULATION_CONFIG.get("results_dir", "simulation_results")
            os.makedirs(results_dir, exist_ok=True)
            
            # Generate output filename based on input filename
            output_filename = generate_output_filename(file_path)
            output_path = os.path.join(results_dir, output_filename)
            
            save_json(result, output_path, pretty=True)
            logger.info(f"Saved result to {output_path}")
            
            # Store result for summary
            results.append(result)

if __name__ == "__main__":
    main()