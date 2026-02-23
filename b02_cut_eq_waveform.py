# main.py
import os
import glob
from tqdm import tqdm
from obspy import read, Stream, UTCDateTime
from obspy.taup import TauPyModel
from obspy.geodetics import locations2degrees

import config as cfg
import utils

def main():
    print(f"--- SKS Waveform Cutting Task Started | Target Phase: {cfg.TARGET_PHASE} ---")
    
    # 1. Initialization
    taup_model = TauPyModel(model=cfg.TAUP_MODEL)
    try:
        events = utils.load_catalog(cfg.CATALOG_FILE)
        print(f"Successfully loaded {len(events)} seismic events.")
    except Exception as e:
        print(f"Error loading catalog: {e}")
        return

    # 2. Scan Station Directories (Robust Version)
    station_paths = []
    
    # Method A: Try Flat Structure (rawdata/Net.Sta)
    flat_candidates = glob.glob(os.path.join(cfg.RAW_DATA_DIR, "*.*"))
    for p in flat_candidates:
        if os.path.isdir(p) and len(os.path.basename(p).split('.')) == 2:
            station_paths.append(p)
            
    # Method B: Try Nested Structure (rawdata/Net_day_sac/Net.Sta) - Original SOD style
    if not station_paths:
        nested_dirs = glob.glob(os.path.join(cfg.RAW_DATA_DIR, "*_day_sac"))
        for nd in nested_dirs:
            station_paths.extend(glob.glob(os.path.join(nd, "*.*")))
    
    # Remove duplicates and sort
    station_paths = sorted(list(set(station_paths)))
    total_stations = len(station_paths)
    
    print(f"Found {total_stations} station directories. Starting processing...")

    # 3. Main Loop (Iterate through stations)
    for idx, s_dir in enumerate(station_paths):
        dir_name = os.path.basename(s_dir)
        try:
            net, sta = dir_name.split('.')
        except ValueError:
            continue
        
        # Display Station Progress
        print(f"[{idx+1}/{total_stations}] Processing Station: {net}.{sta}")

        # Get Station Coordinates (read only once per station)
        sample_files = glob.glob(os.path.join(s_dir, "*.sac"))
        if not sample_files: 
            print(f"  -> No SAC files found, skipping.")
            continue
        
        stla, stlo, stel = utils.get_station_coords_fast(sample_files[0])
        if stla is None: 
            print(f"  -> Coordinates missing, skipping.")
            continue

        # --- OPTIMIZATION: Filter Events by Station Time Range ---
        # Get start and end dates of the station's data
        st_start, st_end = utils.get_station_time_range(s_dir)
        
        valid_events = []
        if st_start and st_end:
            # Add a buffer (e.g., +/- 1 day) to be safe
            safe_start = st_start - 86400
            safe_end = st_end + 86400
            # Only keep events that occurred while the station was active
            valid_events = [e for e in events if safe_start <= e['time'] <= safe_end]
        else:
            # Fallback if time parsing fails: use all events
            valid_events = events
            
        if not valid_events:
            print(f"  -> No events within station operating period. Skipping.")
            continue
            
        # Optional: Print how many events are relevant
        print(f"  -> Valid events: {len(valid_events)} / {len(events)}")
        # ---------------------------------------------------------

        # 4. Loop Events (Inner Loop)
        # Use tqdm here to show progress PER STATION. 
        # 'leave=False' clears the bar after station finishes to keep output clean.
        for ev in tqdm(valid_events, desc="  Scanning Events", unit="ev", leave=False):
            otime = UTCDateTime(ev['time'])

            # 4.1 Epicentral Distance Filter
            dist = locations2degrees(ev['lat'], ev['lon'], stla, stlo)
            if not (cfg.MIN_DIST <= dist <= cfg.MAX_DIST):
                continue
            
            # 4.2 Determine Target Time and Search Window Based on Mode
            if cfg.WINDOW_MODE == 'origin':
                target_time = otime
                t_search_start = target_time - cfg.OFFSET_PRE - cfg.PAD
            elif cfg.WINDOW_MODE == 'phase':               
                try:
                    arrivals = taup_model.get_travel_times(
                        source_depth_in_km=ev['depth'],
                        distance_in_degree=dist,
                        phase_list=[cfg.TARGET_PHASE])
                    
                    if not arrivals: 
                        continue
                    
                    # Absolute arrival time
                    target_time = otime + arrivals[0].time
                    t_search_start = target_time - cfg.OFFSET_PRE - cfg.PAD
                    
                except Exception: 
                    continue     

            duration = cfg.OFFSET_PRE + cfg.OFFSET_POST + (2 * cfg.PAD)
            files = utils.find_waveform_files(net, sta, t_search_start, duration)
            if not files: 
                continue

            # 4.4 Read and Merge Data
            try:
                st = Stream()
                for f in files:
                    st += read(f)
                
                # Merge waveforms (fill gaps with interpolation)
                st.merge(method=1, fill_value='interpolate')
                
                # --- [CRITICAL STEP] 3-Component Completeness Check ---
                # Slice a window exactly covering the phase/origin area for checking
                check_win_start = target_time - cfg.OFFSET_PRE
                check_win_end = target_time + cfg.OFFSET_POST
                
                # Create a temporary slice (does not modify original stream)
                st_check = st.slice(check_win_start, check_win_end)
                
                # If components are missing (e.g., no 'E') or data is empty/incomplete
                if not utils.check_3c_completeness(st_check):
                    continue
                # -----------------------------------------------------

                # 4.5 Remove Instrument Response (on a wider window stream)
                st_resp = st.slice(target_time - cfg.OFFSET_PRE*2 - cfg.PAD, target_time + cfg.OFFSET_POST*2 + cfg.PAD)

                st = utils.remove_response(st_resp, net, sta, cfg.RESPONSE_MODE)
                
                # 4.6 Define Output Path (Naming Requirement)
                if cfg.OUTPUT_STRUCTURE == 'event':
                    # Folder Format: yyyy.mm.dd.hh.mm.ss
                    folder_name = ev['time'].strftime("%Y.%m.%d.%H.%M.%S")
                    out_path = os.path.join(cfg.OUTPUT_DIR, folder_name)
                else:
                    # Folder Format: Net.Sta
                    out_path = os.path.join(cfg.OUTPUT_DIR, f"{net}.{sta}")
                
                if not os.path.exists(out_path): 
                    os.makedirs(out_path)
                
                # 4.7 Final Processing and Saving
                utils.process_and_save(st, ev, target_time, (stla, stlo, stel), out_path)
                
            except Exception:
                # Catch individual waveform processing errors so the loop continues
                pass

    print("\n--- Processing Complete ---")

if __name__ == "__main__":
    main()