import os
import glob
from tqdm import tqdm
from obspy import read, Stream
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

    # 2. Scan Station Directories
    # Structure assumption: rawdata/{net}_day_sac/{net}.{sta}
    # First, find network directories
    net_dirs = glob.glob(os.path.join(cfg.RAW_DATA_DIR, "*_day_sac"))
    station_paths = []
    for nd in net_dirs:
        # Find station folders within network folders
        station_paths.extend(glob.glob(os.path.join(nd, "*.*")))
    
    print(f"Found {len(station_paths)} station directories. Starting processing...")

    # 3. Main Loop by Station (Station-First approach for efficiency)
    for s_dir in tqdm(station_paths, desc="Processing Stations"):
        dir_name = os.path.basename(s_dir)
        try:
            net, sta = dir_name.split('.')
        except ValueError:
            continue # Skip folders that don't follow Net.Sta format

        # Get Station Coordinates (read only once per station)
        sample_files = glob.glob(os.path.join(s_dir, "*.sac"))
        if not sample_files: 
            continue
        
        stla, stlo, stel = utils.get_station_coords_fast(sample_files[0])
        if stla is None: 
            continue

        # 4. Loop through Events
        for ev in events:
            # 4.1 Epicentral Distance Filter
            dist = locations2degrees(ev['lat'], ev['lon'], stla, stlo)
            if not (cfg.MIN_DIST <= dist <= cfg.MAX_DIST):
                continue
            
            # 4.2 Travel Time Calculation
            try:
                arrivals = taup_model.get_travel_times(
                    source_depth_in_km=ev['depth'],
                    distance_in_degree=dist,
                    phase_list=[cfg.TARGET_PHASE])
                
                if not arrivals: 
                    continue
                
                # Absolute arrival time
                sks_abs = ev['time'] + arrivals[0].time
            except Exception: 
                continue

            # 4.3 Find Waveform Files (with Padding)
            # Add padding to ensure valid data at the edges after processing
            pad = 20
            t_search_start = sks_abs - cfg.OFFSET_PRE - pad
            duration = cfg.OFFSET_PRE + cfg.OFFSET_POST + (2 * pad)
            
            files = utils.find_waveform_files(net, sta, t_search_start, duration)
            if not files: 
                continue

            # 4.4 Read and Merge Data
            try:
                st = Stream()
                for f in files:
                    # Reading full file; optimization possible with starttime/endtime arguments
                    st += read(f)
                
                # Merge waveforms (fill gaps with interpolation)
                st.merge(method=1, fill_value='interpolate')
                
                # --- [CRITICAL STEP] 3-Component Completeness Check ---
                # Slice a window exactly covering the SKS area for checking
                check_win_start = sks_abs - cfg.OFFSET_PRE
                check_win_end = sks_abs + cfg.OFFSET_POST
                
                # Create a temporary slice (does not modify original stream)
                st_check = st.slice(check_win_start, check_win_end)
                
                # If components are missing (e.g., no 'E') or data is empty/incomplete
                if not utils.check_3c_completeness(st_check):
                    # Data is incomplete, skip this event for this station
                    continue
                # -----------------------------------------------------

                # 4.5 Remove Instrument Response (on original stream)
                st = utils.remove_response(st, net, sta, cfg.RESPONSE_MODE)
                
                # 4.6 Define Output Path
                if cfg.OUTPUT_STRUCTURE == 'event':
                    # Folder format: YYYYMMDD_HHMMSS_Mag
                    folder_name = f"{ev['time'].strftime('%Y%m%d_%H%M%S')}_M{ev['mag']}"
                    out_path = os.path.join(cfg.OUTPUT_DIR, folder_name)
                else:
                    # Folder format: Net.Sta
                    out_path = os.path.join(cfg.OUTPUT_DIR, f"{net}.{sta}")
                
                if not os.path.exists(out_path): 
                    os.makedirs(out_path)
                
                # 4.7 Final Processing and Saving
                utils.process_and_save(st, ev, sks_abs, (stla, stlo, stel), out_path)
                
            except Exception as e:
                # Catch individual waveform processing errors so the loop continues
                # print(f"Error processing {net}.{sta}: {e}")
                pass

    print("--- Processing Complete ---")

if __name__ == "__main__":
    main()