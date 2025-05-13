#!/usr/bin/env python
"""
Script to calculate metrics for simulation results, comparing against ground truth data.
"""

import os
import sys
import glob
import json
import argparse
import logging
from typing import Dict, List, Any, Optional

# Add the project root to the Python path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the evaluation module from simulation
from simulation.evaluation import SimulationEvaluator, SimulationVisualizer
from utils.json_utils import load_json, save_json
from utils.logger import setup_logger

def get_matching_ground_truth_file(result_file: str, gt_dir: str) -> Optional[str]:
    """
    Find the matching ground truth file for a result file.
    
    Args:
        result_file: Path to the result file
        gt_dir: Directory containing ground truth files
        
    Returns:
        Path to the matching ground truth file, or None if not found
    """
    # Extract the base result filename without _RESULT suffix
    result_filename = os.path.basename(result_file)
    if "_RESULT" in result_filename:
        gt_filename = result_filename.replace("_RESULT", "")
    else:
        # If the filename doesn't follow the expected pattern, try to match by removing extension
        base_name = os.path.splitext(result_filename)[0]
        gt_filename = f"{base_name}.json"
    
    # Check if the ground truth file exists
    gt_file_path = os.path.join(gt_dir, gt_filename)
    if os.path.exists(gt_file_path):
        return gt_file_path
    
    # Try to find a file with a similar name
    for gt_file in glob.glob(os.path.join(gt_dir, "*.json")):
        if os.path.basename(gt_file).startswith(base_name.replace("_RESULT", "")):
            return gt_file
    
    return None

def calculate_metrics(result_file: str, gt_file: str) -> Dict[str, Any]:
    """
    Calculate metrics for a single result file against ground truth.
    
    Args:
        result_file: Path to the result file
        gt_file: Path to the ground truth file
        
    Returns:
        Updated result data with metrics
    """
    # Load result and ground truth data
    result_data = load_json(result_file)
    gt_data = load_json(gt_file)
    
    # Initialize the evaluator
    evaluator = SimulationEvaluator()
    
    # Calculate metrics
    metrics = evaluator.evaluate_simulation(gt_data, result_data)
    
    # Update the result data with metrics
    result_data["evaluation"] = metrics
    
    return result_data

def update_result_file(result_file: str, updated_data: Dict[str, Any]) -> bool:
    """
    Update a result file with new data.
    
    Args:
        result_file: Path to the result file
        updated_data: Updated data to save
        
    Returns:
        True if successful, False otherwise
    """
    return save_json(updated_data, result_file, pretty=True)

def print_metrics_summary(all_metrics: List[Dict[str, Any]], visualizer: SimulationVisualizer) -> None:
    """
    Print a summary of metrics for all evaluated files.
    
    Args:
        all_metrics: List of evaluation metrics
        visualizer: SimulationVisualizer instance for formatting
    """
    # Calculate summary statistics
    total_files = len(all_metrics)
    successful_simulations = sum(1 for m in all_metrics if m.get("success", False))
    
    # Calculate average metrics
    avg_validity_rate = sum(m.get("validity", {}).get("validity_rate", 0.0) for m in all_metrics) / total_files if total_files else 0.0
    avg_tool_match_rate = sum(m.get("correctness", {}).get("tool_match_rate", 0.0) for m in all_metrics) / total_files if total_files else 0.0
    avg_param_match_rate = sum(m.get("correctness", {}).get("param_match_rate", 0.0) for m in all_metrics) / total_files if total_files else 0.0
    avg_turns = sum(m.get("conversation", {}).get("total_turns", 0) for m in all_metrics) / total_files if total_files else 0.0
    avg_questions = sum(m.get("conversation", {}).get("clarification_questions", 0) for m in all_metrics) / total_files if total_files else 0.0
    
    # Print summary
    print("\n" + "="*80)
    print("METRICS SUMMARY")
    print("="*80)
    print(f"Total files evaluated: {total_files}")
    print(f"Successful simulations: {successful_simulations} ({successful_simulations/total_files*100:.2f}% if total_files > 0 else 'N/A')")
    print(f"Average validity rate: {avg_validity_rate:.4f}")
    print(f"Average tool match rate: {avg_tool_match_rate:.4f}")
    print(f"Average parameter match rate: {avg_param_match_rate:.4f}")
    print(f"Average conversation turns: {avg_turns:.2f}")
    print(f"Average clarification questions: {avg_questions:.2f}")
    print("="*80)
    
    # Save summary to file
    summary = {
        "total_files": total_files,
        "successful_simulations": successful_simulations,
        "success_rate": successful_simulations / total_files if total_files > 0 else 0.0,
        "average_validity_rate": avg_validity_rate,
        "average_tool_match_rate": avg_tool_match_rate,
        "average_param_match_rate": avg_param_match_rate,
        "average_turns": avg_turns,
        "average_questions": avg_questions
    }
    
    save_json(summary, "metrics_summary.json", pretty=True)
    print(f"Summary saved to metrics_summary.json")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Calculate metrics for simulation results")
    parser.add_argument("--results_dir", type=str, required=True, help="Directory containing result files")
    parser.add_argument("--gt_dir", type=str, required=True, help="Directory containing ground truth files")
    parser.add_argument("--verbose", action="store_true", help="Print verbose output")
    args = parser.parse_args()
    
    # Setup logging
    log_file = "metrics_calculation.log"
    logger = setup_logger(log_file=log_file)
    
    # Initialize visualizer
    visualizer = SimulationVisualizer()
    
    # Find all result files
    result_files = glob.glob(os.path.join(args.results_dir, "*.json"))
    
    if not result_files:
        logger.error(f"No result files found in {args.results_dir}")
        print(f"No result files found in {args.results_dir}")
        return
    
    # Process each result file
    all_metrics = []
    processed_files = 0
    
    for result_file in result_files:
        # Skip summary files
        if os.path.basename(result_file) in ["summary.json", "metrics_summary.json"]:
            continue
            
        logger.info(f"Processing {result_file}")
        
        # Find matching ground truth file
        gt_file = get_matching_ground_truth_file(result_file, args.gt_dir)
        
        if not gt_file:
            logger.warning(f"No matching ground truth file found for {result_file}")
            print(f"WARNING: No matching ground truth file found for {os.path.basename(result_file)}")
            continue
        
        try:
            # Calculate metrics
            updated_data = calculate_metrics(result_file, gt_file)
            
            # Update the result file
            if update_result_file(result_file, updated_data):
                logger.info(f"Updated {result_file} with metrics")
                processed_files += 1
                
                # Store metrics for summary
                if "evaluation" in updated_data:
                    all_metrics.append(updated_data["evaluation"])
                
                # Print metrics if verbose
                if args.verbose:
                    print("\n" + "="*80)
                    print(f"METRICS FOR {os.path.basename(result_file)}")
                    print(visualizer.visualize_metrics(updated_data["evaluation"]))
            else:
                logger.error(f"Failed to update {result_file}")
                
        except Exception as e:
            logger.exception(f"Error processing {result_file}")
            print(f"ERROR: Failed to process {os.path.basename(result_file)}: {str(e)}")
    
    # Print summary
    if all_metrics:
        print_metrics_summary(all_metrics, visualizer)
        print(f"Processed {processed_files} out of {len(result_files)} result files")
    else:
        print("No metrics were calculated. Check the log file for details.")
    
    print(f"Log file: {log_file}")

if __name__ == "__main__":
    main()