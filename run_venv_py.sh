#!/bin/bash
# Activate the virtual environment
source /python-scripts/qaqc_venv/bin/activate
# Run the Python script with the provided argument
/python-scripts/qaqc_venv/bin/python3.12 "$1"