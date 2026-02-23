# utils.py
import os
import glob
import pandas as pd
from obspy import read, UTCDateTime, read_inventory
from obspy.io.sac.sacpz import attach_paz
import config as cfg

def load_catalog(excel_path):
    """
    Reads and cleans the earthquake catalog from an Excel file.
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Catalog file not found: {excel_path}")
        
    df = pd.read_excel(excel_path)
    # Normalize column names to lowercase and strip whitespace
    df.columns = [c.lower().strip() for c in df.columns]
    
    events = []
    required_cols = ['origin_time', 'evlo', 'evla', 'evdp', 'mag']
    
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Excel is missing required column: {col}")

    for _, row in df.iterrows():
        try:
            ot = UTCDateTime(str(row['origin_time']))
            events.append({
                'time': ot,
                'lat': row['evla'],
                'lon': row['evlo'],
                'depth': row['evdp'], # Assuming depth is in km
                'mag': row['mag']
            })
        except Exception:
            # Skip rows with invalid time formats
            continue
    return events

def get_station_coords_fast(sac_file):
    """
    Quickly reads station coordinates from the SAC header.
    Returns: (lat, lon, elevation)
    """
    try:
        # Read header only for speed
        st = read(sac_file, headonly=True)
        tr = st[0]
        if hasattr(tr.stats, 'sac'):
            return tr.stats.sac.stla, tr.stats.sac.stlo, tr.stats.sac.stel
        elif hasattr(tr.stats, 'coordinates'):
            return tr.stats.coordinates.latitude, tr.stats.coordinates.longitude, tr.stats.coordinates.elevation
    except Exception:
        pass
    return None, None, 0.0

def get_station_time_range(station_dir):
    """
    Scans the station directory to find the earliest and latest SAC files.
    Used to optimize the event loop by skipping events outside the station's operation period.
    Assumes filename format: yyyy.mm.dd.net.sta.chn.sac
    """
    try:
        # List all SAC files
        files = sorted(glob.glob(os.path.join(station_dir, "*.sac")))
        if not files:
            return None, None
            
        # Parse the first file (Start Date)
        first_base = os.path.basename(files[0])
        # Split: [yyyy, mm, dd, net, sta, chn, sac]
        parts_first = first_base.split('.')
        t_start = UTCDateTime(f"{parts_first[0]}-{parts_first[1]}-{parts_first[2]}")
        
        # Parse the last file (End Date)
        last_base = os.path.basename(files[-1])
        parts_last = last_base.split('.')
        t_end = UTCDateTime(f"{parts_last[0]}-{parts_last[1]}-{parts_last[2]}")
        
        # Add 24 hours to the end time to cover the full last day
        t_end += 86400
        
        return t_start, t_end
    except Exception:
        # Return None if parsing fails (fallback to processing all events)
        return None, None

def find_waveform_files(net, sta, start_time, duration):
    """
    Finds waveform files based on the time window (supports day-crossing).
    Searches in both nested ({net}_day_sac) and flat ({net}.{sta}) structures.
    """
    file_list = []
    current_time = start_time
    end_time = start_time + duration
    
    # Calculate all dates involved in this window
    check_days = []
    t = UTCDateTime(current_time.year, current_time.month, current_time.day)
    while t < end_time:
        check_days.append(t)
        t += 86400 # Add one day

    # Construct directory path (Try both structures)
    path_nested = os.path.join(cfg.RAW_DATA_DIR, f"{net}_day_sac", f"{net}.{sta}")
    path_flat = os.path.join(cfg.RAW_DATA_DIR, f"{net}.{sta}")

    if os.path.exists(path_nested):
        station_dir = path_nested
    elif os.path.exists(path_flat):
        station_dir = path_flat
    else:
        return []

    for day in check_days:
        date_str = f"{day.year}.{day.month:02d}.{day.day:02d}"
        # File pattern: yyyy.mm.dd.net.sta.chn.sac
        pattern = f"{date_str}.{net}.{sta}.{cfg.CHANNEL_WILDCARD}.sac"
        full_path_pattern = os.path.join(station_dir, pattern)
        found_files = glob.glob(full_path_pattern)
        file_list.extend(found_files)
        
    return sorted(list(set(file_list)))

def check_3c_completeness(st):
    """
    Checks if the Stream contains complete 3-component data (Z, N, E) or (Z, 1, 2).
    Also checks if the data traces are not empty.
    Returns: True (Complete) / False (Incomplete)
    """
    if len(st) < 3:
        return False
    
    # Get component codes (last character of channel name, e.g., 'Z' from 'BHZ')
    comps = set([tr.stats.channel[-1].upper() for tr in st])
    
    # Valid combinations: (Z+N+E) or (Z+1+2)
    has_Z = 'Z' in comps
    has_NE = ('N' in comps and 'E' in comps)
    has_12 = ('1' in comps and '2' in comps)
    
    if not (has_Z and (has_NE or has_12)):
        return False
    
    # Check for empty traces or extremely short data
    for tr in st:
        if tr.stats.npts < 10: 
            return False
            
    return True

def remove_response(st, net, sta, mode):
    """
    Removes instrument response based on the selected mode.
    """
    if not mode: return st
    try:
        # Pre-filter to prevent instability during deconvolution
        pre_filt = cfg.PRE_FILTER 
        
        if mode == 'xml':
            # Search for StationXML files
            xml_files = glob.glob(os.path.join(cfg.RESP_DIR, f"*{net}*{sta}*.xml"))
            if not xml_files: 
                # Try generic/bulk XML if specific one not found
                xml_files = glob.glob(os.path.join(cfg.RESP_DIR, "*.xml"))
            
            if xml_files:
                inv = read_inventory(xml_files[0])
                st.remove_response(inventory=inv, output="VEL", pre_filt=pre_filt, water_level=60)
        
        elif mode == 'sacpz':
            # Search for SACPZ files
            for tr in st:
                # Match SACPZ filename pattern
                pz = glob.glob(os.path.join(cfg.RESP_DIR, f"SACPZ*{net}*{sta}*{tr.stats.channel}*"))
                if pz:
                    attach_paz(tr, pz[0], to_velocity=True)
                    tr.simulate(paz_remove=tr.stats.paz, pre_filt=pre_filt)

        elif mode == 'resp':
            # Search for RESP files
            for tr in st:
                resp = glob.glob(os.path.join(cfg.RESP_DIR, f"RESP*{net}*{sta}*{tr.stats.channel}"))
                if resp:
                    inv = read_inventory(resp[0])
                    tr.remove_response(inventory=inv, output="VEL", pre_filt=pre_filt, water_level=60)
    except Exception as e:
        print(f"    [Resp Warning] {net}.{sta}: {e}")
        
    return st

def process_and_save(st, ev, target_time, st_coords, out_dir):
    """
    Applies preprocessing (detrend, filter, cut) and saves to SAC format with headers.
    Filename Format: net.sta.yyyy.mm.dd.hh.mm.ss.chn.sac
    """
    stla, stlo, stel = st_coords
    
    # 1. Basic Preprocessing
    st.detrend("demean")
    st.detrend("linear")
    st.taper(0.05)
    
    if cfg.DO_FILTER:
        st.filter("bandpass", freqmin=cfg.FREQ_MIN, freqmax=cfg.FREQ_MAX)
        
    if cfg.RESAMPLE_RATE:
        st.resample(cfg.RESAMPLE_RATE)
        
    # 2. Precise Cutting (Trim)
    t_start = target_time - cfg.OFFSET_PRE
    t_end = target_time + cfg.OFFSET_POST
    st.trim(t_start, t_end)
    
    # Re-check length (in case trim resulted in empty data)
    if len(st) < 3 or st[0].stats.npts == 0:
        return

    # 3. Write SAC Headers and Save
    for tr in st:
        if not hasattr(tr.stats, 'sac'): tr.stats.sac = {}
        
        # Event Information
        tr.stats.sac.evla = ev['lat']
        tr.stats.sac.evlo = ev['lon']
        tr.stats.sac.evdp = ev['depth']
        tr.stats.sac.mag = ev['mag']
        
        # Station Information
        tr.stats.sac.stla = stla
        tr.stats.sac.stlo = stlo
        tr.stats.sac.stel = stel
        
        # Time Reference (Reference Time = Origin Time)
        tr.stats.sac.nzyear = ev['time'].year
        tr.stats.sac.nzjday = ev['time'].julday
        tr.stats.sac.nzhour = ev['time'].hour
        tr.stats.sac.nzmin = ev['time'].minute
        tr.stats.sac.nzsec = ev['time'].second
        tr.stats.sac.nzmsec = ev['time'].microsecond // 1000
        
        # Relative Times
        tr.stats.sac.b = tr.stats.starttime - ev['time']
        tr.stats.sac.o = 0.0
        if cfg.WINDOW_MODE == 'phase':
            tr.stats.sac.a = target_time - ev['time']
            tr.stats.sac.ka = cfg.TARGET_PHASE
        elif cfg.WINDOW_MODE == 'origin':
            tr.stats.sac.a = 0.0
            tr.stats.sac.ka = 'OT'
        
        # Generate Filename (Modified Requirement)
        # Format: net.sta.yyyy.mm.dd.hh.mm.ss.chn.sac
        t = ev['time']
        time_str = f"{t.year:04d}.{t.month:02d}.{t.day:02d}.{t.hour:02d}.{t.minute:02d}.{t.second:02d}"
        
        fname = f"{tr.stats.network}.{tr.stats.station}.{time_str}.{tr.stats.channel}.sac"
        save_path = os.path.join(out_dir, fname)
        
        tr.write(save_path, format="SAC")