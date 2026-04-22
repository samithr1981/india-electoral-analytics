"""
pipeline/00_generate_demo_data.py
====================================
Generates realistic demo data for ALL 23 West Bengal districts.
Completely party-neutral — parties stored as P1/P2/P3/P4.
User maps labels in dashboard sidebar.

Run: python pipeline/00_generate_demo_data.py              # Murshidabad only
     python pipeline/00_generate_demo_data.py --all        # all 23 districts
     python pipeline/00_generate_demo_data.py --district Malda
"""

import random
import argparse
import datetime
import numpy as np
import pandas as pd
from pathlib import Path

random.seed(42)
np.random.seed(42)

OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

DISTRICTS = {
    "Murshidabad":       dict(seats=22,pre_sir=3460000,sir=2870000,sir_adj=1101145,booths_total=3028,muslim_pct=67,sc_pct=31,st_pct=1, literacy=63.1,pop2011=7102430,female_ratio=957,p1_base=0.62,p2_base=0.22,turnout_asm=87.4,turnout_ls=80.0,
        acs={153:"Farakka",154:"Samserganj",155:"Suti",156:"Jangipur",157:"Raghunathganj",158:"Uday Hossain Khan",159:"Sagardighi",160:"Lalgola",161:"Bhagawangola",162:"Raninagar",163:"Murshidabad",164:"Nabagram",165:"Khargram",166:"Berhampore",167:"Baharampur",168:"Hariharpara",169:"Rejinagar",170:"Beldanga",171:"Bharatpur",172:"Burwan",173:"Kandi",174:"Nowda"},
        adj_by_ac={153:0.12,154:0.18,155:0.16,156:0.14,157:0.08,158:0.15,159:0.13,160:0.22,161:0.20,162:0.10,163:0.07,164:0.11,165:0.06,166:0.09,167:0.15,168:0.17,169:0.15,170:0.12,171:0.08,172:0.05,173:0.06,174:0.09}),
    "North 24 Parganas": dict(seats=33,pre_sir=5840000,sir=5100000,sir_adj=591252,booths_total=5980,muslim_pct=26,sc_pct=23,st_pct=1, literacy=81.1,pop2011=10009781,female_ratio=943,p1_base=0.58,p2_base=0.32,turnout_asm=84.0,turnout_ls=79.4,
        acs={c:f"N24P-{c:03d}" for c in range(101,134)},adj_by_ac={c:round(random.uniform(0.04,0.14),2) for c in range(101,134)}),
    "South 24 Parganas": dict(seats=26,pre_sir=3980000,sir=3400000,sir_adj=522042,booths_total=4180,muslim_pct=28,sc_pct=34,st_pct=5, literacy=78.0,pop2011=8153176,female_ratio=956,p1_base=0.60,p2_base=0.28,turnout_asm=85.0,turnout_ls=82.0,
        acs={c:f"S24P-{c:03d}" for c in range(201,227)},adj_by_ac={c:round(random.uniform(0.05,0.15),2) for c in range(201,227)}),
    "Purba Medinipur":   dict(seats=16,pre_sir=2540000,sir=2420000,sir_adj=28000, booths_total=2960,muslim_pct=4, sc_pct=14,st_pct=1, literacy=81.0,pop2011=5094238,female_ratio=975,p1_base=0.64,p2_base=0.28,turnout_asm=89.0,turnout_ls=87.5,
        acs={c:f"PMed-{c:03d}" for c in range(301,317)},adj_by_ac={c:round(random.uniform(0.01,0.04),2) for c in range(301,317)}),
    "Hooghly":           dict(seats=18,pre_sir=2620000,sir=2440000,sir_adj=35000, booths_total=2860,muslim_pct=9, sc_pct=26,st_pct=1, literacy=79.9,pop2011=5520389,female_ratio=951,p1_base=0.58,p2_base=0.32,turnout_asm=84.0,turnout_ls=81.1,
        acs={c:f"Hgl-{c:03d}" for c in range(401,419)},adj_by_ac={c:round(random.uniform(0.02,0.06),2) for c in range(401,419)}),
    "Nadia":             dict(seats=17,pre_sir=2540000,sir=2240000,sir_adj=267940,booths_total=2720,muslim_pct=24,sc_pct=32,st_pct=2, literacy=75.6,pop2011=5167600,female_ratio=953,p1_base=0.56,p2_base=0.34,turnout_asm=84.1,turnout_ls=81.0,
        acs={c:f"Nadia-{c:03d}" for c in range(501,518)},adj_by_ac={c:round(random.uniform(0.04,0.16),2) for c in range(501,518)}),
    "Paschim Medinipur": dict(seats=16,pre_sir=2820000,sir=2640000,sir_adj=18000, booths_total=3220,muslim_pct=8, sc_pct=21,st_pct=11,literacy=79.0,pop2011=5913457,female_ratio=967,p1_base=0.57,p2_base=0.33,turnout_asm=82.0,turnout_ls=81.1,
        acs={c:f"WMed-{c:03d}" for c in range(601,617)},adj_by_ac={c:round(random.uniform(0.01,0.04),2) for c in range(601,617)}),
    "Howrah":            dict(seats=16,pre_sir=2280000,sir=2060000,sir_adj=48000, booths_total=2240,muslim_pct=22,sc_pct=14,st_pct=0, literacy=80.1,pop2011=4850029,female_ratio=939,p1_base=0.57,p2_base=0.32,turnout_asm=83.0,turnout_ls=78.1,
        acs={c:f"Hwr-{c:03d}" for c in range(701,717)},adj_by_ac={c:round(random.uniform(0.02,0.07),2) for c in range(701,717)}),
    "Malda":             dict(seats=12,pre_sir=1980000,sir=1480000,sir_adj=828127,booths_total=2220,muslim_pct=51,sc_pct=39,st_pct=5, literacy=62.7,pop2011=3988845,female_ratio=954,p1_base=0.55,p2_base=0.22,turnout_asm=84.9,turnout_ls=80.0,
        acs={c:f"Malda-{c:03d}" for c in range(801,813)},adj_by_ac={c:round(random.uniform(0.30,0.60),2) for c in range(801,813)}),
    "Purba Bardhaman":   dict(seats=16,pre_sir=2380000,sir=2220000,sir_adj=365539,booths_total=2640,muslim_pct=10,sc_pct=30,st_pct=3, literacy=75.1,pop2011=4835532,female_ratio=949,p1_base=0.60,p2_base=0.28,turnout_asm=85.0,turnout_ls=83.0,
        acs={c:f"EBrd-{c:03d}" for c in range(901,917)},adj_by_ac={c:round(random.uniform(0.08,0.22),2) for c in range(901,917)}),
    "Bankura":           dict(seats=10,pre_sir=1680000,sir=1560000,sir_adj=22000, booths_total=1840,muslim_pct=5, sc_pct=35,st_pct=9, literacy=70.9,pop2011=3596674,female_ratio=959,p1_base=0.55,p2_base=0.34,turnout_asm=81.0,turnout_ls=78.0,
        acs={c:f"Bnk-{c:03d}" for c in range(1001,1011)},adj_by_ac={c:round(random.uniform(0.01,0.04),2) for c in range(1001,1011)}),
    "Birbhum":           dict(seats=11,pre_sir=1540000,sir=1420000,sir_adj=42000, booths_total=1780,muslim_pct=37,sc_pct=36,st_pct=7, literacy=62.4,pop2011=3502404,female_ratio=956,p1_base=0.60,p2_base=0.26,turnout_asm=83.0,turnout_ls=77.1,
        acs={c:f"Birb-{c:03d}" for c in range(1101,1112)},adj_by_ac={c:round(random.uniform(0.02,0.07),2) for c in range(1101,1112)}),
    "Cooch Behar":       dict(seats=9, pre_sir=1510000,sir=1280000,sir_adj=238107,booths_total=1640,muslim_pct=11,sc_pct=51,st_pct=0, literacy=75.5,pop2011=2822780,female_ratio=943,p1_base=0.52,p2_base=0.38,turnout_asm=81.0,turnout_ls=82.0,
        acs={c:f"CB-{c:03d}" for c in range(1201,1210)},adj_by_ac={c:round(random.uniform(0.10,0.22),2) for c in range(1201,1210)}),
    "Uttar Dinajpur":    dict(seats=9, pre_sir=1540000,sir=1280000,sir_adj=480341,booths_total=1520,muslim_pct=49,sc_pct=43,st_pct=10,literacy=60.2,pop2011=3007134,female_ratio=950,p1_base=0.58,p2_base=0.22,turnout_asm=85.0,turnout_ls=80.0,
        acs={c:f"UD-{c:03d}" for c in range(1301,1310)},adj_by_ac={c:round(random.uniform(0.20,0.45),2) for c in range(1301,1310)}),
    "Paschim Bardhaman": dict(seats=9, pre_sir=1520000,sir=1400000,sir_adj=12000, booths_total=1680,muslim_pct=11,sc_pct=25,st_pct=2, literacy=74.5,pop2011=2882031,female_ratio=928,p1_base=0.54,p2_base=0.33,turnout_asm=83.0,turnout_ls=81.1,
        acs={c:f"WBrd-{c:03d}" for c in range(1401,1410)},adj_by_ac={c:round(random.uniform(0.01,0.03),2) for c in range(1401,1410)}),
    "Jalpaiguri":        dict(seats=8, pre_sir=1830000,sir=1720000,sir_adj=19000, booths_total=1980,muslim_pct=8, sc_pct=36,st_pct=13,literacy=72.4,pop2011=3872846,female_ratio=952,p1_base=0.50,p2_base=0.38,turnout_asm=81.0,turnout_ls=77.0,
        acs={c:f"Jlp-{c:03d}" for c in range(1501,1509)},adj_by_ac={c:round(random.uniform(0.01,0.04),2) for c in range(1501,1509)}),
    "Purulia":           dict(seats=9, pre_sir=1360000,sir=1280000,sir_adj=14000, booths_total=1520,muslim_pct=5, sc_pct=20,st_pct=26,literacy=65.4,pop2011=2930115,female_ratio=955,p1_base=0.52,p2_base=0.36,turnout_asm=82.3,turnout_ls=79.4,
        acs={c:f"Prl-{c:03d}" for c in range(1601,1610)},adj_by_ac={c:round(random.uniform(0.01,0.03),2) for c in range(1601,1610)}),
    "Alipurduar":        dict(seats=5, pre_sir=1420000,sir=1360000,sir_adj=18000, booths_total=1480,muslim_pct=9, sc_pct=37,st_pct=23,literacy=71.1,pop2011=1491250,female_ratio=949,p1_base=0.48,p2_base=0.40,turnout_asm=84.0,turnout_ls=80.9,
        acs={c:f"Alp-{c:03d}" for c in range(1701,1706)},adj_by_ac={c:round(random.uniform(0.01,0.03),2) for c in range(1701,1706)}),
    "Dakshin Dinajpur":  dict(seats=6, pre_sir=900000, sir=840000, sir_adj=28000, booths_total=940, muslim_pct=28,sc_pct=43,st_pct=3, literacy=67.6,pop2011=1670931,female_ratio=952,p1_base=0.57,p2_base=0.27,turnout_asm=82.0,turnout_ls=81.0,
        acs={c:f"DD-{c:03d}" for c in range(1801,1807)},adj_by_ac={c:round(random.uniform(0.02,0.06),2) for c in range(1801,1807)}),
    "Darjeeling":        dict(seats=6, pre_sir=1480000,sir=1360000,sir_adj=12000, booths_total=1480,muslim_pct=4, sc_pct=19,st_pct=32,literacy=79.9,pop2011=1846823,female_ratio=974,p1_base=0.42,p2_base=0.44,turnout_asm=78.0,turnout_ls=72.3,
        acs={c:f"Drj-{c:03d}" for c in range(1901,1907)},adj_by_ac={c:round(random.uniform(0.01,0.03),2) for c in range(1901,1907)}),
    "Jhargram":          dict(seats=4, pre_sir=680000, sir=640000, sir_adj=8000,  booths_total=740, muslim_pct=3, sc_pct=19,st_pct=45,literacy=65.4,pop2011=1136548,female_ratio=970,p1_base=0.55,p2_base=0.33,turnout_asm=81.5,turnout_ls=78.8,
        acs={c:f"Jhr-{c:03d}" for c in range(2001,2005)},adj_by_ac={c:round(random.uniform(0.01,0.03),2) for c in range(2001,2005)}),
    "Kolkata":           dict(seats=11,pre_sir=2020000,sir=1860000,sir_adj=18000, booths_total=1960,muslim_pct=28,sc_pct=12,st_pct=0, literacy=87.1,pop2011=4486679,female_ratio=899,p1_base=0.58,p2_base=0.30,turnout_asm=80.0,turnout_ls=71.0,
        acs={c:f"KOL-{c:03d}" for c in range(2101,2112)},adj_by_ac={c:round(random.uniform(0.01,0.04),2) for c in range(2101,2112)}),
    "Kalimpong":         dict(seats=2, pre_sir=180000, sir=168000, sir_adj=4000,  booths_total=196, muslim_pct=2, sc_pct=6, st_pct=57,literacy=79.8,pop2011=251642, female_ratio=997,p1_base=0.40,p2_base=0.46,turnout_asm=72.0,turnout_ls=67.0,
        acs={c:f"Klp-{c:03d}" for c in range(2201,2203)},adj_by_ac={c:round(random.uniform(0.01,0.03),2) for c in range(2201,2203)}),
}

BOOTH_NAMES = ["Primary School","High School","Govt Office","Panchayat Bhavan",
               "Community Hall","Madrasa","Club Building","Post Office",
               "Health Sub-Centre","Anganwadi Centre","Market Building","Temple Hall"]


def gen_district(name: str, meta: dict) -> dict:
    acs   = meta["acs"]
    adj_m = meta["adj_by_ac"]
    n_acs = len(acs)
    bpa   = meta["booths_total"] // n_acs  # booths per ac
    p1b   = meta["p1_base"]
    p2b   = meta["p2_base"]
    t_asm = meta["turnout_asm"]

    # SIR rolls
    sir_rows = []
    for ac_code, ac_name in acs.items():
        for part in range(1, bpa + random.randint(0, 15)):
            tot = random.randint(480, 820)
            fp  = random.uniform(0.472, 0.508)
            fem = round(tot * fp)
            mal = tot - fem - random.randint(0, 1)
            sir_rows.append({"district":name,"ac_code":ac_code,"ac_name":ac_name,
                "part_no":part,"booth_name":f"{random.choice(BOOTH_NAMES)} {part}",
                "male":mal,"female":fem,"third_gender":max(0,tot-mal-fem),
                "total":tot,"female_pct":round(fem/tot*100,2)})
    sir_df = pd.DataFrame(sir_rows)

    # Form 20 — party neutral P1/P2/P3/P4
    f20_rows = []
    for _, b in sir_df.iterrows():
        ac = b["ac_code"]
        for year in [2019, 2021]:
            tv = round(b["total"] * random.uniform(t_asm*0.90, t_asm*1.04) / 100)
            p1 = max(0.25, min(0.80, p1b + random.gauss(0, 0.07)))
            p2 = max(0.10, min(0.55, p2b + random.gauss(0, 0.06)))
            if p1 + p2 > 0.90: p2 = 0.90 - p1
            p3 = random.uniform(0.03, 0.12) * (1 - p1 - p2)
            p4 = max(0, 1 - p1 - p2 - p3 - 0.01)
            vp1,vp2,vp3,vp4 = round(tv*p1),round(tv*p2),round(tv*p3),round(tv*p4)
            vnota = max(1, tv - vp1 - vp2 - vp3 - vp4)
            vts   = {"P1":vp1,"P2":vp2,"P3":vp3,"P4":vp4}
            w     = max(vts,key=vts.get)
            sc    = sorted(vts,key=vts.get,reverse=True)
            f20_rows.append({"district":name,"ac_code":ac,"ac_name":b["ac_name"],
                "part_no":b["part_no"],"booth_name":b["booth_name"],"year":year,
                "votes_P1":vp1,"votes_P2":vp2,"votes_P3":vp3,"votes_P4":vp4,
                "votes_NOTA":vnota,"total_votes":tv,"winner":w,
                "margin":vts[w]-vts[sc[1]],"turnout_pct":round(tv/b["total"]*100,1)})
    f20_df = pd.DataFrame(f20_rows)

    # Classification
    f21 = f20_df[f20_df["year"]==2021].set_index(["ac_code","part_no"])
    f19 = f20_df[f20_df["year"]==2019].set_index(["ac_code","part_no"])
    cl_rows = []
    for _, b in sir_df.iterrows():
        ac,part = int(b["ac_code"]),b["part_no"]
        key = (ac,part)
        adj_r = adj_m.get(ac, 0.05)
        adj_c = round(b["total"] * adj_r * random.uniform(0.7,1.3))
        adj_p = round(adj_c/max(b["total"],1)*100,1)
        r21   = f21.loc[key] if key in f21.index else None
        r19   = f19.loc[key] if key in f19.index else None
        w21   = r21["winner"] if r21 is not None else "?"
        w19   = r19["winner"] if r19 is not None else "?"
        m21   = int(r21["margin"]) if r21 is not None else 0
        vp1   = int(r21["votes_P1"]) if r21 is not None else 0
        vp2   = int(r21["votes_P2"]) if r21 is not None else 0
        tv21  = int(r21["total_votes"]) if r21 is not None else 1
        p1s   = round(vp1/max(tv21,1)*100,1)
        p2s   = round(vp2/max(tv21,1)*100,1)
        flip  = (w21!=w19 and w19!="?")
        if   adj_p > 10:  cat = "D"
        elif m21 < 50 or flip: cat = "B"
        elif p1s > 65:    cat = "A"
        elif p2s > 65:    cat = "C"
        else:             cat = "B"
        cl_rows.append({**b.to_dict(),
            "adj_count":adj_c,"adj_pct":adj_p,
            "votes_P1_2021":vp1,"votes_P2_2021":vp2,
            "votes_P3_2021":int(r21["votes_P3"]) if r21 is not None else 0,
            "total_votes_2021":tv21,"winner_2021":w21,"margin_2021":m21,
            "P1_share_2021":p1s,"P2_share_2021":p2s,
            "votes_P1_2019":int(r19["votes_P1"]) if r19 is not None else 0,
            "votes_P2_2019":int(r19["votes_P2"]) if r19 is not None else 0,
            "total_votes_2019":int(r19["total_votes"]) if r19 is not None else 1,
            "winner_2019":w19,"flipped_19_21":flip,
            "booth_category":cat,"priority_score":{"D":4,"B":3,"C":2,"A":1}[cat],
            "worker_assigned":"","contact_count":0,
            "votes_to_win_est":round(b["total"]*(t_asm/100)*0.501),"notes":""})
    cl_df = pd.DataFrame(cl_rows)

    # Workers
    w_rows,wid = [],1
    for ac_code,ac_name in acs.items():
        for _ in range(random.randint(60,100)):
            w_rows.append({"worker_id":f"W{wid:05d}","name":f"Worker-{wid}",
                "mobile":f"98{random.randint(10000000,99999999)}",
                "ac_code":ac_code,"ac_name":ac_name,"assigned_booth_part":None,
                "tier":random.choice(["BLA","BLO","Supervisor","Volunteer"]),"active":True})
            wid+=1
    w_df = pd.DataFrame(w_rows)

    # Daily targets
    today = datetime.date.today()
    prio  = cl_df[cl_df["booth_category"].isin(["B","D"])].head(300)
    t_rows = [{"ac_code":b["ac_code"],"part_no":b["part_no"],
        "booth_category":b["booth_category"],
        "target_contacts":max(20,round(b["total"]*0.15)),
        "contacts_done":random.randint(0,round(b["total"]*0.08)),
        "last_contact_date":str(today-datetime.timedelta(days=random.randint(1,10))),
        "flag_form6_filed":random.choice([True,False]) if b["booth_category"]=="D" else False}
        for _,b in prio.iterrows()]
    t_df = pd.DataFrame(t_rows)

    return {"sir":sir_df,"form20":f20_df,"classified":cl_df,"workers":w_df,"targets":t_df}


def save_district(name: str, dfs: dict):
    d = name.lower().replace(" ","_")
    dfs["sir"].to_csv(       OUT/f"sir_rolls_{d}.csv",          index=False)
    dfs["form20"].to_csv(    OUT/f"form20_{d}.csv",             index=False)
    dfs["classified"].to_csv(OUT/f"booths_classified_{d}.csv",  index=False)
    dfs["workers"].to_csv(   OUT/f"campaign_workers_{d}.csv",   index=False)
    dfs["targets"].to_csv(   OUT/f"daily_targets_{d}.csv",      index=False)


def gen_state_summary():
    rows = []
    for dn, meta in DISTRICTS.items():
        d   = dn.lower().replace(" ","_")
        pth = OUT / f"booths_classified_{d}.csv"
        if not pth.exists(): continue
        df  = pd.read_csv(pth)
        cats= df["booth_category"].value_counts()
        rows.append({"district":dn,"seats":meta["seats"],"pop2011":meta["pop2011"],
            "pre_sir_el":meta["pre_sir"],"sir_el":meta["sir"],"sir_adj":meta["sir_adj"],
            "adj_pct":round(meta["sir_adj"]/meta["sir"]*100,1),
            "muslim_pct":meta["muslim_pct"],"sc_pct":meta["sc_pct"],"st_pct":meta["st_pct"],
            "literacy":meta["literacy"],"female_ratio":meta["female_ratio"],
            "turnout_asm":meta["turnout_asm"],"turnout_ls":meta["turnout_ls"],
            "p1_base":round(meta["p1_base"]*100,1),"p2_base":round(meta["p2_base"]*100,1),
            "total_booths":len(df),"cat_A":cats.get("A",0),"cat_B":cats.get("B",0),
            "cat_C":cats.get("C",0),"cat_D":cats.get("D",0),
            "total_electors":df["total"].sum(),"total_adj":df["adj_count"].sum()})
    pd.DataFrame(rows).to_csv(OUT/"state_summary.csv",index=False)
    print(f"  State summary: {len(rows)} districts saved.")


def generate_district(district_name: str):
    """Callable directly from app.py."""
    if district_name not in DISTRICTS:
        raise ValueError(f"Unknown district: {district_name}")
    dfs = gen_district(district_name, DISTRICTS[district_name])
    save_district(district_name, dfs)
    gen_state_summary()

def generate_all():
    """Callable directly from app.py — all 23 districts."""
    for dn, dcfg in DISTRICTS.items():
        dfs = gen_district(dn, dcfg)
        save_district(dn, dfs)
    gen_state_summary()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", default=None)
    parser.add_argument("--all",      action="store_true")
    args = parser.parse_args()

    targets = list(DISTRICTS.keys()) if args.all else (
              [args.district] if args.district else ["Murshidabad"])

    for dn in targets:
        if dn not in DISTRICTS:
            print(f"Unknown district: {dn}"); continue
        print(f"Generating {dn}...", end=" ", flush=True)
        dfs  = gen_district(dn, DISTRICTS[dn])
        save_district(dn, dfs)
        cl   = dfs["classified"]
        cats = cl["booth_category"].value_counts()
        print(f"{len(cl):,} booths | {cl['total'].sum():,} electors | "
              f"A={cats.get('A',0)} B={cats.get('B',0)} C={cats.get('C',0)} D={cats.get('D',0)}")

    gen_state_summary()
    print("\nDone. Run: streamlit run app.py")
