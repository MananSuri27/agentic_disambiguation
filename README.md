# Agentic Disambiguation System

This project implements a generalized agentic disambiguation system that can determine the appropriate tool to use based on user queries, handle uncertainties, and ask clarifying questions when needed. The system uses information theoretic principles to calculate expected value of perfect information (EVPI) and regret reduction when deciding whether to ask clarifying questions.

## Key Features

- **Domain-agnostic tool registry**: Register tools with their arguments and domains
- **Information-theoretic question selection**: Uses EVPI and regret reduction to select clarifying questions
- **LLM-based question generation**: Generates natural, targeted clarification questions
- **User simulation**: Simulates realistic user responses for testing
- **Mock API**: Validates tool calls against ground truth for evaluation
- **Comprehensive metrics**: Tracks and evaluates the disambiguation process

## Project Structure

```
agentic_disambiguation/
│
├── core/
│   ├── tool_registry.py         # Tool registration and management
│   ├── uncertainty.py           # Uncertainty calculation
│   ├── question_generation.py   # Generate and evaluate clarification questions
│   └── tool_executor.py         # Execute tool calls and handle errors
│
├── llm/
│   ├── provider.py              # Abstract LLM provider interface
│   ├── ollama.py                # Ollama implementation
│   └── simulation.py            # LLM-based user simulator
│
├── utils/
│   ├── logger.py                # Logging utilities
│   ├── json_utils.py            # JSON processing utilities
│   └── visualization.py         # Metrics visualization
│
├── simulation/
│   ├── mock_api.py              # Mock tool execution API
│   ├── evaluation.py            # Evaluation metrics
│   └── data_loader.py           # Load simulation data
│
├── main.py                      # Main entry point
├── config.py                    # Configuration
└── requirements.txt             # Dependencies
```

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Ollama (for LLM inference)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/agentic-disambiguation.git
   cd agentic-disambiguation
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Make sure Ollama is running:
   ```
   ollama serve
   ```

### Usage

1. Run a single simulation:
   ```
   python main.py --data simulation_data/sample_query.json --verbose
   ```

2. Run all simulations in the data directory:
   ```
   python main.py --verbose
   ```

3. Specify an output file:
   ```
   python main.py --data simulation_data/sample_query.json --output results/my_result.json
   ```

## How It Works

### The Disambiguation Process

1. **Initial Tool Call Generation**: The system analyzes the user query and generates initial tool calls with potential unknowns.

2. **Uncertainty Calculation**: For each argument, the system calculates certainty based on domain size.

3. **Question Generation**: The system generates candidate clarification questions targeting uncertain arguments.

4. **Question Evaluation**: Questions are evaluated using EVPI and regret reduction metrics.

5. **Question Selection**: The best question is selected using an Upper Confidence Bound (UCB) algorithm.

6. **User Response Processing**: User responses are processed to update tool calls.

7. **Tool Execution**: When certainty is high enough or no good questions remain, the tool calls are executed.

### Information-Theoretic Question Selection

The system uses two key metrics to evaluate questions:

- **Expected Value of Perfect Information (EVPI)**: The expected increase in certainty after asking a question.
- **Regret Reduction**: The expected decrease in regret (importance-weighted uncertainty) after asking a question.

These metrics are combined using a UCB formula that balances exploitation (asking questions with high expected value) and exploration (trying different questions to gather information):

```
UCB(q_k) = (EVPI(q_k) + ΔRegret(q_k)) + c * sqrt(log(N+1) / (n_k+1))
```

Where:
- `c` is the exploration constant
- `N` is the total number of questions asked so far
- `n_k` is the number of times arguments in question `q_k` have been asked about

## Configuration

The system can be configured through `config.py`, which includes settings for:

- LLM parameters
- Question generation and evaluation thresholds
- Tool execution behavior
- Simulation parameters

## Creating Simulation Data

Simulation data files should be JSON objects with the following structure:

```json
{
  "user_query": "Text of the user's query",
  "user_intent": "Description of the user's intent (for simulation)",
  "ground_truth_tool_calls": [
    {
      "tool_name": "name_of_tool",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ],
  "context_field1": "value1",
  "context_field2": "value2"
}
```

The `context_field` entries provide domain-specific context (like number of pages in a PDF).

## Adding New Tools

To add new tools, extend the `PDF_TOOLS_CONFIG` in `config.py` with additional tool definitions.

## License

This project is licensed under the MIT License - see the LICENSE file for details.