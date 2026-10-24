import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
import pvlib, json
hz = pd.read_parquet(os.path.join(S, "hz_out/hz_15min_model_13m.parquet")).set_index("timestamp_utc")
idx = grid_index(); assert len(hz) == len(idx) and (hz.index == idx).all()
w = calendar(idx)
# temperature gap fill
t = hz.outdoor_temp_c.copy(); isna = t.isna()
run_id = (isna != isna.shift()).cumsum(); run_len = isna.groupby(run_id).transform("sum")
lin = t.interpolate(method="time", limit_area="inside")
short = isna & (run_len <= 8)
t2 = t.copy(); t2[short] = lin[short]
long_ = isna & ~short
if long_.any():
    shifts = [t.shift(k*96) for k in (1,2,3)] + [t.shift(-k*96) for k in (1,2,3)]
    tod = pd.concat(shifts, axis=1).mean(axis=1)
    t2[long_] = tod[long_]
still = t2.isna(); t2 = t2.interpolate(limit_direction="both")  # any residual (edges)
w["outdoor_temp_c"] = t2.astype("float32")
w["temp_fill_flag"] = np.select([short, long_ & ~still, still], [1, 2, 3], 0).astype("int8")  # 0 measured,1 linear,2 tod-mean,3 fallback
w["rh_pct"] = hz.rh_pct.astype("float32"); w["rh_missing"] = hz.rh_pct.isna()
w["wind_m_s"] = hz.wind_m_s.astype("float32")
w["ghi_w_m2"] = hz.ghi_w_m2.clip(lower=0).astype("float32"); w["ghi_missing"] = hz.ghi_w_m2.isna()
w["rain_frac"] = hz.rain_frac.astype("float32")
mid = idx + pd.Timedelta(seconds=450)
sp = pvlib.solarposition.get_solarposition(mid, LAT, LON)
w["solar_zenith_deg"] = sp["apparent_zenith"].values.astype("float32")
# PV 1 kWdc
ghi = w.ghi_w_m2.astype(float).fillna(0).values
ghi = np.where(sp["apparent_zenith"].values > 90, 0, ghi)
erbs = pvlib.irradiance.erbs(ghi, sp["zenith"].values, mid)
dni = np.nan_to_num(erbs["dni"].values); dhi = np.nan_to_num(erbs["dhi"].values)
dni_extra = pvlib.irradiance.get_extra_radiation(mid).values
am = pvlib.atmosphere.get_relative_airmass(sp["apparent_zenith"].values)
poa = pvlib.irradiance.get_total_irradiance(30, 180, sp["apparent_zenith"].values, sp["azimuth"].values, dni, ghi, dhi,
                                            dni_extra=dni_extra, model="perez", airmass=am)
aoi = pvlib.irradiance.aoi(30, 180, sp["apparent_zenith"].values, sp["azimuth"].values)
iam = pvlib.iam.physical(aoi)
poa_eff = np.nan_to_num(np.asarray(poa["poa_direct"]) * iam + np.asarray(poa["poa_diffuse"]))
wind = w.wind_m_s.astype(float).interpolate(limit_direction="both").fillna(2).values
tcell = pvlib.temperature.sapm_cell(poa_eff, t2.values, wind, **pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]["open_rack_glass_polymer"])
pdc = pvlib.pvsystem.pvwatts_dc(poa_eff, tcell, pdc0=1.0, gamma_pdc=-0.0037) * (1 - 0.14)
pac = pvlib.inverter.pvwatts(pdc, pdc0=(1.0/1.2)/0.96, eta_inv_nom=0.96)
w["pv_per_kwdc"] = np.clip(np.nan_to_num(pac), 0, None).astype("float32")
w.loc[w.ghi_missing, "pv_per_kwdc"] = np.nan  # don't invent PV where GHI missing
w = w.reset_index(); check_window(w.timestamp_utc)
w.to_parquet(os.path.join(OUT, "weather.parquet"), compression="zstd", index=False)
# PV check vs HouseZero
hzpv = hz.pv_kw.values; m = np.isfinite(hzpv) & np.isfinite(w.pv_per_kwdc.values)
ann = float(np.nansum(w.pv_per_kwdc) / 4)
hz_ann = float(np.nansum(hzpv) / 4)
r15 = float(np.corrcoef(hzpv[m], w.pv_per_kwdc.values[m])[0,1])
dfh = pd.DataFrame({"a": hzpv, "b": w.pv_per_kwdc.values}, index=idx)[m].resample("1D").sum()
rday = float(np.corrcoef(dfh.a, dfh.b)[0,1])
rep = {"pv_model_kwh_per_kwdc_year": round(ann,1), "hz_pv_kwh_year": round(hz_ann,1),
       "hz_equiv_kwdc_by_energy": round(hz_ann/ann,2), "corr_15min": round(r15,3), "corr_daily": round(rday,3),
       "ghi_missing_steps": int(w.ghi_missing.sum()),
       "temp_fill_counts": {str(k): int(v) for k,v in w.temp_fill_flag.value_counts().items()},
       "rh_missing_frac": round(float(w.rh_missing.mean()),3)}
json.dump(rep, open(os.path.join(S, "unified_build/_weather_report.json"), "w"), indent=1); print(rep)
