# SOD Scripts & SKS Waveform Cutter

This repository contains tools for a complete seismic data workflow:
1.  **Data Acquisition**: Scripts for **SOD** ([Standing Order for Data](http://www.seis.sc.edu/sod/)) to download continuous seismograms (e.g., SAC, miniSEED).
2.  **Post-Processing**: A Python based workflow to extract specific phases (e.g., **SKS**) from the downloaded continuous data, handling instrument response removal and quality control.

---

## Part 1: Data Acquisition (SOD)

After downloading and installing [SOD](http://www.seis.sc.edu/downloads/sod/), you can run the recipe as follows:

```bash
$ sod -f a01_6C_EQ.xml
```

### Notes on Data Centers
The default Data Center for catalog and seismogram is **IRIS-DMC**. Some non-default Data Centers are configured as follows:
- **IRIS-DMC**: `service.iris.edu`
- **IRIS-DMC's PH5**: `service.iris.edu`
- **SCEDC**: `service.scedc.caltech.edu`
- **NCEDC**: `service.ncedc.org`
- **GEOFON**: `geofon.gfz-potsdam.de`
- **ETH**: `eida.ethz.ch`
- **RESIF**: `ws.resif.fr`

---

## Part 2: Post-Processing (Python SKS Cutter)

The included Python scripts (`main.py`, `utils.py`, `config.py`) are designed to process the continuous data downloaded by SOD.

### Features
*   **Phase Extraction**: Calculates theoretical arrival times (using `TauP`) for SKS or other phases based on an earthquake catalog.
*   **Cross-Day Handling**: Automatically finds and merges waveform files if the target time window crosses UTC midnight.
*   **Quality Control**: **3-Component Integrity Check** ensures that Z, N, and E components are all present and non-empty. Incomplete events are skipped.
*   **Preprocessing**: Detrending, tapering, and bandpass filtering.
*   **Response Removal**: Supports `StationXML`, `RESP`, or `SACPZ` formats.
*   **Header Management**: Writes full event/station coordinates and relative time markers (`b`, `a`, `ka`) to SAC headers.

### Directory Structure
The scripts expect the following directory structure (standard SOD output):

```text
.
├── config.py              # User configuration (paths, filter settings)
├── main.py                # Main execution script
├── utils.py               # Helper functions
├── events.xlsx            # Input: Earthquake catalog
├── responses/             # Input: Instrument response files
└── rawdata/               # Input: SOD Output Directory
    └── {net}_day_sac/
        └── {net}.{sta}/
            └── yyyy.mm.dd.{net}.{sta}.{chn}.sac
```

### Requirements
Install the necessary Python libraries:

```bash
pip install obspy pandas tqdm openpyxl
```

### Configuration (`config.py`)
Edit `config.py` to control the processing logic:

*   **`CATALOG_FILE`**: Path to your Excel event catalog. Must include columns: `origin_time`, `evlo`, `evla`, `evdp`, `mag`.
*   **`CHANNEL_WILDCARD`**: Set to `"*"` or `"*H?"` to ensure 3-component data is read.
*   **`RESPONSE_MODE`**: Set to `'xml'`, `'resp'`, `'sacpz'`, or `None`.
*   **`MIN_DIST` / `MAX_DIST`**: Filter events by epicentral distance (default: 85°-140°).

### Usage
Run the main script to process the data:

```bash
python main.py
```
The processed waveforms will be saved in the `SKS_Waveforms_Output/` directory.

---

## Links
More detailed information and examples regarding SOD recipes can be found here:

- [Seisman's SOD recipes](https://github.com/seisman/SODrecipes)
- [core-man's SOD recipes](https://github.com/core-man/SOD.recipes)

## Reference
- T. J. Owens, H. P. Crotwell, C. Groves, and P. Oliver-Paul. (2004). SOD: Standing Order for Data. _Seismological Research Letters_, 75(4), 515-520. [![Static Badge](https://img.shields.io/badge/DOI-10.1093%2Fgji/ggy448-blue)](https://doi.org/10.1785/gssrl.75.4.515-a)

## Author

**Changhui Ju**
*   Email: juchanghui15@mails.ucas.ac.cn
*   Copyright © 2026