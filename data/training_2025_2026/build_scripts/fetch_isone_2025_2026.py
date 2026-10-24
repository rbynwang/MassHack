import gridstatus, pandas as pd, sys
iso=gridstatus.ISONE(); kind=sys.argv[1]
months=pd.date_range("2025-06-01","2026-06-01",freq="MS")
out=[]
import os
for a,b in zip(months[:-1],months[1:]):
    f=f"{kind}_{a:%Y%m}.parquet"
    if os.path.exists(f): out.append(pd.read_parquet(f)); continue
    for k in range(3):
        try:
            if kind=="lmp": d=iso.get_lmp(date=a.strftime("%Y-%m-%d"),end=b.strftime("%Y-%m-%d"),market="REAL_TIME_HOURLY",locations=[".Z.NEMASSBOST"])
            else: d=iso.get_load(date=a.strftime("%Y-%m-%d"),end=b.strftime("%Y-%m-%d"))
            out.append(d); d.to_parquet(f"{kind}_{a:%Y%m}.parquet"); print(kind,a.date(),len(d),flush=True); break
        except Exception as e: print("retry",a.date(),repr(e)[:150],flush=True)
pd.concat(out).to_parquet(f"isone_{kind}_2025_2026.parquet"); print("DONE",kind)
