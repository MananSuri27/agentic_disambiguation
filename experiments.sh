# python3 main.py

# python3 active_task.py

# python3 ask_before_plan.py

# python3 control_baseline.py

# python3 cot_disambiguate.py


#!/bin/bash

# Configuration
DISAMBIG_DIR="/fs/nexus-scratch/manans/disambiguation"
CORRUPTED_BENCH_DIR="${DISAMBIG_DIR}/corrupted_benchmark_final_v2"
AMB_DIR="${DISAMBIG_DIR}/data/bfcl_amb_v2"
NORM_DIR="${DISAMBIG_DIR}/data/bfcl_norm_v2"
OUTPUT_BASE_DIR="${DISAMBIG_DIR}/final_exp"
NUM_SAMPLES=100

# Base threshold and alpha settings
BASE_THRESHOLD=1.6
ALPHA=0.16

# Create timestamp for this run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Function to create output directory
create_output_dir() {
    local exp_name=$1
    local output_dir="${OUTPUT_BASE_DIR}/clarify_agent_${exp_name}_${TIMESTAMP}"
    mkdir -p "$output_dir"
    echo "$output_dir"
}

# Function to get random sample of files
get_random_samples() {
    local input_dir=$1
    local num_samples=$2
    local temp_file=$(mktemp)
    
    # Find all .json files, shuffle, and take first N
    find "$input_dir" -name "*.json" -type f | shuf | head -n "$num_samples" > "$temp_file"
    echo "$temp_file"
}

# Function to run experiment
run_experiment() {
    local exp_name=$1
    local input_dir=$2
    local output_dir=$3
    local samples_file=$4
    
    echo "Starting experiment: $exp_name"
    echo "Input directory: $input_dir"
    echo "Output directory: $output_dir"
    echo "Number of samples: $(wc -l < $samples_file)"
    
    # Create log file for this experiment
    local log_file="${output_dir}/experiment.log"
    
    # Log experiment parameters
    {
        echo "Experiment: $exp_name"
        echo "Timestamp: $TIMESTAMP"
        echo "Base threshold: $BASE_THRESHOLD"
        echo "Alpha: $ALPHA"
        echo "Input directory: $input_dir"
        echo "Number of samples: $(wc -l < $samples_file)"
        echo "================================"
    } > "$log_file"
    
    # Counter for progress
    local count=0
    local total=$(wc -l < "$samples_file")
    
    # Process each sample
    while IFS= read -r json_file; do
        count=$((count + 1))
        echo "[$count/$total] Processing: $(basename "$json_file")"
        
        # Extract filename for output
        local basename=$(basename "$json_file")
        local output_file="${output_dir}/${basename}"
        
        # Run main.py with the specific file (main.py is in current directory)
        python3 main.py \
            --data "$json_file" \
            --output "$output_file" \
            --verbose \
            >> "$log_file" 2>&1
        
        # Check if successful
        if [[ $? -eq 0 ]]; then
            echo "  ✓ Success"
        else
            echo "  ✗ Failed - check log for details"
            echo "FAILED: $json_file" >> "${output_dir}/failed_files.txt"
        fi
        
    done < "$samples_file"
    
    # Generate summary
    local success_count=$(find "$output_dir" -name "*.json" -not -name "failed_files.txt" | wc -l)
    local failed_count=$(if [[ -f "${output_dir}/failed_files.txt" ]]; then wc -l < "${output_dir}/failed_files.txt"; else echo 0; fi)
    
    echo "Experiment $exp_name completed!"
    echo "  Successful: $success_count"
    echo "  Failed: $failed_count"
    echo "  Log: $log_file"
    echo ""
    
    # Add summary to log
    {
        echo "================================"
        echo "EXPERIMENT SUMMARY"
        echo "Total samples: $total"
        echo "Successful: $success_count"
        echo "Failed: $failed_count"
        echo "Success rate: $(( (success_count * 100) / total ))%"
    } >> "$log_file"
}

# Function to update config.py with new parameters
update_config() {
    local config_file="./config.py"
    local backup_file="${config_file}.backup_${TIMESTAMP}"
    
    # Backup original config
    cp "$config_file" "$backup_file"
    echo "Backed up config to: $backup_file"
    
    # Update base_threshold and alpha in QUESTION_CONFIG
    # This is a simple sed replacement - might need adjustment based on your config.py format
    sed -i "s/\"base_threshold\":[[:space:]]*[0-9.]*/\"base_threshold\": $BASE_THRESHOLD/g" "$config_file"
    sed -i "s/\"alpha\":[[:space:]]*[0-9.]*/\"alpha\": $ALPHA/g" "$config_file"
    
    echo "Updated config.py with base_threshold=$BASE_THRESHOLD, alpha=$ALPHA"
}

# Main execution
main() {
    echo "==================================="
    echo "Starting disambiguation experiments"
    echo "==================================="
    echo "Timestamp: $TIMESTAMP"
    echo "Base threshold: $BASE_THRESHOLD"
    echo "Alpha: $ALPHA"
    echo "Samples per dataset: $NUM_SAMPLES"
    echo ""
    
    # Update configuration
    update_config
    
    # Get random samples for corrupted benchmark dataset
    echo "Selecting random samples from corrupted benchmark dataset..."
    # corrupted_bench_samples=$(get_random_samples "$CORRUPTED_BENCH_DIR" "$NUM_SAMPLES")
    corrupted_bench_output=$(create_output_dir "corrupted_benchmark_final_v2")
    
    # Get random samples for ambiguous dataset
    echo "Selecting random samples from ambiguous dataset..."
    amb_samples=$(get_random_samples "$AMB_DIR" "$NUM_SAMPLES")
    amb_output=$(create_output_dir "bfcl_amb_v2")
    
    # Get random samples for normal dataset  
    echo "Selecting random samples from normal dataset..."
    norm_samples=$(get_random_samples "$NORM_DIR" "$NUM_SAMPLES")
    norm_output=$(create_output_dir "bfcl_norm_v2")
    
    # Run experiments
    # run_experiment "corrupted_benchmark_final_v2" "$CORRUPTED_BENCH_DIR" "$corrupted_bench_output" "$corrupted_bench_samples"
    run_experiment "bfcl_amb_v2" "$AMB_DIR" "$amb_output" "$amb_samples"
    run_experiment "bfcl_norm_v2" "$NORM_DIR" "$norm_output" "$norm_samples"
    
    # Cleanup temp files
    rm -f "$corrupted_bench_samples" "$amb_samples" "$norm_samples"
    
    echo "==================================="
    echo "All experiments completed!"
    echo "Results saved in:"
    echo "  Corrupted Benchmark: $corrupted_bench_output"
    echo "  Ambiguous (BFCL): $amb_output"
    echo "  Normal (BFCL): $norm_output"
    echo "==================================="
}

# Check if required directories exist
if [[ ! -d "$CORRUPTED_BENCH_DIR" ]]; then
    echo "Error: Corrupted benchmark directory not found: $CORRUPTED_BENCH_DIR"
    exit 1
fi

if [[ ! -d "$AMB_DIR" ]]; then
    echo "Error: Ambiguous dataset directory not found: $AMB_DIR"
    exit 1
fi

if [[ ! -d "$NORM_DIR" ]]; then
    echo "Error: Normal dataset directory not found: $NORM_DIR"
    exit 1
fi

if [[ ! -f "./main.py" ]]; then
    echo "Error: main.py not found in current directory"
    exit 1
fi

# Run the main function
main