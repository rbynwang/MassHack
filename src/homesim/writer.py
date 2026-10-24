"""Write homes.parquet, hourly/ (Parquet partitioned by home_type and month), and inputs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from homesim.inputs import Inputs

HOURLY_FLOAT_COLUMNS = [
    "temp_out_c", "t_in_c", "base_kw", "heat_pump_kw", "backup_heat_kw", "ac_kw",
    "blower_kw", "ev_kw", "pv_kw", "total_load_kw", "grid_net_kw", "grid_import_kw",
    "grid_export_kw",
]


def write_homes(homes: pd.DataFrame, out: Path, compression: str) -> None:
    pq.write_table(pa.Table.from_pandas(homes, preserve_index=False), out / "homes.parquet", compression=compression)


def write_inputs(inp: Inputs, out: Path, compression: str) -> None:
    df = inp.frame.reset_index()
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), out / "weather_inputs.parquet", compression=compression)


def write_hourly_batch(
    batch_idx: int,
    homes: pd.DataFrame,
    inp: Inputs,
    cols: dict[str, np.ndarray],
    occupied: np.ndarray,
    out: Path,
    compression: str,
) -> None:
    n, H = len(homes), inp.n_hours
    ts_utc = inp.frame.index
    ts_local = inp.frame["timestamp_local"]
    month = ts_local.dt.strftime("%Y-%m").to_numpy()

    arrays = {
        "timestamp_utc": pa.array(np.tile(ts_utc.to_numpy(), n), type=pa.timestamp("us", tz="UTC")),
        "timestamp_local": pa.array(
            np.tile(ts_local.dt.tz_convert("UTC").to_numpy(), n),
            type=pa.timestamp("us", tz=str(ts_local.dt.tz)),
        ),
        "home_id": pa.array(np.repeat(homes["home_id"].to_numpy(), H)),
    }
    for c in HOURLY_FLOAT_COLUMNS:
        arrays[c] = pa.array(cols[c].astype(np.float32).ravel())
    arrays["occupied"] = pa.array(occupied.ravel())
    arrays["home_type"] = pa.array(np.repeat(homes["home_type"].to_numpy(), H))
    arrays["month"] = pa.array(np.tile(month, n))
    table = pa.table(arrays)

    ds.write_dataset(
        table,
        out / "hourly",
        format="parquet",
        partitioning=ds.partitioning(pa.schema([("home_type", pa.string()), ("month", pa.string())]), flavor="hive"),
        basename_template=f"part-{batch_idx:04d}-{{i}}.parquet",
        existing_data_behavior="overwrite_or_ignore",
        file_options=ds.ParquetFileFormat().make_write_options(compression=compression),
    )
