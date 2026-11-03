"""ניתוח קפיצות חריגות בשיעור ההצבעה לפי קלפי – כנסת 26 מול ממוצע כנסות 21–25."""
import json
import math

import numpy as np
import pandas as pd

# ---------- פרמטרים ----------
PRIOR = [21, 22, 23, 24, 25]
CUR = 26
ELECTION_NAMES = {21: "אפר' 2019", 22: "ספט' 2019", 23: "מרץ 2020", 24: "מרץ 2021", 25: "נוב' 2022", 26: "אוק' 2026"}
YELLOW_PP = 10.0       # צהוב: 10 עד 15 נק' אחוז
ORANGE_PP = 15.0       # כתום: 15 עד 30 נק' אחוז
RED_PP = 30.0          # אדום: 30 נק' אחוז ומעלה
BANDS = ["אדום", "כתום", "צהוב"]
RED_SD = 3.0           # מבחן מובהקות: מינימום סטיות תקן מעל הממוצע ההיסטורי
MIN_BZB = 100          # מבחן מובהקות: בזב מינימלי
MIN_HISTORY = 3        # מבחן מובהקות: מינימום מערכות בהיסטוריה
ARAB_PARTIES_26 = ["עם", "ודם"]
HAREDI_PARTIES_26 = ["ג", "שס", "זך", "רץ", "נר"]
ARAB_BALLOT_SHARE = 0.5    # קלפי בעיר מעורבת/יהודית שבה רוב הקולות למפלגות ערביות
HAREDI_BALLOT_SHARE = 0.6  # קלפי יהודית שבה רוב גדול לחרדים
DRUZE = {"דאלית אל-כרמל", "עספיא", "ירכא", "גולס", "בית גן", "חורפיש", "כסרא-סמיע", "סאגור", "יאנוח-גת",
         "בוקעאתא", "מגדל שמס", "מסעדה", "עין קנייא", "פקיעין (בוקייעה)", "מגאר"}
BEDOUIN_NORTH = {"בסמת טבעון", "זרזיר", "כעביה-טבאש-חגאגרה", "ביר אל-מכסור", "שבלי - אום אל-גנם", "טובא-זנגריה",
                 "ראס עלי", "חואלד", "אבטין", "סואעד (חמירה)", "חמאם", "מנשית זבדה", "רומת הייב", "ערב אל נעים",
                 "כמאנה", "עוזייר", "דמיידה", "חוסנייה", "ראס אל-עין", "אל-עזי", "סלמה", "עראמשה", "בועיינה-נוגידאת"}
BZB_RATIO = (0.75, 1.33)  # יציבות בזב בין מערכות כדי לקבל התאמה ברמת קלפי
RIKUZ_RATIO = (0.5, 2.0)  # ריכוז (מקום קלפי) – מותר גידול או קיטון גדולים יותר, כי זו אותה שכונה
META = {"סמל ועדה", "ברזל", "שם ישוב", "סמל ישוב", "קלפי", "ריכוז", "שופט", "בזב", "מצביעים",
        "פסולים", "כשרים", "חיצוניות", "קלפי אחרת"}

PARTY_NAMES_26 = {
    "רק": "ביחד (בנט)", "דרך": "ישר! (איזנקוט)", "צדק": "שרשר", "ד": "השותפות לכולם", "צף": "הפיראטים",
    "ך": "עמך ישראל (וינטר)", "י": "ישראל תחילה (השכל)", "ה": "גן עדן", "קה": "קול הנשים",
    "בד": "ביחד נצליח", "ל": "ישראל ביתנו", "קץ": "משפט צדק", "נף": "שמע (גולדמן)",
    "ב": "עוצמה יהודית", "קך": "סדר חדש", "די": "המילואימניקים (הנדל-זליכה)", "אמת": "הדמוקרטים",
    "עם": "רע\"ם", "שס": "ש\"ס", "זך": "הציבור החרדי", "פה": "אני ואתה", "זץ": "ברית עולם",
    "נקי": "התיקון לשיטת הבחירות", "יק": "גה\"ת", "ז": "בטח", "בקר": "אורות השחר", "נץ": "ביטחון אישי",
    "נר": "צבע שחור", "מחל": "הליכוד", "כן": "כחול לבן", "ט": "הציונות הדתית", "צבי": "תנועת אחי",
    "בי": "צומת בית ישראל", "ק": "תקומה", "ודם": "הרשימה המשותפת", "רץ": "הקהל",
    "ג": "יהדות התורה", "ני": "נעם",
}
BLOCS_26 = {"קואליציה": ["מחל", "שס", "ג", "ב", "ט"],
            "אופוזיציה": ["רק", "דרך", "ל", "אמת", "כן", "די"],
            "מפלגות ערביות": ["עם", "ודם"]}
BLOCS_25 = {"קואליציה": ["מחל", "שס", "ג", "ט"],
            "אופוזיציה": ["פה", "כן", "ל", "אמת", "מרצ"],
            "מפלגות ערביות": ["עם", "ום", "ד"]}
MANUAL_COORDS = {3400: (31.5326, 35.0998)}  # חברון – חסר בקובץ הלמ"ס


# ---------- טעינה ----------
def load(n):
    enc = "utf-8-sig" if n >= 25 else "cp1255"
    df = pd.read_csv(f"data/raw/k{n}_expb.csv", encoding=enc)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")].rename(columns={"מספר קלפי": "קלפי"})
    df = df[df["בזב"] > 0].copy()  # מעטפות כפולות/חיצוניות – ללא בזב
    df["parent"] = df["קלפי"].astype(float).astype(int)
    df["split"] = (df["קלפי"] % 1).round(3) > 0
    return df


def party_cols(df):
    return [c for c in df.columns if c not in META and c not in ("parent", "split")]


data = {n: load(n) for n in PRIOR + [CUR]}

# ריכוז לכנסת 21 (חסר בקובץ) – לפי מספר קלפי מכנסת 22
r22 = data[22].groupby(["סמל ישוב", "parent"])["ריכוז"].first()
data[21]["ריכוז"] = data[21].set_index(["סמל ישוב", "parent"]).index.map(r22.to_dict())


def units(df):
    s = ["בזב", "מצביעים"]
    parent = df.groupby(["סמל ישוב", "parent"])[s].sum()
    rikuz = df.dropna(subset=["ריכוז"]).groupby(["סמל ישוב", "ריכוז"])[s].sum()
    city = df.groupby("סמל ישוב")[s].sum()
    return parent, rikuz, city


U = {n: units(data[n]) for n in PRIOR + [CUR]}


def ok_ratio(a, b, rng=BZB_RATIO):
    return b > 0 and rng[0] <= a / b <= rng[1]


# ---------- בסיס היסטורי לכל קלפי בכנסת 26 ----------
cur = data[CUR].reset_index(drop=True)
cur_parent, cur_rikuz, _ = U[CUR]
rows = []
for r in cur.itertuples(index=False):
    city, parent, rik = r[cur.columns.get_loc("סמל ישוב")], r.parent, r[cur.columns.get_loc("ריכוז")]
    ref_bzb = cur_parent.loc[(city, parent), "בזב"]
    rik_bzb = cur_rikuz.loc[(city, rik), "בזב"] if (city, rik) in cur_rikuz.index else None
    rec = {}
    for n in PRIOR:
        p, rk, c = U[n]
        level, t = None, None
        if (city, parent) in p.index and ok_ratio(p.loc[(city, parent), "בזב"], ref_bzb):
            v = p.loc[(city, parent)]
            level, t = "קלפי", v["מצביעים"] / v["בזב"]
        elif rik_bzb and (city, rik) in rk.index and ok_ratio(rk.loc[(city, rik), "בזב"], rik_bzb, RIKUZ_RATIO):
            v = rk.loc[(city, rik)]
            level, t = "ריכוז", v["מצביעים"] / v["בזב"]
        elif city in c.index:
            v = c.loc[city]
            level, t = "יישוב", v["מצביעים"] / v["בזב"]
        rec[n] = (level, t if t is None or t <= 1 else None)  # ערך מעל 100% בקובץ המקור – לא תקין, לא נכנס לממוצע
    rows.append(rec)

for n in PRIOR:
    cur[f"שיעור {ELECTION_NAMES[n]}"] = [r[n][1] for r in rows]
    cur[f"רמה {n}"] = [r[n][0] for r in rows]

tcols = [f"שיעור {ELECTION_NAMES[n]}" for n in PRIOR]
cur["ממוצע 5 קודמות"] = cur[tcols].mean(axis=1)
cur["סטיית תקן"] = cur[tcols].std(axis=1, ddof=0)
cur["מס' מערכות בהיסטוריה"] = cur[tcols].notna().sum(axis=1)
lvl = cur[[f"רמה {n}" for n in PRIOR]]
cur["התאמות ברמת קלפי"] = (lvl == "קלפי").sum(axis=1)
cur["רמת השוואה"] = np.select(
    [(lvl == "קלפי").sum(axis=1) >= 3, (lvl.isin(["קלפי", "ריכוז"])).sum(axis=1) >= 3],
    ["קלפי", "ריכוז"], "יישוב")
cur[f"שיעור {ELECTION_NAMES[CUR]}"] = cur["מצביעים"] / cur["בזב"]
cur["שונות (נק' אחוז)"] = (cur[f"שיעור {ELECTION_NAMES[CUR]}"] - cur["ממוצע 5 קודמות"]) * 100
cur["יחס נוכחי/ממוצע"] = cur[f"שיעור {ELECTION_NAMES[CUR]}"] / cur["ממוצע 5 קודמות"]
cur["סטיות תקן מעל הממוצע"] = cur["שונות (נק' אחוז)"] / (cur["סטיית תקן"] * 100).replace(0, np.nan)
cur["מצביעים צפויים"] = (cur["ממוצע 5 קודמות"] * cur["בזב"]).round()
cur["מצביעים שנוספו"] = cur["מצביעים"] - cur["מצביעים צפויים"]

# שינוי ארצי – להקשר
nat = {n: U[n][2]["מצביעים"].sum() / U[n][2]["בזב"].sum() for n in PRIOR + [CUR]}
nat_avg = np.mean([nat[n] for n in PRIOR])
cur["שונות מעבר לשינוי הארצי"] = cur["שונות (נק' אחוז)"] - (nat[CUR] - nat_avg) * 100


# ---------- מגזר ----------
cbs = pd.read_excel("data/raw/bycode2024.xlsx").set_index("סמל יישוב")
pc26 = party_cols(data[CUR])
valid = cur["כשרים"].replace(0, np.nan)
cur["חלק מפלגות ערביות"] = cur[ARAB_PARTIES_26].sum(axis=1) / valid
cur["חלק מפלגות חרדיות"] = cur[HAREDI_PARTIES_26].sum(axis=1) / valid


def locality_sector(code, name):
    cbs_name = cbs["שם יישוב"].get(code, name)
    rel, nafa = cbs["דת יישוב"].get(code), cbs["שם נפה"].get(code)
    if str(name).startswith("מחנה "):
        return "מחנה צה\"ל"
    if cbs_name in DRUZE:
        return "דרוזי"
    if rel == 3 or (rel == 2 and nafa == "באר שבע"):
        return "בדואי (נגב)"
    if cbs_name in BEDOUIN_NORTH:
        return "בדואי (צפון)"
    if rel == 2:
        return "ערבי"
    if rel == 4:
        return "עיר מעורבת"
    return "יהודי"


cur["סוג יישוב"] = [locality_sector(c, n) for c, n in zip(cur["סמל ישוב"], cur["שם ישוב"])]
sector = cur["סוג יישוב"].copy()
jewish_or_mixed = sector.isin(["יהודי", "עיר מעורבת"])
arab_ballot = jewish_or_mixed & (cur["חלק מפלגות ערביות"] >= ARAB_BALLOT_SHARE)
sector[arab_ballot] = "ערבי (בעיר מעורבת או יהודית)"
haredi_ballot = jewish_or_mixed & ~arab_ballot & (cur["חלק מפלגות חרדיות"] >= HAREDI_BALLOT_SHARE)
sector[haredi_ballot] = "חרדי"
sector[jewish_or_mixed & ~arab_ballot & ~haredi_ballot] = "יהודי"
cur["מגזר"] = sector
cur["רמת ביטחון"] = cur["רמת השוואה"].map({"קלפי": "גבוהה", "ריכוז": "בינונית", "יישוב": "נמוכה"})

# ---------- רצועות שונות ----------
dev = cur["שונות (נק' אחוז)"]
band = np.select([dev >= RED_PP, dev >= ORANGE_PP, dev >= YELLOW_PP], BANDS, "רגיל")
band = np.where(dev.isna(), "ללא היסטוריה", band)
cur["רצועת שונות"] = band
sd_ok = (cur["סטיות תקן מעל הממוצע"] >= RED_SD) | (cur["סטיית תקן"] == 0)
stat_ok = sd_ok & (cur["בזב"] >= MIN_BZB) & (cur["מס' מערכות בהיסטוריה"] >= MIN_HISTORY)
cur["עובר מבחן מובהקות"] = np.where(stat_ok, "כן", "לא")
in_band = cur["רצועת שונות"].isin(BANDS)
cur["סימון"] = np.where(in_band & ~stat_ok, cur["רצועת שונות"] + " (לא מובהק)", cur["רצועת שונות"])
flagged = cur["סימון"].isin(BANDS)

# ---------- התפלגות הקולות שנוספו ----------
R = cur[flagged].copy()
added_valid = R["מצביעים שנוספו"] * R["כשרים"] / R["מצביעים"]
share = R[pc26].div(R["כשרים"], axis=0)
method_a = share.mul(added_valid, axis=0)  # שיטה א' – לפי התפלגות הקלפי

# שיטה ב' – לפי גושים: קולות בפועל פחות צפי (חלק הגוש ב-2022 × מצביעים כשרים צפויים)
d25 = data[25]
pc25 = party_cols(d25)
blocs25 = pd.DataFrame({b: d25[[c for c in cols if c in pc25]].sum(axis=1) for b, cols in BLOCS_25.items()})
blocs25[["סמל ישוב", "parent", "ריכוז", "כשרים"]] = d25[["סמל ישוב", "parent", "ריכוז", "כשרים"]]
bp = blocs25.groupby(["סמל ישוב", "parent"]).sum(numeric_only=True)
br = blocs25.groupby(["סמל ישוב", "ריכוז"]).sum(numeric_only=True)
bc = blocs25.groupby("סמל ישוב").sum(numeric_only=True)
bloc_names = list(BLOCS_26) + ["אחר"]
method_b = []
for idx, r in R.iterrows():
    city, lvl25 = r["סמל ישוב"], r["רמה 25"]
    if lvl25 == "קלפי":
        src = bp.loc[(city, r["parent"])]
    elif lvl25 == "ריכוז":
        src = br.loc[(city, r["ריכוז"])]
    else:
        src = bc.loc[city]
    sh = {b: src[b] / src["כשרים"] for b in BLOCS_25}
    sh["אחר"] = 1 - sum(sh.values())
    exp_valid = r["מצביעים צפויים"] * r["כשרים"] / r["מצביעים"]
    actual = {b: r[[c for c in cols if c in pc26]].sum() for b, cols in BLOCS_26.items()}
    actual["אחר"] = r["כשרים"] - sum(actual.values())
    method_b.append({b: actual[b] - sh[b] * exp_valid for b in bloc_names})
method_b = pd.DataFrame(method_b, index=R.index)

tot = data[CUR][pc26].sum()
passed = tot[tot / tot.sum() >= 0.0325]
seat = passed.sum() / 120

bloc_of = {c: b for b, cols in BLOCS_26.items() for c in cols}
R_band = R["סימון"]
party_summary = pd.DataFrame({
    "מפלגה": [PARTY_NAMES_26.get(c, c) for c in pc26], "אותיות": pc26,
    "גוש": [bloc_of.get(c, "אחר") for c in pc26],
    **{f"נוספו – {b}": method_a[R_band == b].sum().values for b in BANDS},
    "סה\"כ קולות ארצי": tot.values,
})
party_summary["נוספו – סה\"כ"] = party_summary[[f"נוספו – {b}" for b in BANDS]].sum(axis=1)
party_summary["מנדטים משוערים"] = party_summary["נוספו – סה\"כ"] / seat
party_summary = party_summary.sort_values("נוספו – סה\"כ", ascending=False)

bloc_rows = []
for bl in bloc_names:
    cols_bl = [c for c in pc26 if bloc_of.get(c, "אחר") == bl]
    row = {"גוש": bl}
    for b in BANDS:
        row[f"שיטה א' – {b}"] = method_a.loc[R_band == b, cols_bl].sum().sum()
        row[f"שיטה ב' – {b}"] = method_b.loc[R_band == b, bl].sum()
    bloc_rows.append(row)
bloc_summary = pd.DataFrame(bloc_rows)

sector_summary = cur.groupby("מגזר").agg(
    קלפיות=("קלפי", "size"), בזב=("בזב", "sum"), מצביעים=("מצביעים", "sum"),
    ממוצע_קודמות=("ממוצע 5 קודמות", "mean"), שיעור_2026=(f"שיעור {ELECTION_NAMES[CUR]}", "mean"))
for b in BANDS:
    sector_summary[f"קלפיות {b}"] = R[R_band == b].groupby("מגזר").size()
    sector_summary[f"נוספו {b}"] = R[R_band == b].groupby("מגזר")["מצביעים שנוספו"].sum()
sector_summary = sector_summary.fillna(0)
# שיעור הצבעה משוקלל לפי מגזר: 5 קודמות (לפי בסיס הקלפיות) מול 2026
sector_summary["שיעור ממוצע 5 קודמות (משוקלל)"] = cur.groupby("מגזר").apply(
    lambda g: (g["ממוצע 5 קודמות"] * g["בזב"]).sum() / g.loc[g["ממוצע 5 קודמות"].notna(), "בזב"].sum())
sector_summary["שיעור 2026 (משוקלל)"] = sector_summary["מצביעים"] / sector_summary["בזב"]
sector_summary = sector_summary.drop(columns=["ממוצע_קודמות", "שיעור_2026"]).sort_values("קלפיות", ascending=False)


# ---------- קואורדינטות ----------
def itm_to_wgs84(x, y):
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    k0, lon0, lat0 = 1.0000067, math.radians(35.2045169444), math.radians(31.7343936111)
    fe, fn = 219529.584, 626907.390

    def mer(phi):
        e4, e6 = e2 * e2, e2 ** 3
        return a * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
                    + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi) - (35 * e6 / 3072) * math.sin(6 * phi))

    m = mer(lat0) + (y - fn) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu) + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu) \
        + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
    ep2 = e2 / (1 - e2)
    c1, t1 = ep2 * math.cos(phi1) ** 2, math.tan(phi1) ** 2
    n1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)
    r1 = a * (1 - e2) / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
    d = (x - fe) / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (d ** 2 / 2 - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4 / 24)
    lon = lon0 + (d - (1 + 2 * t1 + c1) * d ** 3 / 6) / math.cos(phi1)
    return math.degrees(lat), math.degrees(lon)


coords = {}
for code, xy in cbs["קואורדינטות"].items():
    if pd.notna(xy):
        s = f"{int(xy):012d}"
        coords[int(code)] = itm_to_wgs84(int(s[:6]), int(s[6:]))
coords.update(MANUAL_COORDS)
cur["lat"] = cur["סמל ישוב"].map(lambda c: coords.get(int(c), (None, None))[0])
cur["lon"] = cur["סמל ישוב"].map(lambda c: coords.get(int(c), (None, None))[1])
R[["lat", "lon"]] = cur.loc[R.index, ["lat", "lon"]]
cur.to_pickle("data/cur.pkl")

# ---------- ייצוא ל-Excel ----------
base_cols = ["שם ישוב", "סמל ישוב", "קלפי", "ריכוז", "מגזר", "סוג יישוב", "בזב", "מצביעים", "כשרים"] + tcols + [
    "ממוצע 5 קודמות", "סטיית תקן", f"שיעור {ELECTION_NAMES[CUR]}", "שונות (נק' אחוז)", "רצועת שונות",
    "עובר מבחן מובהקות", "סימון", "יחס נוכחי/ממוצע", "סטיות תקן מעל הממוצע", "שונות מעבר לשינוי הארצי",
    "מצביעים צפויים", "מצביעים שנוספו", "רמת השוואה", "רמת ביטחון", "התאמות ברמת קלפי", "מס' מערכות בהיסטוריה",
    "חלק מפלגות ערביות", "חלק מפלגות חרדיות"]
full = cur[base_cols].sort_values("שונות (נק' אחוז)", ascending=False)
pct_cols = tcols + ["ממוצע 5 קודמות", "סטיית תקן", f"שיעור {ELECTION_NAMES[CUR]}", "חלק מפלגות ערביות", "חלק מפלגות חרדיות"]
full_x = full.copy()
full_x[pct_cols] = (full_x[pct_cols] * 100).round(1)
full_x = full_x.round(2)

flag_x = full_x[full_x["סימון"].isin(BANDS)].copy()
flag_x = flag_x.join(R[pc26].rename(columns=lambda c: PARTY_NAMES_26.get(c, c)))
flag_x = flag_x.join(method_a.round(1).rename(columns=lambda c: "נוסף ל" + PARTY_NAMES_26.get(c, c)))

params = pd.DataFrame({
    "פרמטר": ["צהוב – שונות (נק' אחוז)", "כתום – שונות (נק' אחוז)", "אדום – שונות (נק' אחוז)",
              "מבחן מובהקות – סטיות תקן מינימום", "מבחן מובהקות – בזב מינימלי", "מבחן מובהקות – מינימום מערכות בהיסטוריה",
              "טווח יציבות בזב להתאמה – קלפי", "טווח יציבות בזב להתאמה – ריכוז", "מגזר: קלפי ערבית בעיר מעורבת/יהודית – חלק מפלגות ערביות מינימלי",
              "מגזר: קלפי חרדית – חלק מפלגות חרדיות מינימלי",
              "שיעור הצבעה ארצי (ללא מעטפות כפולות) – ממוצע 5 קודמות", f"שיעור הצבעה ארצי (ללא מעטפות כפולות) – {ELECTION_NAMES[CUR]}",
              "קולות למנדט (משוער)"],
    "ערך": [f"{YELLOW_PP:g}–{ORANGE_PP:g}", f"{ORANGE_PP:g}–{RED_PP:g}", f"{RED_PP:g}+", RED_SD, MIN_BZB, MIN_HISTORY,
            f"{BZB_RATIO[0]}–{BZB_RATIO[1]}", f"{RIKUZ_RATIO[0]}–{RIKUZ_RATIO[1]}", ARAB_BALLOT_SHARE, HAREDI_BALLOT_SHARE,
            round(nat_avg * 100, 2), round(nat[CUR] * 100, 2), round(seat)],
})
sec_x = sector_summary.copy()
sec_x[["שיעור ממוצע 5 קודמות (משוקלל)", "שיעור 2026 (משוקלל)"]] *= 100
FILLS = {"אדום": "F4B6B6", "כתום": "F9D3A8", "צהוב": "FBEFA8"}
with pd.ExcelWriter("ניתוח_שיעור_הצבעה_כנסת26.xlsx", engine="openpyxl") as xw:
    params.to_excel(xw, sheet_name="פרמטרים", index=False)
    full_x.to_excel(xw, sheet_name="כל הקלפיות", index=False)
    flag_x.to_excel(xw, sheet_name="קלפיות מסומנות", index=False)
    party_summary.round(1).to_excel(xw, sheet_name="סיכום לפי מפלגה", index=False)
    bloc_summary.round(0).to_excel(xw, sheet_name="סיכום לפי גוש", index=False)
    sec_x.round(1).to_excel(xw, sheet_name="סיכום לפי מגזר")
    from openpyxl.styles import PatternFill
    for ws in xw.book.worksheets:
        ws.sheet_view.rightToLeft = True
        ws.freeze_panes = "B2"
        head = [c.value for c in ws[1]]
        if "סימון" in head:
            ci = head.index("סימון")
            for row in ws.iter_rows(min_row=2):
                v = str(row[ci].value or "")
                key = v.split(" ")[0]
                if key in FILLS:
                    fill = PatternFill("solid", fgColor=FILLS[key] if v in FILLS else "EEEEEE")
                    row[ci].fill = fill

# ---------- קבצי נתונים ללוח המחוונים ----------
import os

os.makedirs("data/dash", exist_ok=True)
fmt_k = lambda k: f"{k:g}"
flag_ds = pd.DataFrame({
    "id": R["סמל ישוב"].astype(int).astype(str) + "-" + R["קלפי"].map(fmt_k),
    "city": R["שם ישוב"], "kalpi": R["קלפי"].map(fmt_k), "sector": R["מגזר"], "band": R["סימון"],
    "bzb": R["בזב"], "voters": R["מצביעים"],
    **{f"t{n}": (R[f"שיעור {ELECTION_NAMES[n]}"] * 100).round(1) for n in PRIOR},
    "avg": (R["ממוצע 5 קודמות"] * 100).round(1), "now": (R[f"שיעור {ELECTION_NAMES[CUR]}"] * 100).round(1),
    "dev": R["שונות (נק' אחוז)"].round(1), "sd": R["סטיות תקן מעל הממוצע"].round(1),
    "added": R["מצביעים שנוספו"].astype(int), "level": R["רמת השוואה"], "conf": R["רמת ביטחון"],
    "lat": R["lat"].round(4), "lon": R["lon"].round(4),
    "top_party": method_a.idxmax(axis=1).map(lambda c: PARTY_NAMES_26.get(c, c)),
}).sort_values("dev", ascending=False)
flag_ds.to_csv("data/dash/flagged_ballots.csv", index=False, encoding="utf-8")

EN = {"אדום": "red", "כתום": "orange", "צהוב": "yellow"}
ps = party_summary[party_summary["נוספו – סה\"כ"] >= 1]
pd.DataFrame({"party": ps["מפלגה"], "bloc": ps["גוש"],
              **{f"add_{EN[b]}": ps[f"נוספו – {b}"].round().astype(int) for b in BANDS}}).to_csv(
    "data/dash/party_added.csv", index=False, encoding="utf-8")
pd.DataFrame({"bloc": bloc_summary["גוש"],
              **{f"a_{EN[b]}": bloc_summary[f"שיטה א' – {b}"].round().astype(int) for b in BANDS},
              **{f"b_{EN[b]}": bloc_summary[f"שיטה ב' – {b}"].round().astype(int) for b in BANDS}}).to_csv(
    "data/dash/bloc_added.csv", index=False, encoding="utf-8")
pd.DataFrame({"sector": sector_summary.index, "ballots": sector_summary["קלפיות"].astype(int).values,
              "prior": (sector_summary["שיעור ממוצע 5 קודמות (משוקלל)"] * 100).round(1).values,
              "now": (sector_summary["שיעור 2026 (משוקלל)"] * 100).round(1).values,
              **{f"n_{EN[b]}": sector_summary[f"קלפיות {b}"].astype(int).values for b in BANDS},
              **{f"add_{EN[b]}": sector_summary[f"נוספו {b}"].astype(int).values for b in BANDS}}).to_csv(
    "data/dash/sector_summary.csv", index=False, encoding="utf-8")
pd.DataFrame([{"band": EN[b], "name": b, "n": int((R_band == b).sum()),
               "added": int(R.loc[R_band == b, "מצביעים שנוספו"].sum()),
               "seats": round(float(added_valid[R_band == b].sum() / seat), 1)} for b in BANDS]).to_csv(
    "data/dash/band_summary.csv", index=False, encoding="utf-8")
pd.DataFrame([{
    "n_ballots": len(cur), "seat": round(seat), "nat_avg": round(nat_avg * 100, 1), "nat_cur": round(nat[CUR] * 100, 1),
    "yellow_pp": YELLOW_PP, "orange_pp": ORANGE_PP, "red_pp": RED_PP, "red_sd": RED_SD, "min_bzb": MIN_BZB,
    "n_nonsig": int((in_band & ~stat_ok).sum()),
}]).to_csv("data/dash/summary.csv", index=False, encoding="utf-8")

with open("data/report.txt", "w", encoding="utf-8") as fh:
    print(pd.read_csv("data/dash/band_summary.csv").to_string(), file=fh)
    print(pd.read_csv("data/dash/sector_summary.csv").to_string(), file=fh)
    print(pd.read_csv("data/dash/bloc_added.csv").to_string(), file=fh)
    print(pd.read_csv("data/dash/party_added.csv").head(12).to_string(), file=fh)
    print(pd.read_csv("data/dash/summary.csv").to_string(), file=fh)
    print(cur["סימון"].value_counts().to_string(), file=fh)
