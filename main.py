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
from typing import Dict, List, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.tool_registry import ToolRegistry, Tool, Argument, ArgumentDomain, DomainType
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

def initialize_tool_registry(tool_configs: List[Dict[str, Any]]) -> ToolRegistry:
    """
    Initialize the tool registry from configurations.
    
    Args:
        tool_configs: List of tool configurations
        
    Returns:
        Initialized tool registry
    """
    registry = ToolRegistry()
    
    for tool_config in tool_configs:
        # Extract tool details
        name = tool_config["name"]
        description = tool_config["description"]
        arg_configs = tool_config.get("arguments", [])
        
        # Create arguments
        arguments = []
        for arg_config in arg_configs:
            # Extract argument details
            arg_name = arg_config["name"]
            arg_description = arg_config.get("description", "")
            required = arg_config.get("required", True)
            default = arg_config.get("default", None)
            
            # Create domain
            domain_config = arg_config.get("domain", {})
            domain_type_str = domain_config.get("type", "string")
            domain_type = DomainType(domain_type_str)
            domain_values = domain_config.get("values", None)
            importance = domain_config.get("importance", 0.5)
            data_dependent = domain_config.get("data_dependent", False)
            
            domain = ArgumentDomain(
                domain_type=domain_type,
                values=domain_values,
                importance=importance,
                description=arg_description,
                data_dependent=data_dependent
            )
            
            # Create argument
            argument = Argument(
                name=arg_name,
                domain=domain,
                description=arg_description,
                required=required,
                default=default
            )
            
            arguments.append(argument)
        
        # Create and register tool
        tool = Tool(
            name=name,
            description=description,
            arguments=arguments
        )
        
        registry.register_tool(tool)
    
    return registry

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

def run_simulation(
    simulation_data: Dict[str, Any],
    tool_registry: ToolRegistry,
    llm_provider: LLMProvider,
    question_config: Dict[str, Any],
    execution_config: Dict[str, Any],
    simulation_config: Dict[str, Any],
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Run a disambiguation simulation.
    
    Args:
        simulation_data: Simulation data
        tool_registry: Tool registry
        llm_provider: LLM provider
        question_config: Question generation configuration
        execution_config: Tool execution configuration
        simulation_config: Simulation configuration
        verbose: Whether to print verbose output
        
    Returns:
        Simulation results
    """
    # Initialize components
    uncertainty_calculator = UncertaintyCalculator(tool_registry)
    question_generator = QuestionGenerator(
        llm_provider=llm_provider,
        tool_registry=tool_registry,
        uncertainty_calculator=uncertainty_calculator
    )
    
    # Extract simulation data
    user_query = simulation_data.get("user_query", "")
    user_intent = simulation_data.get("user_intent", "")
    ground_truth = simulation_data
    
    # Update tool registry with data-dependent domains
    context = {
        k: v for k, v in simulation_data.items() 
        if k not in ["user_query", "user_intent", "ground_truth_tool_calls"]
    }
    tool_registry.update_domain_from_data(context)
    
    # Initialize mock API and tool executor
    mock_api = MockAPIClient(
        ground_truth=ground_truth,
        strict_validation=execution_config.get("strict_validation", False)
    )
    tool_executor = ToolExecutor(tool_registry, mock_api)
    
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
                from core.question_generation import ClarificationQuestion
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
    
    # # Prepare simulation result
    # result = {
    #     "simulation_id": str(uuid.uuid4()),
    #     "user_query": user_query,
    #     "initial_tool_calls": [tc.to_dict() for tc in tool_calls],
    #     "final_tool_calls": [tc.to_execution_dict() for tc in tool_calls],
    #     "execution_results": [result.to_dict() for result in execution_results],
    #     "conversation": conversation,
    #     "questions": question_metrics,
    #     "turns": turn_count,
    #     "success": all_succeeded,
    # }

    # Prepare simulation result
    result = {
        "simulation_id": str(uuid.uuid4()),
        "user_query": user_query,
        "initial_tool_calls": [tc.to_dict() for tc in initial_tool_calls ],
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
    
    # Add evaluation metrics
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
        print("\n" + "="*80)
        print("EVALUATION:")
        print(visualizer.visualize_metrics(evaluation_metrics))
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
    
    # Initialize components
    tool_registry = initialize_tool_registry(config.PDF_TOOLS_CONFIG)
    llm_provider = initialize_llm_provider(config.LLM_CONFIG)
    
    # Load simulation data
    data_loader = SimulationDataLoader(config.SIMULATION_CONFIG.get("data_dir", "simulation_data"))
    
    if args.data:
        # Run single simulation
        simulation_data = data_loader.load_simulation_data(args.data)
        
        # Run simulation
        result = run_simulation(
            simulation_data=simulation_data,
            tool_registry=tool_registry,
            llm_provider=llm_provider,
            question_config=config.QUESTION_CONFIG,
            execution_config=config.EXECUTION_CONFIG,
            simulation_config=config.SIMULATION_CONFIG,
            verbose=args.verbose
        )
        
        # Save result
        results_dir = config.SIMULATION_CONFIG.get("results_dir", "simulation_results")
        os.makedirs(results_dir, exist_ok=True)
        
        output_path = args.output if args.output else os.path.join(
            results_dir, f"result_{result['simulation_id']}.json"
        )
        
        # Add evaluation metrics before saving
        evaluator = SimulationEvaluator()
        metrics = evaluator.evaluate_simulation(simulation_data, result)
        result["evaluation"] = metrics
        
        save_json(result, output_path, pretty=True)
        logger.info(f"Saved result to {output_path}")
        
        # Print evaluation if verbose
        if args.verbose:
            visualizer = SimulationVisualizer()
            print("\n" + "="*80)
            print("EVALUATION:")
            print(visualizer.visualize_metrics(metrics))
            print("\n" + "="*80)
        
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
                tool_registry=tool_registry,
                llm_provider=llm_provider,
                question_config=config.QUESTION_CONFIG,
                execution_config=config.EXECUTION_CONFIG,
                simulation_config=config.SIMULATION_CONFIG,
                verbose=args.verbose
            )
            
            # Save result
            results_dir = config.SIMULATION_CONFIG.get("results_dir", "simulation_results")
            os.makedirs(results_dir, exist_ok=True)
            
            output_path = os.path.join(
                results_dir, f"result_{result['simulation_id']}.json"
            )
            
            save_json(result, output_path, pretty=True)
            logger.info(f"Saved result to {output_path}")
            
            # Store result for summary
            results.append(result)
        
        # Save summary if multiple simulations
        if len(results) > 1:
            summary = {
                "total_simulations": len(results),
                "successful_simulations": sum(1 for r in results if r.get("success", False)),
                "success_rate": sum(1 for r in results if r.get("success", False)) / len(results),
                "average_tool_match_rate": sum(r.get("evaluation", {}).get("tool_match_rate", 0.0) for r in results) / len(results),
                "tools_fully_matched_rate": sum(1 for r in results if r.get("evaluation", {}).get("tools_fully_matched_rate", 0.0) == 1.0) / len(results),
                "average_param_match_rate": sum(r.get("evaluation", {}).get("param_match_rate", 0.0) for r in results) / len(results),
                "average_turns": sum(r.get("turns", 0) for r in results) / len(results),
                "average_questions": sum(r.get("evaluation", {}).get("num_questions", 0) for r in results) / len(results),
                "simulation_ids": [r.get("simulation_id") for r in results]
            }
            
            summary_path = os.path.join(
                config.SIMULATION_CONFIG.get("results_dir", "simulation_results"),
                "summary.json"
            )
            
            save_json(summary, summary_path, pretty=True)
            logger.info(f"Saved summary to {summary_path}")
            
            # Print summary if verbose
            if args.verbose:
                print("\n" + "="*80)
                print("SUMMARY:")
                print(f"Total simulations: {summary['total_simulations']}")
                print(f"Successful simulations: {summary['successful_simulations']}")
                print(f"Success rate: {summary['success_rate']:.2f}")
                print(f"Average tool match rate: {summary['average_tool_match_rate']:.2f}")
                print(f"Tools fully matched rate: {summary['tools_fully_matched_rate']:.2f}")
                print(f"Average parameter match rate: {summary['average_param_match_rate']:.2f}")
                print(f"Average turns: {summary['average_turns']:.2f}")
                print(f"Average questions: {summary['average_questions']:.2f}")
                print("\n" + "="*80)

if __name__ == "__main__":
    main()