"""
Clean, intuitive visualization utilities for analyzing hyperparameter effects in the 
agentic disambiguation system.
"""

import os
import json
import glob
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from typing import Dict, List, Any, Tuple, Optional
import logging
import seaborn as sns

logger = logging.getLogger(__name__)

class HyperparameterAnalyzer:
    """Clean, focused class for visualizing hyperparameter effects on question selection."""
    
    def __init__(self, results_dir: str = "simulation_results"):
        """
        Initialize a hyperparameter analyzer.
        
        Args:
            results_dir: Directory containing simulation result files
        """
        self.results_dir = results_dir
        self.simulation_data = []
        
    def load_simulation_results(self, file_pattern: str = "*.json") -> int:
        """Load simulation results from files."""
        pattern = os.path.join(self.results_dir, file_pattern)
        files = glob.glob(pattern)
        
        for file_path in files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    self.simulation_data.append(data)
                    logger.info(f"Loaded simulation file: {file_path}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")
        
        return len(self.simulation_data)
    
    def load_single_result(self, file_path: str) -> Dict[str, Any]:
        """Load a single simulation result file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.simulation_data = [data]
                logger.info(f"Loaded single file: {file_path}")
                return data
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return {}
    
    def _recalculate_ucb(self, question_data: Dict[str, Any], c: float) -> float:
        """Recalculate UCB score with a different exploration constant."""
        # Extract the components of the UCB score
        evpi = question_data.get("metrics", {}).get("evpi", 0)
        regret_reduction = question_data.get("metrics", {}).get("regret_reduction", 0)
        
        # The original UCB calculation is: evpi + regret_reduction + c * exploration_term
        # We can extract the exploration term from the original UCB score 
        original_ucb = question_data.get("metrics", {}).get("ucb_score", 0)
        
        # Assuming original c=1.0, we can extract the exploration term
        exploration_term = original_ucb - evpi - regret_reduction
        
        # Apply the new c value
        new_ucb = evpi + regret_reduction + c * exploration_term
        
        return new_ucb
    
    def _calculate_threshold(self, base: float, alpha: float, step: int) -> float:
        """Calculate the threshold for a given step with specified parameters."""
        return base + alpha * step
    
    def _get_questions_by_step(self, data: Dict[str, Any]) -> Dict[int, List[Dict[str, Any]]]:
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
    
    def _get_max_step(self) -> int:
        """Get the maximum step number found in the data."""
        max_step = 0
        for data in self.simulation_data:
            steps = self._get_questions_by_step(data)
            if steps:
                max_step = max(max_step, max(steps.keys()))
        return max_step
    
    def create_multi_step_grid(self, 
                             c_values: List[float],
                             base_values: List[float],
                             alpha_value: float,
                             output_path: Optional[str] = None) -> None:
        """
        Create a clear grid visualization showing parameter impact across all steps.
        
        This visualization shows how c and base threshold impact the proportion of
        questions that exceed the dynamic threshold at each step in the clarification process.
        
        Args:
            c_values: List of exploration constant values to test
            base_values: List of base threshold values to test
            alpha_value: Alpha value to use
            output_path: Path to save the visualization
        """
        if not self.simulation_data:
            logger.error("No simulation data loaded")
            return
        
        # Get maximum step
        max_step = self._get_max_step()
        
        if max_step == 0:
            logger.error("No question steps found in data")
            return
        
        # Create a grid of heatmaps - one per step
        # Add one to max_step since steps are 1-indexed
        n_steps = min(max_step, 4)  # Limit to 4 steps for readability
        
        # Set up the figure with subplots
        fig, axes = plt.subplots(1, n_steps, figsize=(5*n_steps, 6), sharey=True)
        
        # Handle case with only one step
        if n_steps == 1:
            axes = [axes]
        
        # Process each step
        for step_idx, step in enumerate(range(1, n_steps+1)):
            ax = axes[step_idx]
            
            # Create a heatmap matrix for this step
            heatmap_data = np.zeros((len(c_values), len(base_values)))
            
            # Calculate proportion values for each parameter combination
            for c_idx, c in enumerate(c_values):
                for base_idx, base in enumerate(base_values):
                    # Calculate dynamic threshold for this step and parameters
                    threshold = self._calculate_threshold(base, alpha_value, step-1)
                    
                    # Count questions exceeding threshold
                    questions_exceeding = 0
                    total_questions = 0
                    
                    # Process each simulation
                    for data in self.simulation_data:
                        questions_by_step = self._get_questions_by_step(data)
                        
                        if step in questions_by_step:
                            step_questions = questions_by_step[step]
                            total_questions += len(step_questions)
                            
                            # Check each question
                            for q in step_questions:
                                ucb = self._recalculate_ucb(q, c)
                                if ucb > threshold:
                                    questions_exceeding += 1
                    
                    # Calculate proportion
                    if total_questions > 0:
                        proportion = questions_exceeding / total_questions
                    else:
                        proportion = 0
                    
                    heatmap_data[c_idx, base_idx] = proportion
            
            # Create heatmap
            im = ax.imshow(heatmap_data, cmap='viridis', origin='lower', vmin=0, vmax=1, 
                          aspect='auto')
            
            # Add text annotations
            for c_idx in range(len(c_values)):
                for base_idx in range(len(base_values)):
                    value = heatmap_data[c_idx, base_idx]
                    text_color = 'white' if value > 0.5 else 'black'
                    ax.text(base_idx, c_idx, f'{value:.2f}', 
                           ha='center', va='center', color=text_color, fontsize=9)
            
            # Set axes labels and ticks
            ax.set_xticks(range(len(base_values)))
            ax.set_xticklabels([f'{b:.2f}' for b in base_values], rotation=45)
            
            if step_idx == 0:  # Only label y-axis on first subplot
                ax.set_yticks(range(len(c_values)))
                ax.set_yticklabels([f'{c:.2f}' for c in c_values])
                ax.set_ylabel('Exploration constant (c)')
            
            ax.set_xlabel('Base threshold')
            ax.set_title(f'Step {step}')
        
        # Add colorbar
        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        cbar = fig.colorbar(im, cax=cbar_ax)
        cbar.set_label('Proportion of questions\nexceeding threshold')
        
        # Add overall title
        plt.suptitle(f'Parameter Impact Across Steps (alpha={alpha_value})', 
                    fontsize=16, y=0.98)
        
        # Adjust layout
        plt.tight_layout(rect=[0, 0, 0.9, 0.95])
        
        # Save or show
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()
    
    def create_step_line_comparison(self,
                                  parameter_type: str,
                                  parameter_values: List[float],
                                  fixed_c: float = 1.0,
                                  fixed_base: float = 0.1,
                                  fixed_alpha: float = 0.05,
                                  output_path: Optional[str] = None) -> None:
        """
        Create line charts showing how a parameter affects selection across steps.
        
        Args:
            parameter_type: Type of parameter to vary ('c', 'base', or 'alpha')
            parameter_values: List of values to test for the chosen parameter
            fixed_c: Fixed value for c when varying other parameters
            fixed_base: Fixed value for base threshold when varying other parameters
            fixed_alpha: Fixed value for alpha when varying other parameters
            output_path: Path to save the visualization
        """
        if not self.simulation_data:
            logger.error("No simulation data loaded")
            return
        
        # Get maximum step
        max_step = self._get_max_step()
        
        if max_step == 0:
            logger.error("No question steps found in data")
            return
        
        # Set up the figure
        plt.figure(figsize=(10, 6))
        
        # Set color map
        n_values = len(parameter_values)
        colors = plt.cm.viridis(np.linspace(0, 1, n_values))
        
        # Process each parameter value
        for idx, param_value in enumerate(parameter_values):
            # Set the parameters based on which one we're varying
            if parameter_type == 'c':
                c = param_value
                base = fixed_base
                alpha = fixed_alpha
                label = f'c = {param_value:.2f}'
            elif parameter_type == 'base':
                c = fixed_c
                base = param_value
                alpha = fixed_alpha
                label = f'base = {param_value:.2f}'
            elif parameter_type == 'alpha':
                c = fixed_c
                base = fixed_base
                alpha = param_value
                label = f'alpha = {param_value:.2f}'
            else:
                logger.error(f"Unknown parameter type: {parameter_type}")
                return
            
            # Calculate proportion values for each step
            step_values = []
            
            for step in range(1, max_step + 1):
                # Calculate dynamic threshold for this step and parameters
                threshold = self._calculate_threshold(base, alpha, step-1)
                
                # Count questions exceeding threshold
                questions_exceeding = 0
                total_questions = 0
                
                # Process each simulation
                for data in self.simulation_data:
                    questions_by_step = self._get_questions_by_step(data)
                    
                    if step in questions_by_step:
                        step_questions = questions_by_step[step]
                        total_questions += len(step_questions)
                        
                        # Check each question
                        for q in step_questions:
                            ucb = self._recalculate_ucb(q, c)
                            if ucb > threshold:
                                questions_exceeding += 1
                
                # Calculate proportion
                if total_questions > 0:
                    proportion = questions_exceeding / total_questions
                else:
                    proportion = 0
                
                step_values.append(proportion)
            
            # Plot line for this parameter value
            plt.plot(range(1, len(step_values) + 1), step_values, 'o-', 
                    color=colors[idx], linewidth=2, markersize=8, label=label)
            
            # Add value annotations
            for step, value in enumerate(step_values, 1):
                plt.annotate(f'{value:.2f}', (step, value),
                           xytext=(0, 10), textcoords='offset points',
                           ha='center', va='bottom', fontsize=8)
        
        # Set axes labels and title
        plt.xlabel('Clarification Step')
        plt.ylabel('Proportion of questions exceeding threshold')
        
        if parameter_type == 'c':
            plt.title(f'Impact of Exploration Constant (c) Across Steps\n' +
                     f'base={fixed_base}, alpha={fixed_alpha}')
        elif parameter_type == 'base':
            plt.title(f'Impact of Base Threshold Across Steps\n' +
                     f'c={fixed_c}, alpha={fixed_alpha}')
        elif parameter_type == 'alpha':
            plt.title(f'Impact of Alpha Across Steps\n' +
                     f'c={fixed_c}, base={fixed_base}')
        
        # Set x-ticks to integer steps
        plt.xticks(range(1, max_step + 1))
        
        # Set y-axis limits
        plt.ylim(0, 1.05)
        
        # Add reference line at 0.5
        plt.axhline(y=0.5, color='red', linestyle='--', alpha=0.7,
                   label='50% threshold')
        
        # Add grid
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Add legend
        plt.legend(loc='best')
        
        # Adjust layout
        plt.tight_layout()
        
        # Save or show
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()

    def create_ucb_distribution_plot(self,
                                   c_values: List[float],
                                   base_threshold: float,
                                   alpha_value: float,
                                   step: int = 1,
                                   output_path: Optional[str] = None) -> None:
        """
        Create a clear visualization of UCB score distributions for different c values.
        
        Args:
            c_values: List of c values to compare
            base_threshold: Base threshold value
            alpha_value: Alpha value
            step: Clarification step to analyze (default: 1)
            output_path: Path to save the visualization
        """
        if not self.simulation_data:
            logger.error("No simulation data loaded")
            return
        
        # Find data with questions for the requested step
        questions = []
        for data in self.simulation_data:
            questions_by_step = self._get_questions_by_step(data)
            if step in questions_by_step and questions_by_step[step]:
                questions = questions_by_step[step]
                break
        
        if not questions:
            logger.error(f"No questions found for step {step}")
            return
        
        # Calculate dynamic threshold
        threshold = self._calculate_threshold(base_threshold, alpha_value, step-1)
        
        # Set up the figure with subplots - one per c value
        fig, axes = plt.subplots(1, len(c_values), figsize=(5*len(c_values), 6), sharey=True)
        
        # Handle case with only one c value
        if len(c_values) == 1:
            axes = [axes]
        
        # Process each c value
        for idx, c in enumerate(c_values):
            ax = axes[idx]
            
            # Calculate UCB scores for this c value
            ucb_scores = [self._recalculate_ucb(q, c) for q in questions]
            
            # Determine colors based on threshold
            colors = ['green' if score > threshold else 'red' for score in ucb_scores]
            
            # Create bar chart
            bars = ax.bar(range(len(ucb_scores)), ucb_scores, color=colors)
            
            # Add value annotations
            for j, score in enumerate(ucb_scores):
                ax.text(j, score + 0.05, f'{score:.2f}', ha='center')
            
            # Add threshold line
            ax.axhline(y=threshold, color='black', linestyle='--',
                      label=f'Threshold = {threshold:.2f}')
            
            # Set labels and title
            ax.set_xlabel('Question Index')
            if idx == 0:
                ax.set_ylabel('UCB Score')
            ax.set_title(f'c = {c:.2f}')
            
            # Set x-ticks
            ax.set_xticks(range(len(ucb_scores)))
            ax.set_xticklabels([f'Q{j+1}' for j in range(len(ucb_scores))])
            
            # Set y limits with padding
            max_score = max(ucb_scores) if ucb_scores else 1
            ax.set_ylim(0, max_score * 1.2)
            
            # Add grid
            ax.grid(True, linestyle='--', alpha=0.3)
            
            # Add legend
            ax.legend()
        
        # Add overall title
        plt.suptitle(f'UCB Score Distribution (Step {step})\n' +
                    f'base={base_threshold}, alpha={alpha_value}', fontsize=16)
        
        # Adjust layout
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        
        # Save or show
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
        else:
            plt.show()
        
    def create_all_visualizations(self, 
                                output_dir: str = "hyperparameter_analysis",
                                c_values: List[float] = [0.5, 1.0, 1.5, 2.0, 3.0],
                                base_values: List[float] = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
                                alpha_values: List[float] = [0.01, 0.03, 0.05, 0.08, 0.1]) -> None:
        """
        Create all visualizations with default parameters and save to output directory.
        
        Args:
            output_dir: Directory to save visualizations
            c_values: List of c values to test
            base_values: List of base threshold values to test
            alpha_values: List of alpha values to test
        """
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # 1. Create multi-step grids for each alpha value
        for alpha in alpha_values:
            alpha_str = f"{alpha:.2f}".replace(".", "_")
            output_path = os.path.join(output_dir, f"grid_alpha_{alpha_str}.png")
            self.create_multi_step_grid(c_values, base_values, alpha, output_path)
        
        # 2. Create step line comparisons for each parameter type
        # For c
        c_output_path = os.path.join(output_dir, "c_impact_across_steps.png")
        self.create_step_line_comparison('c', c_values, output_path=c_output_path)
        
        # For base
        base_output_path = os.path.join(output_dir, "base_impact_across_steps.png")
        self.create_step_line_comparison('base', base_values, output_path=base_output_path)
        
        # For alpha
        alpha_output_path = os.path.join(output_dir, "alpha_impact_across_steps.png")
        self.create_step_line_comparison('alpha', alpha_values, output_path=alpha_output_path)
        
        # 3. Create UCB distribution plots for steps 1-3
        max_step = min(self._get_max_step(), 3)
        for step in range(1, max_step + 1):
            ucb_output_path = os.path.join(output_dir, f"ucb_distribution_step_{step}.png")
            self.create_ucb_distribution_plot(c_values[:3], 0.1, 0.05, step, ucb_output_path)
            
        logger.info(f"All visualizations created and saved to {output_dir}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean hyperparameter visualization tool")
    parser.add_argument("--results_dir", type=str, default="simulation_results",
                      help="Directory containing simulation results")
    parser.add_argument("--output_dir", type=str, default="hyperparameter_analysis",
                      help="Directory to save visualization outputs")
    parser.add_argument("--file", type=str, help="Specific result file to analyze")
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(level=logging.INFO,
                       format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Create analyzer
    analyzer = HyperparameterAnalyzer(args.results_dir)
    
    # Load data
    if args.file:
        analyzer.load_single_result(args.file)
    else:
        num_files = analyzer.load_simulation_results()
        logger.info(f"Loaded {num_files} files")
    
    # Create all visualizations
    analyzer.create_all_visualizations(args.output_dir)