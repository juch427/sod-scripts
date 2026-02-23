#!/bin/bash
# To run in background: nohup ./b01_downld_wave_data.sh &
# Exit immediately if a command exits with a non-zero status
set -e

# Clean up old files (silent mode)
rm -rf "6c_day_sac" "SodDb" 2>/dev/null || true
rm -f "sod_hibernate.out" *.log 2>/dev/null || true

# Execute the main command
sod -f a01_6C_continuous_data.xml
