import os
import json
import glob
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patheffects as path_effects
import seaborn as sns
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from matplotlib.ticker import MaxNLocator
import math


class ResultsVisualizer:
    """Class for visualizing simulation results from the agentic disambiguation system."""
    
    def __init__(self, results_dir: str):
        """
        Initialize a results visualizer.
        
        Args:
            results_dir: Directory containing simulation result files
        """
        self.results_dir = results_dir
        self.results = []
        self.load_results()
        
        # Set up color palette
        self.colors = {
            'evpi': '#1f77b4',  # blue
            'regret_reduction': '#ff7f0e',  # orange
            'ucb_score': '#2ca02c',  # green
            'threshold': '#d62728',  # red
            'certainty': '#9467bd',  # purple
            'certainty_threshold': '#8c564b',  # brown
        }
        
        # Use Seaborn styling
        sns.set_style("whitegrid")
        
    def load_results(self) -> None:
        """Load all result files from the results directory."""
        # Find all JSON files in the results directory
        result_files = glob.glob(os.path.join(self.results_dir, "*.json"))
        
        for file_path in result_files:
            try:
                with open(file_path, 'r') as f:
                    result = json.load(f)
                    self.results.append(result)
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                
        print(f"Loaded {len(self.results)} simulation results")
    
    def process_question_history(self) -> Tuple[Dict, List[Dict]]:
        """
        Process question history data from all results.
        
        Returns:
            Tuple of (metrics_by_turn, all_question_data)
        """
        all_question_data = []
        metrics_by_turn = defaultdict(lambda: defaultdict(list))
        
        for result in self.results:
            history = result.get("question_history", [])
            
            # Group questions by turn - assuming q_0 resets each turn
            turn_idx = 0
            last_q_id = None
            
            for q_data in history:
                q_id = q_data.get("question_id", "")
                
                # When we see q_0 again, we're at a new turn
                if q_id.startswith("q_0") and last_q_id is not None and not last_q_id.startswith("q_0"):
                    turn_idx += 1
                
                # Store metrics for this turn
                metrics = q_data.get("metrics", {})
                metrics_by_turn[turn_idx]["evpi"].append(metrics.get("evpi", 0))
                metrics_by_turn[turn_idx]["regret_reduction"].append(metrics.get("regret_reduction", 0))
                metrics_by_turn[turn_idx]["ucb_score"].append(metrics.get("ucb_score", 0))
                metrics_by_turn[turn_idx]["certainty"].append(q_data.get("overall_certainty", 0))
                
                # Store the question data with its turn
                q_data["turn"] = turn_idx
                all_question_data.append(q_data)
                
                last_q_id = q_id
                
        return metrics_by_turn, all_question_data
    
    def calculate_threshold(self, turn: int, total_clarifications: int, base_threshold: float = 1.5, alpha: float = 0.25) -> float:
        """
        Calculate dynamic threshold based on number of clarification questions asked.
        
        Args:
            turn: Turn number (not used directly)
            total_clarifications: Total number of clarification questions asked
            base_threshold: Base threshold value
            alpha: Threshold increase factor
            
        Returns:
            Dynamic threshold value
        """
        # Formula from UncertaintyCalculator.compute_dynamic_threshold
        # tau = tau_0 * (1.0 + alpha * N)
        return base_threshold + alpha * total_clarifications
    
    def visualize_metrics_over_turns(self, save_path: Optional[str] = None) -> None:
        """
        Create an enhanced visualization of metrics evolving over turns.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        metrics_by_turn, all_questions = self.process_question_history()
        
        if not metrics_by_turn:
            print("No metrics data available for visualization")
            return
        
        # Create figure with custom style
        plt.figure(figsize=(14, 10))
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # Get total clarifications per turn
        total_clarifications_by_turn = {}
        current_total = 0
        
        for turn in sorted(metrics_by_turn.keys()):
            # Each turn represents one clarification question asked
            current_total += 1
            total_clarifications_by_turn[turn] = current_total
        
        max_turn = max(metrics_by_turn.keys())
        turns = list(range(max_turn + 1))
        
        # Calculate average, min, max for each metric per turn
        avg_metrics = {
            'evpi': [],
            'regret_reduction': [],
            'ucb_score': [],
            'certainty': []
        }
        
        min_metrics = {
            'evpi': [],
            'regret_reduction': [],
            'ucb_score': [],
            'certainty': []
        }
        
        max_metrics = {
            'evpi': [],
            'regret_reduction': [],
            'ucb_score': [],
            'certainty': []
        }
        
        # For each turn, calculate the metrics
        for turn in turns:
            for metric in avg_metrics.keys():
                values = metrics_by_turn[turn][metric]
                if values:
                    avg_metrics[metric].append(np.mean(values))
                    min_metrics[metric].append(np.min(values))
                    max_metrics[metric].append(np.max(values))
                else:
                    avg_metrics[metric].append(0)
                    min_metrics[metric].append(0)
                    max_metrics[metric].append(0)
        
        # Calculate threshold for each turn based on total clarifications
        thresholds = [self.calculate_threshold(t, total_clarifications_by_turn.get(t, 0)) for t in turns]
        
        # Create a custom colormap for the uncertainty background
        cmap = plt.cm.get_cmap('Blues_r')
        
        # Create a custom background to represent uncertainty
        for t in range(len(turns)-1):
            certainty = avg_metrics['certainty'][t]
            # Inverse of certainty = uncertainty
            uncertainty = 1.0 - certainty
            # Use uncertainty to determine color intensity (fading as certainty increases)
            color = cmap(uncertainty * 0.7)  # Scale to ensure visibility
            plt.axvspan(turns[t], turns[t+1], color=color, alpha=0.3)
        
        # Determine y-axis scale
        y_max = max(
            max(max_metrics['evpi']), 
            max(max_metrics['regret_reduction']), 
            max(max_metrics['ucb_score']), 
            max(thresholds)
        ) * 1.1  # Add 10% padding
        
        # Plot data with enhanced styling
        for metric in ['evpi', 'regret_reduction', 'ucb_score']:
            # Plot average line
            plt.plot(turns, avg_metrics[metric], marker='o', 
                    label=f'Average {metric.replace("_", " ").title()}',
                    color=self.colors[metric], linewidth=3, markersize=8)
            
            # Plot min/max range
            plt.fill_between(turns, min_metrics[metric], max_metrics[metric],
                            alpha=0.2, color=self.colors[metric], label=f'Min/Max {metric.replace("_", " ").title()}')
        
        # Plot threshold line with annotation
        threshold_line = plt.plot(turns, thresholds, '--', color=self.colors['threshold'], 
                                linewidth=3, label='Dynamic Threshold')
        
        # Annotate threshold formula
        formula = r"$\tau = \tau_0 \cdot (1 + \alpha \cdot N)$"
        plt.annotate(formula, xy=(0.02, 0.97), xycoords='axes fraction',
                    fontsize=12, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
        
        # Add annotations for threshold crossings
        for t in turns:
            if max_metrics['ucb_score'][t] >= thresholds[t]:
                # Highlight crossings with star
                plt.scatter([t], [max_metrics['ucb_score'][t]], s=200,
                           marker='*', color='gold', edgecolor='black', zorder=10,
                           label='Threshold Crossed' if t == turns[0] else "")
                
                # Add annotation for the first few crossings
                if t <= 2:  # Limit annotations to avoid clutter
                    plt.annotate(f"Question Selected\nUCB: {max_metrics['ucb_score'][t]:.2f}\nThreshold: {thresholds[t]:.2f}",
                                xy=(t, max_metrics['ucb_score'][t]), xytext=(t+0.2, max_metrics['ucb_score'][t]*0.8),
                                arrowprops=dict(facecolor='black', shrink=0.05, width=1.5, headwidth=8),
                                fontsize=10, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8))
        
        # Show certainty as an inverse-scaled marker size on the same plot
        certainties = avg_metrics['certainty']
        # Scale marker sizes: larger = more uncertain
        marker_sizes = [1000 * (1.0 - c + 0.1) for c in certainties]  # Add 0.1 to ensure visibility for high certainty
        
        # Scatter plot to show certainty
        scatter = plt.scatter(turns, [y_max * 0.05] * len(turns), s=marker_sizes, 
                             c=certainties, cmap='RdYlGn', alpha=0.7, 
                             edgecolors='black', linewidths=1, zorder=5)
        
        # Add colorbar for certainty
        cbar = plt.colorbar(scatter, orientation='vertical', pad=0.01, fraction=0.05)
        cbar.set_label('Certainty Level', fontsize=12)
        
        # Add text labels for certainty
        for i, c in enumerate(certainties):
            if i % 2 == 0:  # Label every other point to avoid clutter
                plt.annotate(f"{c:.2f}", xy=(turns[i], y_max * 0.05),
                            xytext=(turns[i], y_max * 0.12),
                            fontsize=9, ha='center',
                            arrowprops=dict(arrowstyle='->', lw=1))
        
        # Additional UI enhancements
        plt.title('Metrics Evolution & Uncertainty Analysis', fontsize=18, fontweight='bold', pad=20)
        plt.xlabel('Turn Number', fontsize=14, fontweight='bold')
        plt.ylabel('Metric Value', fontsize=14, fontweight='bold')
        
        # Create a legend with custom grouping
        from matplotlib.lines import Line2D
        legend_elements = [
            # Metrics
            Line2D([0], [0], color=self.colors['evpi'], lw=3, marker='o', markersize=8, label='Avg EVPI'),
            Line2D([0], [0], color=self.colors['regret_reduction'], lw=3, marker='o', markersize=8, label='Avg Regret Reduction'),
            Line2D([0], [0], color=self.colors['ucb_score'], lw=3, marker='o', markersize=8, label='Avg UCB Score'),
            # Threshold
            Line2D([0], [0], color=self.colors['threshold'], lw=3, linestyle='--', label='Dynamic Threshold'),
            # Threshold crossing
            Line2D([0], [0], marker='*', color='w', markerfacecolor='gold', markersize=15, 
                  markeredgecolor='black', label='Threshold Crossed'),
            # Certainty
            Line2D([0], [0], marker='o', color='w', markerfacecolor='green', markersize=10, 
                  markeredgecolor='black', label='Certainty (larger=less certain)')
        ]
        
        plt.legend(handles=legend_elements, loc='upper left', fontsize=12, framealpha=0.95)
        
        plt.xlim(-0.5, max_turn + 0.5)
        plt.ylim(0, y_max)
        
        # Use integer ticks for x-axis
        plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))
        
        # Add a descriptive subtitle
        plt.figtext(0.5, 0.01, 
                   "This visualization shows how question selection metrics evolve over conversation turns.\n"
                   "Background color intensity represents uncertainty (darker = more uncertain).\n"
                   "Circle size indicates certainty level (larger = less certain).", 
                   ha='center', fontsize=11, bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.8))
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.97])
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()
    
    def visualize_question_metrics(self, save_path: Optional[str] = None) -> None:
        """
        Create visualization of question metrics by type of argument targeted.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        _, all_questions = self.process_question_history()
        
        if not all_questions:
            print("No question data available for visualization")
            return
        
        # Group questions by their target arguments
        arg_metrics = defaultdict(lambda: defaultdict(list))
        
        for q in all_questions:
            target_args = q.get("target_args", [])
            metrics = q.get("metrics", {})
            
            for tool_arg in target_args:
                if len(tool_arg) == 2:
                    tool, arg = tool_arg
                    key = f"{tool}.{arg}"
                    
                    arg_metrics[key]["evpi"].append(metrics.get("evpi", 0))
                    arg_metrics[key]["regret_reduction"].append(metrics.get("regret_reduction", 0))
                    arg_metrics[key]["ucb_score"].append(metrics.get("ucb_score", 0))
        
        # Create dataframe for visualization
        df_data = []
        
        for arg, metrics in arg_metrics.items():
            for metric_name, values in metrics.items():
                for value in values:
                    df_data.append({
                        "Argument": arg,
                        "Metric": metric_name,
                        "Value": value
                    })
        
        df = pd.DataFrame(df_data)
        
        # Create visualization
        plt.figure(figsize=(14, 8))
        
        # Use categorical plot from seaborn
        sns.boxplot(data=df, x="Argument", y="Value", hue="Metric")
        
        plt.title("Question Metrics by Target Argument", fontsize=16)
        plt.xlabel("Target Argument", fontsize=12)
        plt.ylabel("Metric Value", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.legend(title="Metric")
        plt.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()
    
    def visualize_arg_importance(self, save_path: Optional[str] = None) -> None:
        """
        Visualize the argument importance and clarification counts.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        # Get clarification counts from all results
        arg_counts = defaultdict(int)
        
        for result in self.results:
            counts = result.get("arg_clarification_counts", {})
            for arg, count in counts.items():
                arg_counts[arg] += count
        
        if not arg_counts:
            print("No argument clarification data available")
            return
        
        # Sort by count, descending
        sorted_args = sorted(arg_counts.items(), key=lambda x: x[1], reverse=True)
        args = [x[0] for x in sorted_args]
        counts = [x[1] for x in sorted_args]
        
        plt.figure(figsize=(12, 6))
        
        bars = plt.barh(args, counts, color=sns.color_palette("viridis", len(args)))
        
        plt.title("Argument Clarification Counts", fontsize=16)
        plt.xlabel("Number of Clarifications", fontsize=12)
        plt.ylabel("Argument", fontsize=12)
        
        # Add count labels to bars
        for i, v in enumerate(counts):
            plt.text(v + 0.1, i, str(v), va='center')
        
        plt.grid(True, axis='x', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()
    
    def visualize_success_metrics(self, save_path: Optional[str] = None) -> None:
        """
        Visualize success metrics across all simulations.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        if not self.results:
            print("No results available for visualization")
            return
        
        data = []
        
        for result in self.results:
            eval_data = result.get("evaluation", {})
            
            # Extract metrics
            metrics = {
                "Validity Rate": eval_data.get("validity", {}).get("validity_rate", 0),
                "Tool Match Rate": eval_data.get("correctness", {}).get("tool_match_rate", 0),
                "Parameter Match Rate": eval_data.get("correctness", {}).get("param_match_rate", 0),
                "Success": 1 if result.get("success", False) else 0
            }
            
            # Add to data list
            data.append(metrics)
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Create visualization
        plt.figure(figsize=(10, 6))
        
        # Create a bar chart of average success metrics
        avg_metrics = df.mean()
        bars = plt.bar(avg_metrics.index, avg_metrics.values, 
                      color=sns.color_palette("viridis", len(avg_metrics)))
        
        plt.title("Average Success Metrics Across Simulations", fontsize=16)
        plt.ylabel("Rate (0-1)", fontsize=12)
        plt.ylim(0, 1.1)
        
        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                    f'{height:.2f}', ha='center', va='bottom')
        
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()
    
    def visualize_turns_vs_success(self, save_path: Optional[str] = None) -> None:
        """
        Visualize relationship between number of turns and success.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        if not self.results:
            print("No results available for visualization")
            return
        
        # Extract turns and success data
        turns_data = []
        success_data = []
        
        for result in self.results:
            turns = result.get("turns", 0)
            success = result.get("success", False)
            
            turns_data.append(turns)
            success_data.append(1 if success else 0)
        
        # Create scatterplot
        plt.figure(figsize=(10, 6))
        
        # Jitter the success values slightly to show overlapping points
        jittered_success = [s + np.random.normal(0, 0.05) for s in success_data]
        
        plt.scatter(turns_data, jittered_success, alpha=0.7, s=100, 
                   c=success_data, cmap='viridis')
        
        plt.title("Relationship Between Turns and Success", fontsize=16)
        plt.xlabel("Number of Turns", fontsize=12)
        plt.ylabel("Success (0=Failed, 1=Succeeded)", fontsize=12)
        plt.yticks([0, 1], ["Failed", "Succeeded"])
        plt.grid(True, linestyle='--', alpha=0.7)
        
        # Use integer ticks for x-axis
        ax = plt.gca()
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        
        # Add turn distribution as a histogram above the main plot
        divider = make_axes_locatable(ax)
        ax_hist = divider.append_axes("top", 1.2, pad=0.1, sharex=ax)
        ax_hist.hist(turns_data, bins=max(turns_data), color='skyblue', alpha=0.7)
        ax_hist.set_title("Distribution of Turns", fontsize=12)
        ax_hist.set_ylabel("Count", fontsize=10)
        ax_hist.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()
    
    def visualize_question_effectiveness(self, save_path: Optional[str] = None) -> None:
        """
        Visualize how questions affect certainty.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        certainty_changes = []
        
        for result in self.results:
            history = result.get("question_history", [])
            
            for i in range(1, len(history)):
                prev_certainty = history[i-1].get("overall_certainty", 0)
                curr_certainty = history[i].get("overall_certainty", 0)
                
                # Calculate change in certainty
                change = curr_certainty - prev_certainty
                
                # Get question details
                question = history[i-1].get("question_text", "")
                targets = history[i-1].get("target_args", [])
                
                if targets:
                    target_args = [f"{t[0]}.{t[1]}" for t in targets if len(t) == 2]
                    target_str = ", ".join(target_args)
                else:
                    target_str = "Unknown"
                
                # Only include if there's a question and targets
                if question and target_str != "Unknown":
                    certainty_changes.append({
                        "Question": question[:50] + "..." if len(question) > 50 else question,
                        "Target": target_str,
                        "Certainty Change": change
                    })
        
        if not certainty_changes:
            print("No question effectiveness data available")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(certainty_changes)
        
        # Group by target argument and calculate average certainty change
        grouped = df.groupby("Target")["Certainty Change"].agg(['mean', 'count']).reset_index()
        grouped = grouped.sort_values('mean', ascending=False)
        
        plt.figure(figsize=(12, 8))
        
        bars = plt.barh(grouped["Target"], grouped["mean"], 
                       color=sns.color_palette("viridis", len(grouped)))
        
        # Add count labels
        for i, (_, row) in enumerate(grouped.iterrows()):
            plt.text(max(0.001, row['mean'] + 0.01), i, f"n={int(row['count'])}", va='center')
        
        plt.title("Average Certainty Improvement by Target Argument", fontsize=16)
        plt.xlabel("Average Increase in Certainty", fontsize=12)
        plt.ylabel("Target Argument", fontsize=12)
        plt.grid(True, axis='x', linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()

            
    def visualize_certainty_progress(self, save_path: Optional[str] = None) -> None:
        """
        Visualize how certainty increases with each clarification question.
        
        Args:
            save_path: Path to save the visualization (optional)
        """
        if not self.results:
            print("No results available for visualization")
            return
        
        # Extract certainty progression from question history
        certainty_progressions = []
        
        for result in self.results:
            history = result.get("question_history", [])
            if not history:
                continue
                
            # Extract certainty values with their corresponding turn
            progression = []
            for i, item in enumerate(history):
                progression.append({
                    'turn': i,
                    'certainty': item.get('overall_certainty', 0),
                    'question': item.get('question_text', '')[:50] + '...' if len(item.get('question_text', '')) > 50 else item.get('question_text', '')
                })
            
            certainty_progressions.append(progression)
        
        if not certainty_progressions:
            print("No certainty progression data available")
            return
        
        # Create plot
        plt.figure(figsize=(14, 8))
        
        # Plot individual progressions
        for i, progression in enumerate(certainty_progressions):
            turns = [item['turn'] for item in progression]
            certainties = [item['certainty'] for item in progression]
            
            # Use a unique color for each simulation
            color = plt.cm.viridis(i / max(1, len(certainty_progressions) - 1))
            
            label = f"Simulation {i+1}" if i < 5 else None  # Limit labels to avoid clutter
            plt.plot(turns, certainties, 'o-', color=color, alpha=0.7, linewidth=2, label=label)
            
            # Annotate significant jumps in certainty
            for j in range(1, len(progression)):
                if progression[j]['certainty'] > progression[j-1]['certainty'] * 5:  # Significant increase
                    plt.annotate(progression[j-1]['question'],
                                xy=(progression[j-1]['turn'], progression[j-1]['certainty']),
                                xytext=(progression[j-1]['turn'] - 0.2, progression[j-1]['certainty'] * 3),
                                arrowprops=dict(arrowstyle="->", color='black', lw=1.5),
                                fontsize=8, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.8),
                                ha='right', va='center')
        
        # Calculate and plot the average progression
        max_turns = max([len(prog) for prog in certainty_progressions])
        avg_certainties = [0] * max_turns
        counts = [0] * max_turns
        
        for progression in certainty_progressions:
            for item in progression:
                turn = item['turn']
                if turn < max_turns:
                    avg_certainties[turn] += item['certainty']
                    counts[turn] += 1
        
        # Calculate averages
        for i in range(max_turns):
            if counts[i] > 0:
                avg_certainties[i] /= counts[i]
        
        # Plot average as a thicker line
        plt.plot(range(max_turns), avg_certainties, 'k-', linewidth=4, label='Average Certainty')
        
        # Add certainty threshold line
        certainty_threshold = 0.9  # From sample result
        plt.axhline(y=certainty_threshold, color='r', linestyle='--', 
                   label=f'Certainty Threshold ({certainty_threshold})')
        
        # Display logged scale for better visibility of small values
        plt.yscale('log')
        
        # Add a grid for better readability
        plt.grid(True, which="both", ls="-", alpha=0.2)
        
        # Add labels and title
        plt.title('Certainty Progression with Each Clarification Question', fontsize=16, fontweight='bold')
        plt.xlabel('Question Number', fontsize=14)
        plt.ylabel('Certainty (log scale)', fontsize=14)
        plt.legend(loc='best', fontsize=10)
        
        # Add text explanation
        plt.figtext(0.5, 0.01, 
                   "This visualization shows how certainty increases with each clarification question.\n"
                   "Significant jumps indicate questions that resolved key uncertainties.", 
                   ha='center', fontsize=11, bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="gray", alpha=0.8))
        
        plt.tight_layout(rect=[0, 0.03, 1, 0.97])
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {save_path}")
        else:
            plt.show()

    
    def visualize_all(self, output_dir: str) -> None:
        """
        Generate all visualizations and save them to the output directory.
        
        Args:
            output_dir: Directory to save visualization files
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate all visualizations
        self.visualize_metrics_over_turns(
            save_path=os.path.join(output_dir, "metrics_over_turns.png"))
        
        self.visualize_certainty_progress(
            save_path=os.path.join(output_dir, "certainty_progress.png"))
        
        self.visualize_question_metrics(
            save_path=os.path.join(output_dir, "question_metrics.png"))
        
        self.visualize_arg_importance(
            save_path=os.path.join(output_dir, "arg_importance.png"))
        
        self.visualize_success_metrics(
            save_path=os.path.join(output_dir, "success_metrics.png"))
        
        self.visualize_turns_vs_success(
            save_path=os.path.join(output_dir, "turns_vs_success.png"))
        
        self.visualize_question_effectiveness(
            save_path=os.path.join(output_dir, "question_effectiveness.png"))
        
        print(f"All visualizations saved to {output_dir}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Visualization for Agentic Disambiguation System")
    parser.add_argument("--results_dir", type=str, default="simulation_results", 
                        help="Directory containing simulation results")
    parser.add_argument("--output_dir", type=str, default="visualization_output", 
                        help="Directory to save visualization outputs")
    parser.add_argument("--visualize", type=str, default="all",
                        choices=["all", "metrics", "certainty", "questions", "importance", 
                                "success", "turns", "effectiveness"],
                        help="Specific visualization to generate")
    
    args = parser.parse_args()
    
    # Create visualizer
    visualizer = ResultsVisualizer(args.results_dir)
    
    # Generate visualizations
    if args.visualize == "all":
        visualizer.visualize_all(args.output_dir)
    elif args.visualize == "metrics":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_metrics_over_turns(
            save_path=os.path.join(args.output_dir, "metrics_over_turns.png"))
    elif args.visualize == "questions":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_question_metrics(
            save_path=os.path.join(args.output_dir, "question_metrics.png"))
    elif args.visualize == "importance":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_arg_importance(
            save_path=os.path.join(args.output_dir, "arg_importance.png"))
    elif args.visualize == "success":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_success_metrics(
            save_path=os.path.join(args.output_dir, "success_metrics.png"))
    elif args.visualize == "turns":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_turns_vs_success(
            save_path=os.path.join(args.output_dir, "turns_vs_success.png"))
    elif args.visualize == "effectiveness":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_question_effectiveness(
            save_path=os.path.join(args.output_dir, "question_effectiveness.png"))
    elif args.visualize == "certainty":
        os.makedirs(args.output_dir, exist_ok=True)
        visualizer.visualize_certainty_progress(save_path=os.path.join(args.output_dir, "certainty_progress.png"))    
            
    

if __name__ == "__main__":
    # Ensure the mpl_toolkits import is available for the turns_vs_success visualization
    try:
        from mpl_toolkits.axes_grid1 import make_axes_locatable
    except ImportError:
        def make_axes_locatable(ax):
            raise ImportError("mpl_toolkits.axes_grid1 is required for the turns visualization. "
                             "Please install it using 'pip install matplotlib'.")
    
    main()