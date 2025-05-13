"""
Enhanced module for creating comprehensive hyperparameter visualizations.
Contains multiple visualization modes including:
1. Mean proportion of questions exceeding threshold
2. Percentage of simulations with at least one question exceeding threshold
3. Alternative format visualization showing all dimensions
"""

import os
import json
import glob
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any, Optional, Tuple
import logging
import seaborn as sns
from matplotlib.colors import LinearSegmentedColormap
from mpl_toolkits.mplot3d import Axes3D

logger = logging.getLogger(__name__)

def load_simulation_data(file_path: str) -> Dict[str, Any]:
    """Load a single simulation result file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return {}

def load_simulation_results(results_dir: str, file_pattern: str = "*.json") -> List[Dict[str, Any]]:
    """Load all simulation results from a directory."""
    pattern = os.path.join(results_dir, file_pattern)
    files = glob.glob(pattern)
    results = []
    
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                results.append(data)
                logger.debug(f"Loaded {file_path}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    
    logger.info(f"Loaded {len(results)} simulation files from {results_dir}")
    return results

def _recalculate_ucb(question_data: Dict[str, Any], c: float) -> float:
    """Recalculate UCB score with a different exploration constant."""
    evpi = question_data.get("metrics", {}).get("evpi", 0)
    regret_reduction = question_data.get("metrics", {}).get("regret_reduction", 0)
    original_ucb = question_data.get("metrics", {}).get("ucb_score", 0)
    
    # Assuming original c=1.0, extract the exploration term
    exploration_term = original_ucb - evpi - regret_reduction
    
    # Apply the new c value
    new_ucb = evpi + regret_reduction + c * exploration_term
    
    return new_ucb

def _calculate_threshold(base: float, alpha: float, step_idx: int) -> float:
    """Calculate the threshold for a given step with specified parameters."""
    return base + alpha * step_idx

def _get_questions_by_step(data: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
    """Group questions by step based on question_id patterns."""
    questions_by_step = {}
    step = 0
    
    # Process questions
    questions = data.get("questions", [])
    
    if not questions:
        return {}
        
    for q in questions:
        q_id = q.get("question_id", "")
        
        # Detect new step by looking for q_0 pattern
        if q_id.startswith("q_0"):
            step += 1
            questions_by_step[step] = []
            
        # Make sure we have a valid step
        if step > 0:
            if step not in questions_by_step:
                questions_by_step[step] = []
            questions_by_step[step].append(q)
    
    return questions_by_step

def _get_max_step(simulation_data: List[Dict[str, Any]]) -> int:
    """Get the maximum step number found in the data."""
    max_step = 0
    for data in simulation_data:
        steps = _get_questions_by_step(data)
        if steps:
            max_step = max(max_step, max(steps.keys()))
    return max_step

def create_multi_alpha_grid(
    simulation_data: List[Dict[str, Any]],
    c_values: List[float],
    base_values: List[float],
    alpha_values: List[float],
    max_steps: int = 4,
    output_path: Optional[str] = None,
    mode: str = "mean_proportion"
) -> None:
    """
    Create a comprehensive visualization showing parameter impact for all alpha values.
    
    Args:
        simulation_data: List of loaded simulation data dictionaries
        c_values: List of exploration constant values to test
        base_values: List of base threshold values to test
        alpha_values: List of alpha values to test
        max_steps: Maximum number of steps to visualize
        output_path: Path to save the visualization
        mode: Visualization mode ('mean_proportion' or 'has_question_percent')
    """
    if not simulation_data:
        logger.error("No simulation data provided")
        return
    
    # Get actual max step from data
    data_max_step = _get_max_step(simulation_data)
    max_steps = min(data_max_step, max_steps)
    
    if max_steps == 0:
        logger.error("No question steps found in data")
        return
    
    # Set up title and colorbar label based on mode
    if mode == "mean_proportion":
        main_title = 'Mean Proportion of Questions Exceeding Threshold'
        colorbar_label = 'Proportion of questions\nexceeding threshold'
    else:  # has_question_percent mode
        main_title = 'Percentage of Simulations with At Least One Question Exceeding Threshold'
        colorbar_label = '% of simulations with\nat least one question\nexceeding threshold'
    
    # Create a grid of subplots - each row is an alpha value, each column is a step
    fig, axes = plt.subplots(
        len(alpha_values), max_steps, 
        figsize=(5*max_steps, 4*len(alpha_values)),
        sharex=True, sharey=True,
        squeeze=False  # Always return 2D array of axes
    )
    
    # Create a colorbar axes
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    
    # Process each alpha value and step
    for alpha_idx, alpha in enumerate(alpha_values):
        for step_idx, step in enumerate(range(1, max_steps + 1)):
            ax = axes[alpha_idx, step_idx]
            
            # Create heatmap data for this alpha-step combination
            heatmap_data = np.zeros((len(c_values), len(base_values)))
            
            # Calculate values for each c-base combination
            for c_idx, c in enumerate(c_values):
                for base_idx, base in enumerate(base_values):
                    # Calculate dynamic threshold
                    threshold = _calculate_threshold(base, alpha, step - 1)
                    
                    if mode == "mean_proportion":
                        # Count questions exceeding threshold
                        questions_exceeding = 0
                        total_questions = 0
                        
                        # Process each simulation
                        for data in simulation_data:
                            questions_by_step = _get_questions_by_step(data)
                            
                            if step in questions_by_step:
                                step_questions = questions_by_step[step]
                                total_questions += len(step_questions)
                                
                                # Check each question
                                for q in step_questions:
                                    ucb = _recalculate_ucb(q, c)
                                    if ucb > threshold:
                                        questions_exceeding += 1
                        
                        # Calculate proportion
                        if total_questions > 0:
                            value = questions_exceeding / total_questions
                        else:
                            value = 0
                    
                    else:  # has_question_percent mode
                        # Count simulations with at least one question exceeding threshold
                        sims_with_questions = 0
                        total_sims_with_step = 0
                        
                        # Process each simulation
                        for data in simulation_data:
                            questions_by_step = _get_questions_by_step(data)
                            
                            if step in questions_by_step:
                                total_sims_with_step += 1
                                step_questions = questions_by_step[step]
                                
                                # Check if any question exceeds threshold
                                has_question_exceeding = False
                                for q in step_questions:
                                    ucb = _recalculate_ucb(q, c)
                                    if ucb > threshold:
                                        has_question_exceeding = True
                                        break
                                
                                if has_question_exceeding:
                                    sims_with_questions += 1
                        
                        # Calculate percentage
                        if total_sims_with_step > 0:
                            value = sims_with_questions / total_sims_with_step * 100
                        else:
                            value = 0
                    
                    heatmap_data[c_idx, base_idx] = value
            
            # Create heatmap - adjust vmax based on mode
            vmax = 1.0 if mode == "mean_proportion" else 100.0
            im = ax.imshow(heatmap_data, cmap='viridis', origin='lower', vmin=0, vmax=vmax, aspect='auto')
            
            # Add text annotations
            for c_idx in range(len(c_values)):
                for base_idx in range(len(base_values)):
                    value = heatmap_data[c_idx, base_idx]
                    
                    # Format value text based on mode
                    if mode == "mean_proportion":
                        value_text = f'{value:.2f}'
                    else:  # has_question_percent mode
                        value_text = f'{value:.0f}%'
                    
                    # Determine text color - adjust threshold based on mode
                    threshold = 0.5 if mode == "mean_proportion" else 50
                    text_color = 'white' if value > threshold else 'black'
                    
                    ax.text(base_idx, c_idx, value_text, 
                           ha='center', va='center', color=text_color, fontsize=8)
            
            # Set axes labels and ticks
            if step_idx == 0:  # First column
                ax.set_ylabel(f'α={alpha:.2f}\nC value')
                ax.set_yticks(range(len(c_values)))
                ax.set_yticklabels([f'{c:.1f}' for c in c_values])
            
            if alpha_idx == 0:  # First row
                ax.set_title(f'Step {step}')
            
            if alpha_idx == len(alpha_values) - 1:  # Last row
                ax.set_xlabel('Base threshold')
                ax.set_xticks(range(len(base_values)))
                ax.set_xticklabels([f'{b:.1f}' for b in base_values], rotation=45)
    
    # Add colorbar
    cbar = fig.colorbar(im, cax=cbar_ax)
    cbar.set_label(colorbar_label)
    
    # Add overall title
    plt.suptitle(f'Parameter Impact for All Alpha Values Across Steps\n{main_title}', 
                fontsize=20, y=0.98)
    
    # Adjust layout
    plt.tight_layout(rect=[0, 0, 0.9, 0.95])
    
    # Save or show
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved multi-alpha grid visualization to {output_path}")
    else:
        plt.show()

def create_alternative_visualization(
    simulation_data: List[Dict[str, Any]],
    c_values: List[float],
    base_values: List[float],
    alpha_values: List[float],
    max_steps: int = 4,
    output_path: Optional[str] = None
) -> None:
    """
    Create an alternative visualization showing all dimensions of the data.
    Uses a different format than heatmaps to display all hyperparameter relationships.
    
    Args:
        simulation_data: List of loaded simulation data dictionaries
        c_values: List of exploration constant values to test
        base_values: List of base threshold values to test
        alpha_values: List of alpha values to test
        max_steps: Maximum number of steps to visualize
        output_path: Path to save the visualization
    """
    if not simulation_data:
        logger.error("No simulation data provided")
        return
    
    # Get actual max step from data
    data_max_step = _get_max_step(simulation_data)
    max_steps = min(data_max_step, max_steps)
    
    if max_steps == 0:
        logger.error("No question steps found in data")
        return
    
    # We'll use a bubble chart with grid layout
    fig = plt.figure(figsize=(15, 12))
    
    # Create a grid of subplots - each row is a step, each column is an alpha value
    # This is the inverse of the previous visualization
    n_rows, n_cols = max_steps, len(alpha_values)
    
    # Calculate the data first - for all parameter combinations and metrics
    all_data = {}
    
    # First, gather all data values
    for step in range(1, max_steps + 1):
        all_data[step] = {}
        
        for alpha_idx, alpha in enumerate(alpha_values):
            all_data[step][alpha] = {}
            
            for c in c_values:
                all_data[step][alpha][c] = {}
                
                for base in base_values:
                    # Calculate dynamic threshold
                    threshold = _calculate_threshold(base, alpha, step - 1)
                    
                    # Calculate both metrics
                    # 1. Mean proportion of questions exceeding threshold
                    questions_exceeding = 0
                    total_questions = 0
                    
                    # 2. Percentage of simulations with at least one question
                    sims_with_questions = 0
                    total_sims_with_step = 0
                    
                    # Process each simulation
                    for data in simulation_data:
                        questions_by_step = _get_questions_by_step(data)
                        
                        if step in questions_by_step:
                            step_questions = questions_by_step[step]
                            total_questions += len(step_questions)
                            
                            # For second metric
                            total_sims_with_step += 1
                            has_question_exceeding = False
                            
                            # Check each question
                            for q in step_questions:
                                ucb = _recalculate_ucb(q, c)
                                if ucb > threshold:
                                    questions_exceeding += 1
                                    has_question_exceeding = True
                            
                            if has_question_exceeding:
                                sims_with_questions += 1
                    
                    # Calculate metrics
                    mean_proportion = questions_exceeding / total_questions if total_questions > 0 else 0
                    has_question_percent = sims_with_questions / total_sims_with_step * 100 if total_sims_with_step > 0 else 0
                    
                    # Store results
                    all_data[step][alpha][c][base] = {
                        "mean_proportion": mean_proportion,
                        "has_question_percent": has_question_percent
                    }

    # Create radar chart
    # We'll use step, alpha, c, base as the axes
    # And mean_proportion as the value
    
    # Create a custom colormap
    cmap = plt.cm.viridis
    
    # Create a subplot grid
    grid = plt.GridSpec(max_steps, len(alpha_values), wspace=0.4, hspace=0.3)
    
    # Find min/max values for consistent bubble sizing
    min_prop = 1.0
    max_prop = 0.0
    min_percent = 100.0
    max_percent = 0.0
    
    for step in all_data:
        for alpha in all_data[step]:
            for c in all_data[step][alpha]:
                for base in all_data[step][alpha][c]:
                    values = all_data[step][alpha][c][base]
                    
                    min_prop = min(min_prop, values["mean_proportion"])
                    max_prop = max(max_prop, values["mean_proportion"])
                    
                    min_percent = min(min_percent, values["has_question_percent"])
                    max_percent = max(max_percent, values["has_question_percent"])
    
    # Make sure we don't divide by zero
    if min_prop == max_prop:
        max_prop = min_prop + 0.1
    if min_percent == max_percent:
        max_percent = min_percent + 10
    
    # Create plots
    for step_idx, step in enumerate(range(1, max_steps + 1)):
        for alpha_idx, alpha in enumerate(alpha_values):
            # Create subplot
            ax = plt.subplot(grid[step_idx, alpha_idx])
            
            # For each c-base combination, plot a point
            for c_idx, c in enumerate(c_values):
                for base_idx, base in enumerate(base_values):
                    values = all_data[step][alpha][c][base]
                    
                    # Get metrics
                    mean_prop = values["mean_proportion"]
                    has_percent = values["has_question_percent"]
                    
                    # Normalize for bubble size and color
                    norm_prop = (mean_prop - min_prop) / (max_prop - min_prop)
                    norm_percent = (has_percent - min_percent) / (max_percent - min_percent)
                    
                    # Calculate bubble size - based on has_question_percent
                    # Min size 20, max size 500
                    size = 20 + 480 * norm_percent
                    
                    # Get color based on mean_proportion
                    color = cmap(norm_prop)
                    
                    # Plot bubble
                    ax.scatter(c, base, s=size, color=color, alpha=0.7, 
                              edgecolor='black', linewidth=1)
                    
                    # Add percentage text for larger bubbles
                    if size > 100:
                        ax.text(c, base, f"{has_percent:.0f}%", 
                               ha='center', va='center', fontsize=8, 
                               color='white' if norm_prop > 0.5 else 'black')
            
            # Set labels and title
            if step_idx == max_steps - 1:  # Bottom row
                ax.set_xlabel('C value')
            if alpha_idx == 0:  # First column
                ax.set_ylabel('Base threshold')
            
            # Add title
            ax.set_title(f'Step {step}, α={alpha:.2f}')
            
            # Set limits
            ax.set_xlim(min(c_values) - 0.1, max(c_values) + 0.1)
            ax.set_ylim(min(base_values) - 0.1, max(base_values) + 0.1)
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.5)
    
    # Add color bar for mean proportion
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=plt.gcf().get_axes())
    cbar.set_label('Mean proportion of questions exceeding threshold')
    
    # Add size legend
    # Create three example sizes
    sizes = [20, 250, 480]
    labels = [f"{min_percent:.0f}%", f"{(min_percent + max_percent)/2:.0f}%", f"{max_percent:.0f}%"]
    
    # Add a legend for bubble sizes
    legend_elements = []
    for i, (size, label) in enumerate(zip(sizes, labels)):
        legend_elements.append(plt.Line2D([0], [0], marker='o', color='w', 
                               label=label, markerfacecolor='gray',
                               markersize=np.sqrt(size/15)))
    
    # Place the legend
    fig.legend(handles=legend_elements, loc='lower right', 
              title='% of simulations with questions', 
              bbox_to_anchor=(0.95, 0.05))
    
    # Add overall title
    plt.suptitle('Comprehensive Hyperparameter Visualization\nBubble size = % of simulations with questions, Color = Mean question proportion', 
                fontsize=16)
    
    # Adjust layout
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    # Save or show
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Saved alternative visualization to {output_path}")
    else:
        plt.show()

def visualize_all(
    results_dir: str,
    c_values: List[float],
    base_values: List[float],
    alpha_values: List[float],
    output_dir: str,
    max_steps: int = 4
) -> None:
    """
    Create all three visualizations:
    1. Mean proportion of questions exceeding threshold
    2. Percentage of simulations with at least one question exceeding threshold
    3. Alternative visualization showing all dimensions
    
    Args:
        results_dir: Directory containing simulation results
        c_values: List of exploration constant values to test
        base_values: List of base threshold values to test
        alpha_values: List of alpha values to test
        output_dir: Directory to save visualizations
        max_steps: Maximum number of steps to visualize
    """
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)
    
    # Load simulation data
    simulation_data = load_simulation_results(results_dir)
    
    if not simulation_data:
        logger.error(f"No simulation data found in {results_dir}")
        return
    
    # 1. Mean proportion grid
    mean_output_path = os.path.join(output_dir, "mean_proportion_grid.png")
    create_multi_alpha_grid(
        simulation_data=simulation_data,
        c_values=c_values,
        base_values=base_values,
        alpha_values=alpha_values,
        max_steps=max_steps,
        output_path=mean_output_path,
        mode="mean_proportion"
    )
    
    # 2. Has question percentage grid
    percent_output_path = os.path.join(output_dir, "has_question_percent_grid.png")
    create_multi_alpha_grid(
        simulation_data=simulation_data,
        c_values=c_values,
        base_values=base_values,
        alpha_values=alpha_values,
        max_steps=max_steps,
        output_path=percent_output_path,
        mode="has_question_percent"
    )
    
    # 3. Alternative visualization
    alt_output_path = os.path.join(output_dir, "alternative_visualization.png")
    create_alternative_visualization(
        simulation_data=simulation_data,
        c_values=c_values,
        base_values=base_values,
        alpha_values=alpha_values,
        max_steps=max_steps,
        output_path=alt_output_path
    )
    
    logger.info(f"All visualizations created and saved to {output_dir}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create enhanced hyperparameter visualizations")
    parser.add_argument("--results_dir", required=True, 
                        help="Directory containing simulation results")
    parser.add_argument("--output_dir", default="hyperparam_analysis",
                        help="Output directory for visualizations")
    parser.add_argument("--c_values", type=float, nargs="+",
                        default=[0.5, 1.0, 1.5, 2.0],
                        help="C values to visualize")
    parser.add_argument("--base_values", type=float, nargs="+",
                        default=[1.0, 1.5, 1.75, 1.9],
                        help="Base threshold values to visualize")
    parser.add_argument("--alpha_values", type=float, nargs="+",
                        default=[0.05, 0.1, 0.15, 0.2, 0.25, 0.5],
                        help="Alpha values to visualize")
    parser.add_argument("--max_steps", type=int, default=4,
                        help="Maximum number of steps to visualize")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, 
                       format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Create all visualizations
    visualize_all(
        results_dir=args.results_dir,
        c_values=args.c_values,
        base_values=args.base_values,
        alpha_values=args.alpha_values,
        output_dir=args.output_dir,
        max_steps=args.max_steps
    )