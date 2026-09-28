#!/usr/bin/env python3
from pathlib import Path
import re, zipfile, requests, numpy as np
from PIL import Image

ROOT=Path(r"C:\AI\NAO\BIGBANG2026\BIGBANG_STORY")
D=ROOT/"_downloads"; A=ROOT/"ASC"; P=ROOT/"PNG"
BASE="https://groupware.sinanet.isprambiente.it/bigbang-data/library/bigbang100/ascii_grid"
DATA={
"TP":("total_precipitation","tp_monthly_1951-2025"),
"SP":("snow_precipitation","sp_monthly_1951-2025"),
"SM":("snow_melt","sm_monthly_1951-2025"),
"AE":("actual_evapotranspiration","ae_monthly_1951-2025"),
"RF":("surface_runoff","rf_monthly_1951-2025"),
"WS":("soil_water_content","ws_monthly_1951-2025"),
"IF":("internal_flow","if_monthly_1951-2025")}
S=requests.Session(); S.headers["User-Agent"]="Mozilla/5.0"

def url(c,f,s): return f"{BASE}/{f}/{s}/download/en/1/{c}_MONTHLY_1951-2025.zip"

def download(u,d):
    part=Path(str(d)+".part"); n=part.stat().st_size if part.exists() else 0
    h={"Range":f"bytes={n}-"} if n else {}
    with S.get(u,stream=True,timeout=(30,300),headers=h) as r:
        r.raise_for_status()
        if n and r.status_code==200: part.unlink(missing_ok=True); n=0
        mode="ab" if n and r.status_code==206 else "wb"
        total=int(r.headers.get("content-length",0))+n
        with open(part,mode) as w:
            for ch in r.iter_content(4*1024*1024):
                if ch:
                    w.write(ch); n+=len(ch)
                    if total: print(f"\r{d.name}: {100*n/total:5.1f}%",end="",flush=True)
    print(); part.replace(d)

def files(folder,c):
    rx=re.compile(rf"^{c.lower()}_(\d{{4}})_(\d{{2}})c?\.asc$",re.I)
    z=[]
    for x in folder.rglob("*.asc"):
        m=rx.match(x.name)
        if m:z.append((int(m[1]),int(m[2]),x))
    return sorted(z)

def readasc(p):
    h={}
    with open(p,encoding="utf-8",errors="replace") as f:
        for _ in range(6):
            q=f.readline().split(); h[q[0].lower()]=float(q[1])
        a=np.loadtxt(f,dtype=np.float32)
    a[a==h.get("nodata_value",-9999)]=np.nan
    return a

def scale(fs):
    ss=[]
    for i,(_,_,p) in enumerate(fs,1):
        v=readasc(p); v=v[np.isfinite(v)]
        if len(v): ss.append(v[::max(1,len(v)//20000)])
        if i%100==0: print("scala:",i,"/ 900")
    return float(np.nanpercentile(np.concatenate(ss),98))

def rgba(a,hi):
    ok=np.isfinite(a); x=np.zeros(a.shape,np.float32)
    x[ok]=np.clip(a[ok]/hi,0,1)
    stops=np.array([[247,251,255],[198,219,239],[107,174,214],[33,113,181],[8,48,107]],np.float32)
    q=x*4; k=np.minimum(q.astype(int),3); t=q-k
    rgb=stops[k]*(1-t[...,None])+stops[k+1]*t[...,None]
    out=np.zeros((*a.shape,4),np.uint8); out[...,:3]=rgb.astype(np.uint8); out[...,3]=ok*255
    return out

def main():
    for x in (D,A,P):x.mkdir(parents=True,exist_ok=True)
    for c,(folder,slug) in DATA.items():
        print("\n==",c,"==")
        z=D/f"{c}_MONTHLY_1951-2025.zip"
        if not z.exists(): download(url(c,folder,slug),z)
        dest=A/c; marker=dest/".ok"
        if not marker.exists():
            dest.mkdir(parents=True,exist_ok=True)
            with zipfile.ZipFile(z) as q:q.extractall(dest)
            marker.write_text("ok")
        fs=files(dest,c)
        print("ASC trovati:",len(fs))
        if len(fs)!=900: raise RuntimeError(f"{c}: attesi 900 ASC, trovati {len(fs)}")
        expected=[(y,m) for y in range(1951,2026) for m in range(1,13)]
        if [(y,m) for y,m,_ in fs]!=expected: raise RuntimeError(f"{c}: mesi mancanti")
        out=P/f"{c}_MONTHLY_1KM_1951-2025"; out.mkdir(exist_ok=True)
        sf=out/"_scale.txt"
        if sf.exists(): hi=float(sf.read_text().split("=")[1])
        else:
            hi=scale(fs); sf.write_text(f"display_max={hi}\npercentile=98\n")
        print("P98 fisso:",hi)
        for i,(y,m,a) in enumerate(fs,1):
            o=out/f"{c.lower()}_{y}_{m:02d}.png"
            if not o.exists(): Image.fromarray(rgba(readasc(a),hi),"RGBA").save(o,optimize=True)
            if i%100==0 or i==900: print("PNG:",i,"/ 900")
    print("\nFINITO:",P)
    print("6300 PNG nuovi; con GR già pronto = 7200 raster mensili.")

if __name__=="__main__": main()
