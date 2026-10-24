# Harvard HouseZero dataset for MassHack

Measured hourly office-building electricity, PV and weather data from Cambridge, Massachusetts (Greater Boston).

Source: https://doi.org/10.6084/m9.figshare.26499595 (version 3).
Authors: Jung Min Han, Ali Malkawi, Xu Han, Sunghwan Lim, Elence Xinzhu Chen, Sang Won Kang, Yiwei Lyu, Peter Howard.
License: CC BY 4.0 https://creativecommons.org/licenses/by/4.0/
Paper: https://doi.org/10.1038/s41597-024-03770-7

Original bytes are preserved; filenames were renamed for clarity. See sources.json for original names, download URLs and MD5 checksums.

| File | Period | Rows | Encoding |
| --- | --- | --- | --- |
| loads_year1_2022-2023.csv | June 2022–May 2023 | 8760 | UTF-8 |
| weather_year1_2022-2023.csv | June 2022–May 2023 | 8760 | EUC-KR |
| loads_year2_2023-2024.csv | June 2023–May 2024 | 8784 | UTF-8 |
| weather_year2_2023-2024.csv | June 2023–May 2024 | 8784 | UTF-8 |

The first-year weather file uses EUC-KR for degree symbols; read it with pandas.read_csv(path, encoding="euc_kr"). Its time column is Time; the other files use Timestamp. Preserve timezone offsets when parsing timestamps.

PV_meter1_load (kW) and PV_meter2_load (kW) are PV readings. NET is signed grid exchange, not gross building load. IN is grid import; OUT is negative for export. Do not sum every numeric column. Battery cabinet is an electrical circuit measurement, not battery state of charge. Consult Data_Report.pdf for units and meter definitions. No utility tariff or complete battery-dispatch dataset is included.

For installation, copy the data/ directory into the MassHack repository root. These files contain historical observations; future observations must not be used as forecast inputs in a backtest.
