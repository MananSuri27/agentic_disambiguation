#!/usr/bin/env python
"""
Main entry point for the agentic disambiguation system.
"""

import argparse
import logging
import os
import uuid
import json
import sys
import traceback
from typing import Dict, List, Any, Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.plugin_manager import PluginManager
from core.tool_registry import ToolRegistry
from core.uncertainty import UncertaintyCalculator
from core.question_generation import QuestionGenerator
from core.tool_executor import ToolExecutor
from core.react_agent import ReactAgent

from llm.provider import LLMProvider
from llm.ollama import OllamaProvider
from llm.simulation import UserSimulator

from simulation.evaluation import SimulationEvaluator, SimulationVisualizer
from simulation.data_loader import SimulationDataLoader

from utils.logger import setup_logger
from utils.json_utils import save_json

import config

logger = None  # Will be initialized in main


def initialize_llm_provider(llm_config: Dict[str, Any]) -> LLMProvider:
    """Initialize the LLM provider from configuration."""
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


def determine_plugin_from_simulation_data(simulation_data: Dict[str, Any]) -> Optional[str]:
    """Determine which plugin to load based on the simulation data."""
    # Check for explicit primary_api field
    if "primary_api" in simulation_data:
        api_name = simulation_data["primary_api"]
        # Map API names to plugin names
        api_to_plugin = {
            "GorillaFileSystem": "gfs",
            "TravelAPI": "travel", 
            "TradingBot": "trading",
            "VehicleControlAPI": "vehicle",
            "DocumentPlugin": "document"
        }
        return api_to_plugin.get(api_name)
    
    return None


def initialize_components(plugin_name: str, simulation_data: Optional[Dict[str, Any]] = None) -> Tuple[PluginManager, ToolRegistry, LLMProvider, UncertaintyCalculator, QuestionGenerator]:
    """Initialize system components with the specified plugin."""
    # Initialize the plugin manager
    plugin_manager = PluginManager(plugin_config_dir="config/plugins")
    
    # Load the specified plugin
    success = plugin_manager.load_plugin(plugin_name)
    if not success:
        logger.warning(f"Failed to load plugin {plugin_name} from config, trying direct import")
        # Try loading plugin directly based on name
        if plugin_name == "gfs":
            from plugins.gfs_plugin import GFSPlugin
            plugin = GFSPlugin()
            plugin_manager.register_plugin(plugin)
        elif plugin_name == "travel":
            from plugins.travel_plugin import TravelPlugin
            plugin = TravelPlugin()
            plugin_manager.register_plugin(plugin)
        elif plugin_name == "trading":
            from plugins.trading_plugin import TradingPlugin
            plugin = TradingPlugin()
            plugin_manager.register_plugin(plugin)
        elif plugin_name == "vehicle_control":
            from plugins.vehicle_plugin import VehicleControlPlugin
            plugin = VehicleControlPlugin()
            plugin_manager.register_plugin(plugin)
        elif plugin_name == "document":
            from plugins.document_plugin import DocumentPlugin
            plugin = DocumentPlugin()
            plugin_manager.register_plugin(plugin)
        else:
            raise ValueError(f"Unknown plugin: {plugin_name}")
    
    # Initialize plugin from simulation data if available
    if simulation_data and "initial_config" in simulation_data:
        plugin = plugin_manager.get_plugin(plugin_name)
        if plugin and hasattr(plugin, "initialize_from_config"):
            plugin.initialize_from_config(simulation_data["initial_config"])
            logger.info(f"Initialized {plugin_name} from config")
    
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
    """Generate output filename by appending _RESULT to the input filename."""
    base = os.path.basename(input_filename)
    name, ext = os.path.splitext(base)
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
    user_intent = simulation_data.get("user_intention", "")
    follow_ups = simulation_data.get("follow_ups", [])
    ground_truth = simulation_data
    
    # Extract API-specific context and pass it to relevant plugins
    context = {
        k: v for k, v in simulation_data.items() 
        if k not in ["user_query", "user_intention", "ground_truth_tool_calls", "follow_ups"]
    }
    
    # Ensure initial_config is included in context
    if "initial_config" in simulation_data and "initial_config" not in context:
        context["initial_config"] = simulation_data["initial_config"]
    
    # Update tool registry with data-dependent domains
    tool_registry.update_domain_from_data(context)
    
    # Initialize components
    tool_executor = ToolExecutor(tool_registry, plugin_manager)
    agent = ReactAgent(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        uncertainty_calculator=uncertainty_calculator,
        question_generator=question_generator,
        tool_executor=tool_executor,
        plugin_manager=plugin_manager,
        config=question_config
    )
    user_simulator = UserSimulator(
        llm_provider=llm_provider,
        ground_truth=ground_truth,
        user_intent=user_intent
    )
    
    # Process all requests (initial + follow-ups)
    all_requests = [("initial", user_query)] + [("follow_up", req) for req in follow_ups]
    max_clarifications = simulation_config.get("max_clarifications_per_request", 5)
    
    for request_type, request_text in all_requests:
        logger.info(f"Processing {request_type} request: {request_text}")
        
        # Start tracking this request
        agent.start_new_request(request_text, request_type)
        
        # Fresh context for each request (observations reset)
        request_context = {"observations": []}
        current_request = request_text
        
        # Clarification loop for this request
        clarifications_made = 0
        while clarifications_made < max_clarifications:
            # Run the agent
            result = agent.run(current_request, request_context)
            
            if result.success:
                # Request completed successfully
                logger.info(f"Request completed: {result.message}")
                executed_tools = [
                    tc for tc in agent.get_compatibility_data()["final_tool_calls"]
                    if tc.get("request_index") == len(agent.conversation_tracker.requests) - 1
                ]
                agent.complete_current_request(True, result.message, executed_tools)
                break
                
            elif result.type in ["clarification", "error_clarification"]:
                # Agent needs clarification
                logger.info(f"Agent needs clarification: {result.message}")
                
                # Get user response
                user_response = user_simulator.get_response_to_question(result.message)
                
                if user_response is None:
                    # User done with requests
                    logger.info("User has no response to clarification, ending this request")
                    agent.complete_current_request(False, "Incomplete due to lack of clarification", [])
                    break
                
                logger.info(f"User clarification: {user_response}")
                
                # Enrich the request with clarification
                current_request = agent.process_clarification(request_text, user_response)
                clarifications_made += 1
                
                # Continue loop with enriched request and SAME context (observations persist)
                
            else:
                # Some other error
                logger.error(f"Request failed: {result.message}")
                agent.complete_current_request(False, result.message, [])
                break
        
        if clarifications_made >= max_clarifications:
            logger.warning(f"Request exceeded max clarifications ({max_clarifications})")
            agent.complete_current_request(False, "Exceeded max clarifications", [])
    
    # Export results in both formats
    detailed_conversation = agent.get_full_conversation_data()
    compatibility_data = agent.get_compatibility_data()
    
    # Prepare simulation result
    result = {
        "simulation_id": str(uuid.uuid4()),
        "user_query": user_query,
        
        # Nested detailed structure
        **detailed_conversation,
        
        # Flat compatibility structure
        **compatibility_data,
        
        # Additional compatibility fields
        "questions": compatibility_data.get("questions", []),
        "all_candidate_questions": question_generator.get_all_candidate_questions(),
        "success": all(req.request_result and req.request_result["success"] 
                      for req in agent.conversation_tracker.requests),
        "turns": detailed_conversation["metrics"]["total_turns"],
        "execution_results": []  # Legacy field, can be derived from tool attempts
    }
    
    # Add evaluation metrics if we have ground truth
    if "ground_truth_tool_calls" in simulation_data:
        evaluator = SimulationEvaluator()
        evaluation_metrics = evaluator.evaluate_simulation(simulation_data, result)
        result["evaluation"] = evaluation_metrics
    
    # Display results if verbose
    if verbose:
        visualizer = SimulationVisualizer()
        print("\n" + "="*80)
        print("CONVERSATION:")
        print(visualizer.visualize_conversation(compatibility_data["conversation"]))
        print("\n" + "="*80)
        print("TOOL CALLS:")
        print(visualizer.visualize_tool_calls(
            compatibility_data["final_tool_calls"], 
            "Final Tool Calls", 
            compatibility_data["all_tool_call_attempts"]
        ))
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
    args = parser.parse_args()
    
    # Setup logging
    global logger
    log_dir = config.SIMULATION_CONFIG.get("log_dir", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "simulation.log")
    logger = setup_logger(log_file=log_file)
    
    # Load simulation data
    data_loader = SimulationDataLoader(config.SIMULATION_CONFIG.get("data_dir", "simulation_data"))
    
    if args.data:
        # Run single simulation
        try:
            simulation_data = data_loader.load_simulation_data(args.data)
            
            # Determine which plugin to load from the simulation data
            plugin_name = determine_plugin_from_simulation_data(simulation_data)
            if not plugin_name:
                raise ValueError(f"Could not determine plugin from simulation data in {args.data}")
            
            logger.info(f"Determined plugin: {plugin_name}")

            # Initialize components with the determined plugin
            plugin_manager, tool_registry, llm_provider, uncertainty_calculator, question_generator = \
                initialize_components(plugin_name, simulation_data)
            
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
                output_filename = generate_output_filename(args.data)
                output_path = os.path.join(results_dir, output_filename)
            
            save_json(result, output_path, pretty=True)
            logger.info(f"Saved result to {output_path}")
            
        except Exception as e:
            logger.exception(f"Error running simulation for {args.data}: {str(e)}")
            print(f"ERROR: Failed to run simulation for {args.data}: {str(e)}")
            
            # Create an error result
            error_result = {
                "simulation_id": str(uuid.uuid4()),
                "user_query": simulation_data.get("user_query", "") if "simulation_data" in locals() else "",
                "error": True,
                "error_message": str(e),
                "error_traceback": traceback.format_exc()
            }
            
            # Save error result
            results_dir = config.SIMULATION_CONFIG.get("results_dir", "simulation_results")
            os.makedirs(results_dir, exist_ok=True)
            
            if args.output:
                output_path = args.output
            else:
                output_filename = generate_output_filename(args.data)
                output_path = os.path.join(results_dir, output_filename)
            
            save_json(error_result, output_path, pretty=True)
            logger.info(f"Saved error result to {output_path}")
            
    else:
        # Run all simulations in the data directory
        simulation_files = data_loader.list_simulation_files()
        
        if not simulation_files:
            logger.error("No simulation files found")
            print(f"No simulation files found in {config.SIMULATION_CONFIG.get('data_dir', 'simulation_data')}")
            return
        
        successful_runs = 0
        failed_runs = 0
        
        for file_path in simulation_files:
            # Skip summary files
            if os.path.basename(file_path) in ["summary.json", "metrics_summary.json"]:
                continue
                
            logger.info(f"Running simulation for {file_path}")
            
            try:
                simulation_data = data_loader.load_simulation_data(file_path)
                
                # Determine which plugin to load from the simulation data
                plugin_name = determine_plugin_from_simulation_data(simulation_data)
                if not plugin_name:
                    raise ValueError(f"Could not determine plugin from simulation data in {file_path}")
                
                logger.info(f"Determined plugin: {plugin_name} for {file_path}")

                # Initialize components with the determined plugin
                plugin_manager, tool_registry, llm_provider, uncertainty_calculator, question_generator = \
                    initialize_components(plugin_name, simulation_data)
                
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
                
                output_filename = generate_output_filename(file_path)
                output_path = os.path.join(results_dir, output_filename)
                
                save_json(result, output_path, pretty=True)
                logger.info(f"Saved result to {output_path}")
                
                successful_runs += 1
                
            except Exception as e:
                logger.exception(f"Error running simulation for {file_path}: {str(e)}")
                print(f"ERROR: Failed to run simulation for {file_path}: {str(e)}")
                
                # Create an error result
                error_result = {
                    "simulation_id": str(uuid.uuid4()),
                    "user_query": simulation_data.get("user_query", "") if "simulation_data" in locals() else "",
                    "error": True,
                    "error_message": str(e),
                    "error_traceback": traceback.format_exc(),
                    "file_path": file_path
                }
                
                # Save error result
                results_dir = config.SIMULATION_CONFIG.get("results_dir", "simulation_results")
                os.makedirs(results_dir, exist_ok=True)
                
                output_filename = generate_output_filename(file_path)
                output_path = os.path.join(results_dir, output_filename)
                
                save_json(error_result, output_path, pretty=True)
                logger.info(f"Saved error result to {output_path}")
                
                failed_runs += 1
                continue
        
        # Create summary
        summary = {
            "total_runs": len(simulation_files),
            "successful_runs": successful_runs,
            "failed_runs": failed_runs,
            "success_rate": successful_runs / len(simulation_files) if simulation_files else 0.0
        }
        
        # Save summary
        summary_path = os.path.join(config.SIMULATION_CONFIG.get("results_dir", "simulation_results"), "summary.json")
        save_json(summary, summary_path, pretty=True)
        logger.info(f"Saved summary to {summary_path}")
        print(f"Completed {successful_runs} simulations successfully, {failed_runs} failed. See {summary_path} for details.")


if __name__ == "__main__":
    main()