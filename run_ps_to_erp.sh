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

# Run the Python script and append both stdout and stderr to the log
python3 -m  RPA_AUTOMATION.py 2>&1 | tee -a $LOG_FILE

# Append finish timestamp
echo "===== BOT Finished at $(date) =====" | tee -a $LOG_FILE
echo "" | tee -a $LOG_FILE  # extra line for separation
