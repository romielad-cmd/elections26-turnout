"""בדיקות חוסן: השוואה לקלפיות דומות (מגזר/יישוב) ו-Backtesting של כלל הסימון על בחירות קודמות.

רץ אחרי analyze.py. מחשב לכל מערכת יעד (2021, 2022, 2026) את הבסיס ההיסטורי באותה שיטת התאמה,
מפעיל את אותו כלל סימון, ובודק כמה קלפיות היו מסומנות בבחירות "רגילות" (שיעור התראות שווא).
מוסיף לשוניות ל-Excel ומעדכן את קובצי הדשבורד.
"""
import numpy as np
import pandas as pd
from openpyxl import load_workbook

NAMES = {21: "אפר' 2019", 22: "ספט' 2019", 23: "מרץ 2020", 24: "מרץ 2021", 25: "נוב' 2022", 26: "אוק' 2026"}
TARGETS = {24: [21, 22, 23], 25: [21, 22, 23, 24], 26: [21, 22, 23, 24, 25]}
BZB_RATIO, RIKUZ_RATIO = (0.75, 1.33), (0.5, 2.0)
YELLOW_PP, ORANGE_PP, RED_PP, RED_SD, MIN_BZB, MIN_HISTORY = 10.0, 15.0, 30.0, 3.0, 100, 3
# מפלגות ערביות וחרדיות לפי האותיות של כל מערכת (לסיווג קלפי בעיר מעורבת/יהודית)
ARAB = {24: ["עם", "ודעם"], 25: ["עם", "ום", "ד"], 26: ["עם", "ודם"]}
HAREDI = {24: ["ג", "שס"], 25: ["ג", "שס"], 26: ["ג", "שס", "זך", "רץ", "נר"]}
MIN_PEERS = 10          # מינימום קלפיות ביישוב כדי להשוות ליישוב; אחרת למגזר
MAD_FLOOR = 2.0         # רצפה לפיזור העמיתים (נק' אחוז), כדי שיישוב אחיד לא יפיק ציוני z מנופחים
TARGET_FALSE_RATE = 0.01  # שיעור התראות שווא רצוי בבחירות "רגילות"
PEER_MIN_EXCESS = 10.0  # עודף מינימלי מעל העמיתים (נק' אחוז)
XLSX = "ניתוח_שיעור_הצבעה_כנסת26.xlsx"
META = {"סמל ועדה", "ברזל", "שם ישוב", "סמל ישוב", "קלפי", "ריכוז", "שופט", "בזב", "מצביעים",
        "פסולים", "כשרים", "חיצוניות", "קלפי אחרת", "parent"}


def load(n):
    enc = "utf-8-sig" if n >= 25 else "cp1255"
    df = pd.read_csv(f"data/raw/k{n}_expb.csv", encoding=enc)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")].rename(columns={"מספר קלפי": "קלפי"})
    df = df[df["בזב"] > 0].copy()
    df["parent"] = df["קלפי"].astype(float).astype(int)
    return df


data = {n: load(n) for n in NAMES}
r22 = data[22].groupby(["סמל ישוב", "parent"])["ריכוז"].first()
data[21]["ריכוז"] = data[21].set_index(["סמל ישוב", "parent"]).index.map(r22.to_dict())


def units(df):
    s = ["בזב", "מצביעים"]
    return (df.groupby(["סמל ישוב", "parent"])[s].sum(),
            df.dropna(subset=["ריכוז"]).groupby(["סמל ישוב", "ריכוז"])[s].sum(),
            df.groupby("סמל ישוב")[s].sum())


U = {n: units(data[n]) for n in NAMES}


def ok(a, b, rng):
    return b > 0 and rng[0] <= a / b <= rng[1]


def baseline(target):
    """אותה שיטת התאמה כמו ב-analyze.py, לכל מערכת יעד."""
    cur = data[target].reset_index(drop=True).copy()
    cp, cr, _ = U[target]
    vals, lvls = {n: [] for n in TARGETS[target]}, {n: [] for n in TARGETS[target]}
    for city, parent, rik in zip(cur["סמל ישוב"], cur["parent"], cur["ריכוז"]):
        ref = cp.loc[(city, parent), "בזב"]
        rref = cr.loc[(city, rik), "בזב"] if (city, rik) in cr.index else None
        for n in TARGETS[target]:
            p, rk, c = U[n]
            lv, t = None, None
            if (city, parent) in p.index and ok(p.loc[(city, parent), "בזב"], ref, BZB_RATIO):
                v = p.loc[(city, parent)]; lv, t = "קלפי", v["מצביעים"] / v["בזב"]
            elif rref and (city, rik) in rk.index and ok(rk.loc[(city, rik), "בזב"], rref, RIKUZ_RATIO):
                v = rk.loc[(city, rik)]; lv, t = "ריכוז", v["מצביעים"] / v["בזב"]
            elif city in c.index:
                v = c.loc[city]; lv, t = "יישוב", v["מצביעים"] / v["בזב"]
            vals[n].append(t if t is None or t <= 1 else None)
            lvls[n].append(lv)
    h = pd.DataFrame({n: vals[n] for n in TARGETS[target]}, dtype=float)
    lv = pd.DataFrame(lvls)
    cur["avg"] = h.mean(axis=1)
    cur["sd"] = h.std(axis=1, ddof=0)
    cur["hist_n"] = h.notna().sum(axis=1)
    cur["level"] = np.select([(lv == "קלפי").sum(axis=1) >= 3, lv.isin(["קלפי", "ריכוז"]).sum(axis=1) >= 3],
                             ["קלפי", "ריכוז"], "יישוב")
    cur["now"] = cur["מצביעים"] / cur["בזב"]
    cur["dev"] = (cur["now"] - cur["avg"]) * 100
    cur["z_own"] = cur["dev"] / (cur["sd"] * 100).replace(0, np.nan)
    cur["added"] = cur["מצביעים"] - (cur["avg"] * cur["בזב"]).round()
    return cur


# סוג יישוב (קבוע בין מערכות) – מתוך הניתוח של 2026
c26 = pd.read_pickle("data/cur.pkl")
loc_type = c26.groupby("סמל ישוב")["סוג יישוב"].first()


def add_sector(df, target):
    df["loc_type"] = df["סמל ישוב"].map(loc_type).fillna("יהודי")
    valid = df["כשרים"].replace(0, np.nan)
    arab = df[[c for c in ARAB[target] if c in df]].sum(axis=1) / valid
    har = df[[c for c in HAREDI[target] if c in df]].sum(axis=1) / valid
    jm = df["loc_type"].isin(["יהודי", "עיר מעורבת"])
    sec = df["loc_type"].copy()
    sec[jm] = "יהודי"
    sec[jm & (har >= 0.6)] = "חרדי"
    sec[jm & (arab >= 0.5)] = "ערבי (בעיר מעורבת או יהודית)"
    df["sector"] = sec
    return df


def own_rule(df):
    """כלל הסימון הנוכחי: רצועה לפי שונות + מבחן מובהקות מול ההיסטוריה של הקלפי."""
    sd_ok = (df["z_own"] >= RED_SD) | (df["sd"] == 0)
    stat = sd_ok & (df["בזב"] >= MIN_BZB) & (df["hist_n"] >= MIN_HISTORY)
    band = np.select([df["dev"] >= RED_PP, df["dev"] >= ORANGE_PP, df["dev"] >= YELLOW_PP], ["אדום", "כתום", "צהוב"], "רגיל")
    df["band"] = np.where(stat, band, "רגיל")
    df["eligible"] = (df["בזב"] >= MIN_BZB) & (df["hist_n"] >= MIN_HISTORY) & df["dev"].notna()
    return df


def peers(df):
    """השוואה לקלפיות דומות: חציון ופיזור (MAD) של השונות באותו מגזר באותו יישוב (אם יש מספיק קלפיות),
    אחרת באותו מגזר בכל הארץ. כך קלפי ערבית בעיר מעורבת מושווית לקלפיות ערביות, לא לעיר כולה."""
    base = df[df["eligible"]]
    key = [base["סמל ישוב"], base["sector"]]
    city_n = base.groupby(key)["dev"].transform("size")
    med_city = base.groupby(key)["dev"].transform("median")
    mad_city = base.groupby(key)["dev"].transform(lambda s: (s - s.median()).abs().median())
    med_sec = base.groupby("sector")["dev"].transform("median")
    mad_sec = base.groupby("sector")["dev"].transform(lambda s: (s - s.median()).abs().median())
    use_city = city_n >= MIN_PEERS
    df["peer_group"] = pd.Series(np.where(use_city, "יישוב", "מגזר"), index=base.index)
    df.loc[base.index, "peer_med"] = np.where(use_city, med_city, med_sec)
    scale = np.maximum(1.4826 * np.where(use_city, mad_city, mad_sec), MAD_FLOOR)
    df.loc[base.index, "peer_scale"] = scale
    df["sector_med"] = df["sector"].map(base.groupby("sector")["dev"].median())
    df["excess_sector"] = df["dev"] - df["sector_med"]
    df["excess_peer"] = df["dev"] - df["peer_med"]
    df["z_peer"] = df["excess_peer"] / df["peer_scale"]
    return df


res = {}
for t in TARGETS:
    d = peers(own_rule(add_sector(baseline(t), t)))
    res[t] = d
    print(t, "done", len(d))

# בדיקת עקביות: הבסיס של 2026 כאן זהה לזה של analyze.py
chk = res[26].merge(c26[["סמל ישוב", "קלפי", "ממוצע 5 קודמות", "רצועת שונות", "עובר מבחן מובהקות", "מגזר"]],
                    on=["סמל ישוב", "קלפי"])
same_avg = np.isclose(chk["avg"], chk["ממוצע 5 קודמות"], equal_nan=True).all()
analyze_band = np.where(chk["עובר מבחן מובהקות"] == "כן", chk["רצועת שונות"], "רגיל")
same_band = (chk["band"].values == analyze_band).all()
same_sector = (chk["sector"].values == chk["מגזר"].values).mean()
print("consistency avg", same_avg, "band", same_band, "sector", same_sector)

# כיול: סף z מול עמיתים כך שבבחירות "רגילות" (2021, 2022) רק ~1% מהקלפיות הזכאיות מסומנות
pool = pd.concat([res[24].loc[res[24]["eligible"]], res[25].loc[res[25]["eligible"]]])
pool_ok = pool[pool["excess_peer"] >= PEER_MIN_EXCESS]
grid = np.arange(2.0, 8.01, 0.25)
rates = {round(z, 2): max(((res[t]["eligible"]) & (res[t]["excess_peer"] >= PEER_MIN_EXCESS) & (res[t]["z_peer"] >= z)).sum()
                         / res[t]["eligible"].sum() for t in (24, 25)) for z in grid}
Z_PEER = min(z for z, r in rates.items() if r <= TARGET_FALSE_RATE)
# כיול של כלל הסטיות תקן (מול ההיסטוריה של הקלפי בלבד) לאותו שיעור, לשם השוואה
sd_grid = np.arange(3.0, 30.01, 0.5)
sd_rates = {round(z, 1): max(((res[t]["eligible"]) & (res[t]["dev"] >= ORANGE_PP) & ((res[t]["z_own"] >= z) | (res[t]["sd"] == 0))).sum()
                             / res[t]["eligible"].sum() for t in (24, 25)) for z in sd_grid}
SD_CAL = min((z for z, r in sd_rates.items() if r <= TARGET_FALSE_RATE), default=None)
print("Z_PEER", Z_PEER, "SD_CAL", SD_CAL)

for t, d in res.items():
    d["peer_flag"] = d["eligible"] & (d["dev"] >= YELLOW_PP) & (d["excess_peer"] >= PEER_MIN_EXCESS) & (d["z_peer"] >= Z_PEER)
    d["combined"] = d["band"].isin(["אדום", "כתום"]) & d["peer_flag"]

# ---------- טבלת Backtest ----------
nat = {n: data[n]["מצביעים"].sum() / data[n]["בזב"].sum() for n in NAMES}
bt_rows = []
for t, d in res.items():
    e = d["eligible"]
    n_e = int(e.sum())
    row = {
        "מערכת יעד": NAMES[t], "target": t, "מערכות בהיסטוריה": len(TARGETS[t]),
        "שינוי ארצי (נק')": round((nat[t] - np.mean([nat[n] for n in TARGETS[t]])) * 100, 1),
        "קלפיות זכאיות": n_e,
        "כלל נוכחי – כתום+אדום": int(d["band"].isin(["אדום", "כתום"]).sum()),
        "כלל נוכחי – צהוב": int((d["band"] == "צהוב").sum()),
        "חריג מול עמיתים": int(d["peer_flag"].sum()),
        "משולב (כתום/אדום וגם חריג מול עמיתים)": int(d["combined"].sum()),
        "כלל נוכחי, שונות מעבר לשינוי הארצי – כתום+אדום": int((e & ((d["z_own"] >= RED_SD) | (d["sd"] == 0)) &
                                                       (d["dev"] - (nat[t] - np.mean([nat[n] for n in TARGETS[t]])) * 100 >= ORANGE_PP)).sum()),
    }
    for k in ["כלל נוכחי – כתום+אדום", "חריג מול עמיתים", "משולב (כתום/אדום וגם חריג מול עמיתים)",
              "כלל נוכחי, שונות מעבר לשינוי הארצי – כתום+אדום"]:
        row[f"% {k}"] = round(row[k] / n_e * 100, 2)
    bt_rows.append(row)
bt = pd.DataFrame(bt_rows)

# לפי מגזר
sec_rows = []
for t, d in res.items():
    for s, g in d[d["eligible"]].groupby("sector"):
        sec_rows.append({"מערכת יעד": NAMES[t], "target": t, "מגזר": s, "קלפיות זכאיות": len(g),
                         "שונות חציונית במגזר (נק')": round(g["dev"].median(), 1),
                         "כלל נוכחי – כתום+אדום": int(g["band"].isin(["אדום", "כתום"]).sum()),
                         "% כלל נוכחי": round(g["band"].isin(["אדום", "כתום"]).mean() * 100, 1),
                         "חריג מול עמיתים": int(g["peer_flag"].sum()),
                         "% חריג מול עמיתים": round(g["peer_flag"].mean() * 100, 2),
                         "משולב": int(g["combined"].sum())})
bt_sec = pd.DataFrame(sec_rows)

# ---------- 2026: עודף מעל רמת ההתראות הרגילה ----------
d26 = res[26]
e26 = int(d26["eligible"].sum())
base_rate_own = max(bt.loc[bt["target"] == t, "% כלל נוכחי – כתום+אדום"].item() for t in (24, 25)) / 100
base_rate_peer = max(bt.loc[bt["target"] == t, "% חריג מול עמיתים"].item() for t in (24, 25)) / 100

# התפלגות הקולות שנוספו בקלפיות החריגות במשולב (לפי התפלגות ההצבעה בקלפי)
PARTY_NAMES = dict(zip(pd.read_excel(XLSX, sheet_name="סיכום לפי מפלגה")["אותיות"],
                       pd.read_excel(XLSX, sheet_name="סיכום לפי מפלגה")["מפלגה"]))
pc26 = [c for c in data[26].columns if c not in META]
C = d26[d26["combined"]]
added_valid = C["added"] * C["כשרים"] / C["מצביעים"]
comb_party = C[pc26].div(C["כשרים"], axis=0).mul(added_valid, axis=0).sum().sort_values(ascending=False)
seat = 41422

summary_rows = {
    "קלפיות זכאיות ב-2026": e26,
    "כתום+אדום לפי הכלל הנוכחי": int(d26["band"].isin(["אדום", "כתום"]).sum()),
    "צפי התראות שווא לכלל הנוכחי (לפי השיעור המרבי ב-2021/2022)": round(base_rate_own * e26),
    "חריגות מול עמיתים ב-2026": int(d26["peer_flag"].sum()),
    "צפי התראות שווא לבדיקת העמיתים": round(base_rate_peer * e26),
    "משולב: כתום/אדום וגם חריג מול עמיתים": int(d26["combined"].sum()),
    "מצביעים שנוספו בקלפיות המשולבות": int(C["added"].sum()),
    "סף z מכויל מול עמיתים": Z_PEER,
    "סף סטיות תקן מכויל (היסטוריה בלבד) ל-1% התראות": SD_CAL,
}

with open("data/robustness.txt", "w", encoding="utf-8") as fh:
    print(bt.to_string(), file=fh)
    print(bt_sec.to_string(), file=fh)
    print(summary_rows, file=fh)
    print("rates", rates, file=fh)
    print("sd_rates", {k: v for k, v in sd_rates.items() if k <= 12}, file=fh)
    print(C.groupby("sector").agg(n=("dev", "size"), added=("added", "sum")).to_string(), file=fh)
    print((comb_party.head(10) / 1).round(0).to_string(), file=fh)
    print("consistency", same_avg, same_band, same_sector, file=fh)

with open("data/robustness.txt", "a", encoding="utf-8") as fh:
    print("\nTOP combined cities:", C.groupby("שם ישוב").agg(n=("dev", "size"), added=("added", "sum"), dev=("dev", "median"), peer=("peer_med", "median")).sort_values("n", ascending=False).head(20).to_string(), file=fh)
    print(C.sort_values("z_peer", ascending=False)[["שם ישוב", "קלפי", "sector", "level", "avg", "now", "dev", "peer_med", "z_peer", "added"]].head(25).to_string(), file=fh)
    print("level of combined:", C["level"].value_counts().to_dict(), file=fh)

# ---------- ביטחון: משולב רק כשההשוואה ההיסטורית היא ברמת קלפי או מקום קלפי ----------
for t, d in res.items():
    d["combined_hc"] = d["combined"] & (d["level"] != "יישוב")
for row in bt_rows:
    d = res[row["target"]]
    row["משולב, ביטחון גבוה/בינוני"] = int(d["combined_hc"].sum())
    row["% משולב, ביטחון גבוה/בינוני"] = round(d["combined_hc"].sum() / row["קלפיות זכאיות"] * 100, 2)
bt = pd.DataFrame(bt_rows)
for r in sec_rows:
    g = res[r["target"]]
    r["משולב, ביטחון גבוה/בינוני"] = int((g["combined_hc"] & (g["sector"] == r["מגזר"])).sum())
bt_sec = pd.DataFrame(sec_rows)
H = d26[d26["combined_hc"]]
hv = H["added"] * H["כשרים"] / H["מצביעים"]
hc_party = H[pc26].div(H["כשרים"], axis=0).mul(hv, axis=0).sum().sort_values(ascending=False)
base_rate_comb = max(bt.loc[bt["target"] == t, "% משולב (כתום/אדום וגם חריג מול עמיתים)"].item() for t in (24, 25)) / 100
base_rate_hc = max(bt.loc[bt["target"] == t, "% משולב, ביטחון גבוה/בינוני"].item() for t in (24, 25)) / 100

summary = pd.DataFrame([
    ("קלפיות זכאיות ב-2026 (בזב 100+, 3 מערכות בהיסטוריה לפחות)", e26, ""),
    ("כתום+אדום לפי הכלל הנוכחי (מול ההיסטוריה של הקלפי)", int(d26["band"].isin(["אדום", "כתום"]).sum()),
     f"צפי התראות שווא: {round(base_rate_own * e26)}"),
    ("חריגות מול קלפיות דומות (אותו מגזר, אותו יישוב או ארצי)", int(d26["peer_flag"].sum()),
     f"צפי התראות שווא: {round(base_rate_peer * e26)}"),
    ("משולב: כתום/אדום וגם חריג מול קלפיות דומות", int(d26["combined"].sum()),
     f"צפי התראות שווא: {round(base_rate_comb * e26)}"),
    ("משולב, וגם ההשוואה ההיסטורית ברמת קלפי או מקום קלפי", int(d26["combined_hc"].sum()),
     f"צפי התראות שווא: {round(base_rate_hc * e26)}"),
    ("מצביעים שנוספו – משולב", int(C["added"].sum()), f"כ-{C['added'].sum() * 0.99 / seat:.2f} מנדטים"),
    ("מצביעים שנוספו – משולב בביטחון גבוה/בינוני", int(H["added"].sum()), f"כ-{H['added'].sum() * 0.99 / seat:.2f} מנדטים"),
    ("סף z מכויל מול קלפיות דומות (1% התראות ב-2021/2022)", Z_PEER, "בנוסף: עודף של 10 נק' לפחות מעל החציון של הקבוצה"),
    ("סף סטיות תקן מכויל, היסטוריה בלבד (1% התראות)", SD_CAL, "הסף הנוכחי, 3, כבר עומד ביעד של 1%"),
], columns=["מדד", "ערך", "הערה"])

# ---------- Excel ----------
cols26 = {"שם ישוב": "שם ישוב", "קלפי": "קלפי", "sector": "מגזר", "level": "רמת השוואה", "בזב": "בזב",
          "avg": "ממוצע היסטורי", "now": "שיעור 2026", "dev": "שונות (נק')", "z_own": "סטיות תקן מול ההיסטוריה",
          "band": "סימון (כלל נוכחי)", "peer_group": "קבוצת השוואה", "peer_med": "שונות חציונית בקבוצה",
          "excess_peer": "עודף מעל הקבוצה (נק')", "z_peer": "z מול הקבוצה", "peer_flag": "חריג מול קלפיות דומות",
          "combined": "משולב", "combined_hc": "משולב בביטחון גבוה/בינוני", "added": "מצביעים שנוספו"}
p26 = d26[list(cols26)].rename(columns=cols26)
p26[["ממוצע היסטורי", "שיעור 2026"]] *= 100
for c in ["חריג מול קלפיות דומות", "משולב", "משולב בביטחון גבוה/בינוני"]:
    p26[c] = np.where(p26[c], "כן", "לא")
p26 = p26.round(2).sort_values("z מול הקבוצה", ascending=False)
try:
    with pd.ExcelWriter(XLSX, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
        summary.to_excel(xw, sheet_name="חוסן – שורה תחתונה", index=False)
        bt.drop(columns=["target"]).to_excel(xw, sheet_name="Backtest", index=False)
        bt_sec.drop(columns=["target"]).to_excel(xw, sheet_name="Backtest לפי מגזר", index=False)
        p26.to_excel(xw, sheet_name="השוואה לקלפיות דומות", index=False)
    wb = load_workbook(XLSX)
    for name in ("חוסן – שורה תחתונה", "Backtest", "Backtest לפי מגזר", "השוואה לקלפיות דומות"):
        wb[name].sheet_view.rightToLeft = True
        wb[name].freeze_panes = "B2"
    wb.save(XLSX)
except PermissionError:
    print("!! קובץ ה-Excel פתוח בתוכנה אחרת – הלשוניות החדשות לא נכתבו. סגור אותו והרץ שוב.")

# ---------- קובצי הדשבורד ----------
fb = pd.read_csv("data/dash/flagged_ballots.csv", dtype={"kalpi": str})
d26["id"] = d26["סמל ישוב"].astype(int).astype(str) + "-" + d26["קלפי"].map(lambda k: f"{k:g}")
extra = d26.set_index("id")[["excess_peer", "z_peer", "peer_flag", "combined_hc"]]
fb = fb.drop(columns=[c for c in ["excess_peer", "z_peer", "peer"] if c in fb]).join(extra, on="id")
fb["excess_peer"] = fb["excess_peer"].round(1)
fb["z_peer"] = fb["z_peer"].round(1)
fb["peer"] = np.select([fb["combined_hc"] == True, fb["peer_flag"] == True], ["כן, בביטחון", "כן"], "לא")
fb.drop(columns=["peer_flag", "combined_hc"]).to_csv("data/dash/flagged_ballots.csv", index=False, encoding="utf-8")
pd.DataFrame({
    "election": bt["מערכת יעד"], "target": bt["target"], "nat_change": bt["שינוי ארצי (נק')"], "eligible": bt["קלפיות זכאיות"],
    "own": bt["כלל נוכחי – כתום+אדום"], "own_pct": bt["% כלל נוכחי – כתום+אדום"],
    "peer": bt["חריג מול עמיתים"], "peer_pct": bt["% חריג מול עמיתים"],
    "comb": bt["משולב (כתום/אדום וגם חריג מול עמיתים)"], "comb_pct": bt["% משולב (כתום/אדום וגם חריג מול עמיתים)"],
    "hc": bt["משולב, ביטחון גבוה/בינוני"], "hc_pct": bt["% משולב, ביטחון גבוה/בינוני"],
}).to_csv("data/dash/backtest.csv", index=False, encoding="utf-8")
s26 = bt_sec[bt_sec["target"] == 26]
pd.DataFrame({"sector": s26["מגזר"], "eligible": s26["קלפיות זכאיות"], "median_dev": s26["שונות חציונית במגזר (נק')"],
              "own": s26["כלל נוכחי – כתום+אדום"], "own_pct": s26["% כלל נוכחי"],
              "peer": s26["חריג מול עמיתים"], "comb": s26["משולב"], "hc": s26["משולב, ביטחון גבוה/בינוני"]}).to_csv(
    "data/dash/robust_sector.csv", index=False, encoding="utf-8")
pd.DataFrame([{"eligible": e26, "own": int(d26["band"].isin(["אדום", "כתום"]).sum()), "own_exp": round(base_rate_own * e26),
               "peer": int(d26["peer_flag"].sum()), "peer_exp": round(base_rate_peer * e26),
               "comb": int(d26["combined"].sum()), "comb_exp": round(base_rate_comb * e26),
               "hc": int(d26["combined_hc"].sum()), "hc_exp": round(base_rate_hc * e26),
               "comb_added": int(C["added"].sum()), "hc_added": int(H["added"].sum()),
               "z_peer": Z_PEER, "peer_min_excess": PEER_MIN_EXCESS, "min_peers": MIN_PEERS}]).to_csv(
    "data/dash/robust_summary.csv", index=False, encoding="utf-8")

with open("data/robustness.txt", "a", encoding="utf-8") as fh:
    print("\n", summary.to_string(), file=fh)
    print(bt[["מערכת יעד", "משולב, ביטחון גבוה/בינוני", "% משולב, ביטחון גבוה/בינוני"]].to_string(), file=fh)
    print(H.groupby("sector").agg(n=("dev", "size"), added=("added", "sum")).to_string(), file=fh)
    print(H[["שם ישוב", "קלפי", "sector", "level", "avg", "now", "dev", "peer_med", "z_peer", "added"]].sort_values("z_peer", ascending=False).to_string(), file=fh)
    print(hc_party.head(8).round(0).to_string(), file=fh)
