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
    Run a disambiguation simulation.
    
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
        if k not in ["user_query", "user_intent", "ground_truth_tool_calls"]
    }
    
    # Update tool registry with data-dependent domains
    tool_registry.update_domain_from_data(context)
    
    # Initialize tool executor
    tool_executor = ToolExecutor(tool_registry, plugin_manager)
    
    # Initialize user simulator
    user_simulator = UserSimulator(
        llm_provider=llm_provider,
        ground_truth=ground_truth,
        user_intent=user_intent
    )
    
    # Initialize conversation logging
    conversation = []
    conversation.append({
        "role": "user",
        "message": user_query,
        "type": "initial"
    })
    
    # Generate initial tool calls
    logger.info(f"Generating initial tool calls for: {user_query}")
    tool_descriptions = tool_registry.get_tool_descriptions()
    
    tool_call_results = llm_provider.generate_tool_calls(
        user_query=user_query,
        tool_descriptions=tool_descriptions
    )
    
    # Convert to ToolCall objects
    tool_calls = []
    for tc_result in tool_call_results:
        tool_name = tc_result.get("tool_name", "")
        arguments = tc_result.get("arguments", {})
        
        tool_call = ToolCall(tool_name, arguments)
        tool_calls.append(tool_call)
    
    initial_tool_calls = copy.deepcopy(tool_calls)
    
    # Calculate initial uncertainty
    overall_certainty, arg_certainties = uncertainty_calculator.calculate_sequence_certainty(tool_calls)
    logger.info(f"Initial overall certainty: {overall_certainty}")
    
    # Store question metrics
    question_metrics = []
    
    # Main disambiguation loop
    max_turns = simulation_config.get("max_turns", 10)
    turn_count = 0
    
    while turn_count < max_turns:
        turn_count += 1
        logger.info(f"Turn {turn_count} of {max_turns}")
        
        # Calculate uncertainty
        overall_certainty, arg_certainties = uncertainty_calculator.calculate_sequence_certainty(tool_calls)
        logger.info(f"Current overall certainty: {overall_certainty}")
        
        # Check if overall certainty is high enough
        certainty_threshold = question_config.get("certainty_threshold", 0.9)
        if overall_certainty > certainty_threshold:
            logger.info(f"Certainty is high enough ({overall_certainty:.4f} > {certainty_threshold}), proceeding to execution")
            conversation.append({
                "role": "agent",
                "message": "I have enough information to proceed.",
                "type": "confirmation"
            })
            break
        
        # Generate candidate questions
        candidate_questions = question_generator.generate_candidate_questions(
            user_query=user_query,
            tool_calls=tool_calls,
            max_questions=question_config.get("max_candidates", 5)
        )
        
        # Evaluate questions
        best_question, eval_metrics = question_generator.evaluate_questions(
            questions=candidate_questions,
            tool_calls=tool_calls,
            base_threshold=question_config.get("base_threshold", 0.1),
            certainty_threshold=certainty_threshold
        )
        
        # Store question metrics for evaluation
        if candidate_questions:
            for q in candidate_questions:
                question_metrics.append(q.to_dict())
        
        # Check if we should ask a question
        if best_question:
            # Ask the question
            question_text = best_question.question_text
            logger.info(f"Asking clarification question: {question_text}")
            
            conversation.append({
                "role": "agent",
                "message": question_text,
                "type": "clarification"
            })
            
            # Get user response
            user_response = user_simulator.get_response_to_question(question_text)
            logger.info(f"User response: {user_response}")
            
            conversation.append({
                "role": "user",
                "message": user_response,
                "type": "clarification_response"
            })
            
            # Update argument clarification counts
            question_generator.update_arg_clarification_counts(best_question)
            
            # Process user response to update tool calls
            updated_tool_calls = question_generator.process_user_response(
                question=best_question,
                user_response=user_response,
                tool_calls=tool_calls
            )
            
            # Update tool calls
            tool_calls = updated_tool_calls
            
        else:
            # No good questions, proceed to execution
            logger.info("No good questions to ask, proceeding to execution")
            conversation.append({
                "role": "agent",
                "message": "I'll proceed with the information I have.",
                "type": "confirmation"
            })
            break
    
    # Execute tool calls
    logger.info("Executing tool calls")
    conversation.append({
        "role": "agent",
        "message": f"Executing the following actions: {[tc.tool_name for tc in tool_calls]}",
        "type": "execution"
    })
    
    execution_results = tool_executor.execute_tool_calls(tool_calls)
    
    # Check if all executions were successful
    all_succeeded = all(result.success for result in execution_results)
    
    if all_succeeded:
        conversation.append({
            "role": "agent",
            "message": "All actions executed successfully.",
            "type": "execution_result"
        })
    else:
        # Get the first error
        error_result = next((result for result in execution_results if not result.success), None)
        if error_result:
            error_message = f"Error executing {error_result.tool_name}: {error_result.message}"
            
            # Try to get a clarification question for the error
            clarification_question, updated_tool_calls = tool_executor.generate_error_clarification(
                error_result=error_result,
                tool_calls=tool_calls,
                user_query=user_query,
                llm_provider=llm_provider
            )
            
            if clarification_question:
                logger.info(f"Generated error clarification question: {clarification_question}")
                
                # Add the error and question to the conversation
                conversation.append({
                    "role": "agent",
                    "message": f"{error_message}\n\n{clarification_question}",
                    "type": "error_clarification"
                })
                
                # Get user response
                user_response = user_simulator.get_response_to_question(clarification_question)
                logger.info(f"User response to error: {user_response}")
                
                conversation.append({
                    "role": "user",
                    "message": user_response,
                    "type": "error_response"
                })
                
                # Create a dummy ClarificationQuestion to update arg counts
                error_q = ClarificationQuestion(
                    question_id=f"error_q_{len(question_metrics)}",
                    question_text=clarification_question,
                    target_args=[(error_result.tool_name, param) for param in error_result.error.split()]
                )
                
                # Update clarification counts
                question_generator.update_arg_clarification_counts(error_q)
                
                # Store question metrics
                question_metrics.append(error_q.to_dict())
                
                # Try to update tool calls based on the user's response
                tool_calls = question_generator.process_user_response(
                    question=error_q,
                    user_response=user_response,
                    tool_calls=updated_tool_calls
                )
                
                # Try executing the updated tool calls
                logger.info("Executing updated tool calls after error")
                conversation.append({
                    "role": "agent",
                    "message": f"Executing the updated actions: {[tc.tool_name for tc in tool_calls]}",
                    "type": "execution_retry"
                })
                
                execution_results = tool_executor.execute_tool_calls(tool_calls)
                all_succeeded = all(result.success for result in execution_results)
                
                if all_succeeded:
                    conversation.append({
                        "role": "agent",
                        "message": "All actions executed successfully after clarification.",
                        "type": "execution_result"
                    })
                else:
                    error_result = next((result for result in execution_results if not result.success), None)
                    error_message = f"Error still persists: {error_result.tool_name}: {error_result.message}"
                    conversation.append({
                        "role": "agent",
                        "message": error_message,
                        "type": "execution_error"
                    })
            else:
                # No clarification question generated
                conversation.append({
                    "role": "agent",
                    "message": error_message,
                    "type": "execution_error"
                })
    
    # Prepare simulation result
    result = {
        "simulation_id": str(uuid.uuid4()),
        "user_query": user_query,
        "initial_tool_calls": [tc.to_dict() for tc in initial_tool_calls],
        "final_tool_calls": [tc.to_dict() for tc in tool_calls],
        "execution_results": [result.to_dict() for result in execution_results],
        "conversation": conversation,
        "questions": question_metrics,
        "question_history": question_generator.question_history,
        "arg_clarification_counts": dict(question_generator.arg_clarification_counts),
        "total_clarifications": question_generator.total_clarifications,
        "turns": turn_count,
        "success": all_succeeded,
        "certainty_threshold": certainty_threshold,
        "final_certainty": overall_certainty
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
        print(visualizer.visualize_tool_calls([tc.to_execution_dict() for tc in tool_calls], "Final Tool Calls"))
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