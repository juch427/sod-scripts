import os

# ================= Path Configuration =================
# Root directory for raw continuous waveform data
# Expected structure: rawdata/{net}_day_sac/{net}.{sta}/yyyy.mm.dd.{net}.{sta}.{chn}.sac
RAW_DATA_DIR = "rawdata"

# Earthquake catalog file (Excel format)
# Required columns: origin_time, evlo, evla, evdp, mag
CATALOG_FILE = "events.xlsx"

# Instrument response directory
# The program will search for files here based on RESPONSE_MODE
RESP_DIR = "responses"

# Output directory for cut waveforms
OUTPUT_DIR = "SKS_Waveforms_Output"

# ================= Cutting Parameters =================
# Epicentral distance range (in degrees)
MIN_DIST = 85.0
MAX_DIST = 140.0

# Target seismic phase
TARGET_PHASE = "SKS"

# Cutting window: Seconds BEFORE and AFTER the theoretical arrival time
OFFSET_PRE = 100.0
OFFSET_POST = 100.0

# Channel wildcard
# MUST be set to "*" or "*H?" or "*B?" to ensure 3-components (Z, N, E) are read
CHANNEL_WILDCARD = "*" 

# ================= Preprocessing Parameters =================
# Instrument response removal mode
# Options: 'xml' (StationXML), 'resp' (RESP files), 'sacpz' (SAC Poles & Zeros), or None (skip)
RESPONSE_MODE = "sacpz" 

# Bandpass filter settings
DO_FILTER = True
FREQ_MIN = 0.02  # Hz
FREQ_MAX = 0.5   # Hz

# Resampling rate (Hz). Set to None to skip resampling.
RESAMPLE_RATE = None 

# Earth model for travel time calculation (TauP)
TAUP_MODEL = "iasp91"

# Output directory structure
# 'event': OUTPUT_DIR/EventID/Net.Sta.SAC
# 'station': OUTPUT_DIR/Net.Sta/EventID.SAC
OUTPUT_STRUCTURE = "event"