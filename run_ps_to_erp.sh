#!/bin/bash

# ============================
# PeopleStrong → ERP BOT Runner
# ============================

# Activate Python virtual environment
source ~/Documents/peoplestrong/venv/bin/activate

# Navigate to project directory
cd ~/Documents/peoplestrong || { echo "ERROR: Cannot cd to project directory"; exit 1; }

# Single log file
LOG_FILE="logs/ps_to_erp_task_schedular.log"

# Ensure logs directory exists
mkdir -p logs

# Append start timestamp
echo "===== Starting PeopleStrong → ERP BOT at $(date) =====" | tee -a "$LOG_FILE"

# -----------------------------
# Functions to run Python code
# -----------------------------

# Run as module
run_python_script() {
    local module="$1"
    local mode="$2"
    echo ">>> Attempting to run as module: $module with mode: $mode" | tee -a "$LOG_FILE"
    python3 -m "$module" "$mode" 2>&1 | tee -a "$LOG_FILE"
}

# Run as standalone .py file
run_python_file() {
    local file="$1"
    local mode="$2"
    echo ">>> Attempting to run as file: $file.py with mode: $mode" | tee -a "$LOG_FILE"
    python3 "$file.py" "$mode" 2>&1 | tee -a "$LOG_FILE"
}

# -----------------------------
# Main Execution
# -----------------------------

MODULE_NAME="RPA_AUTOMATION"
MODE="${1:-push}"   # default mode is "push"

# Try running as module
run_python_script "$MODULE_NAME" "$MODE"
EXIT_CODE=${PIPESTATUS[0]}

# If module fails, fallback to .py file
if [ $EXIT_CODE -ne 0 ]; then
    echo ">>> Module run failed with exit code $EXIT_CODE, falling back to .py file" | tee -a "$LOG_FILE"
    run_python_file "$MODULE_NAME" "$MODE"
    EXIT_CODE=${PIPESTATUS[0]}
fi

# -----------------------------
# Final Status
# -----------------------------

if [ $EXIT_CODE -eq 0 ]; then
    echo ">>> RPA_AUTOMATION completed successfully." | tee -a "$LOG_FILE"
else
    echo "!!! RPA_AUTOMATION finished with errors. Exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
fi

# Append finish timestamp
echo "===== BOT Finished at $(date) =====" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
