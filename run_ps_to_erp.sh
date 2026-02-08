#!/bin/bash

# Activate Python environment
source ~/Documents/peoplestrong/venv/bin/activate

# Go to the project directory
cd ~/Documents/peoplestrong

# Single log file
LOG_FILE="logs/ps_to_erp_task_schedular.log"

# Ensure logs directory exists
mkdir -p logs

# Append start timestamp
echo "===== Starting PeopleStrong → ERP BOT at $(date) =====" | tee -a $LOG_FILE

# Function to run Python script
run_python_script() {
    echo ">>> Attempting to run as module: $1" | tee -a $LOG_FILE
    python3 -m "$1" 2>&1 | tee -a $LOG_FILE
}

run_python_file() {
    echo ">>> Attempting to run as file: $1.py" | tee -a $LOG_FILE
    python3 "$1.py" 2>&1 | tee -a $LOG_FILE
}

# Try module first
MODULE_NAME="RPA_AUTOMATION"
run_python_script "$MODULE_NAME"

# Capture exit code
EXIT_CODE=${PIPESTATUS[0]}

# If module failed, try as a file
if [ $EXIT_CODE -ne 0 ]; then
    echo ">>> Module run failed with exit code $EXIT_CODE, falling back to .py file" | tee -a $LOG_FILE
    run_python_file "$MODULE_NAME"
    EXIT_CODE=${PIPESTATUS[0]}
fi

# Final status
if [ $EXIT_CODE -eq 0 ]; then
    echo ">>> RPA_AUTOMATION completed successfully." | tee -a $LOG_FILE
else
    echo "!!! RPA_AUTOMATION finished with errors. Exit code: $EXIT_CODE" | tee -a $LOG_FILE
fi

# Append finish timestamp
echo "===== BOT Finished at $(date) =====" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE
