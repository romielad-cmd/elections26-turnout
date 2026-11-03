"""בדיקות תקינות לניתוח שיעור ההצבעה. כותב דוח טקסט ושתי לשוניות לקובץ ה-Excel."""
import numpy as np
import pandas as pd
from openpyxl import load_workbook

PRIOR, CUR = [21, 22, 23, 24, 25], 26
NAMES = {21: "אפר' 2019", 22: "ספט' 2019", 23: "מרץ 2020", 24: "מרץ 2021", 25: "נוב' 2022", 26: "אוק' 2026"}
BANDS = ["אדום", "כתום", "צהוב"]
XLSX = "ניתוח_שיעור_הצבעה_כנסת26.xlsx"
META = {"סמל ועדה", "ברזל", "שם ישוב", "סמל ישוב", "קלפי", "מספר קלפי", "ריכוז", "שופט", "בזב", "מצביעים",
        "פסולים", "כשרים", "חיצוניות", "קלפי אחרת"}


def read(path):
    raw = open(path, "rb").read()
    enc = "utf-8-sig" if raw[:3] == b"\xef\xbb\xbf" else "cp1255"
    df = pd.read_csv(path, encoding=enc)
    return df.loc[:, ~df.columns.str.startswith("Unnamed")].rename(columns={"מספר קלפי": "קלפי"})


checks = []  # (בדיקה, תוצאה, תקין?, הערה)


def add(name, result, ok, note=""):
    checks.append({"בדיקה": name, "תוצאה": result, "תקין": "✔" if ok else "✘ לבדיקה", "הערה": note})


raw = {n: read(f"data/raw/k{n}_expb.csv") for n in PRIOR + [CUR]}
loc = {n: read(f"data/raw/k{n}_expc.csv") for n in PRIOR + [CUR]}
cur = pd.read_pickle("data/cur.pkl")
tcols = [f"שיעור {NAMES[n]}" for n in PRIOR]

# 1. כיסוי – כל קלפי בכנסת 26 נמצאת בניתוח
r26 = raw[CUR]
home = r26[r26["בזב"] > 0]
env = r26[r26["בזב"] == 0]
add("קלפיות בקובץ 2026 (כולל מעטפות כפולות)", len(r26), True)
add("קלפיות ביתיות (בזב > 0) שנכנסו לניתוח", f"{len(cur)} מתוך {len(home)}", len(cur) == len(home))
add("קלפיות מעטפות כפולות (בזב 0) שאינן בניתוח", f"{len(env)} קלפיות, {env['מצביעים'].sum():,} מצביעים", True,
    "מצביעי מעטפות כפולות (חיילים, אסירים, נכים, אנשי סגל) אינם משויכים לקלפי ביתית ולכן אין להם שיעור הצבעה.")
dups = cur.duplicated(["סמל ישוב", "קלפי"]).sum()
add("כפילויות של יישוב+קלפי בניתוח", int(dups), dups == 0)
miss_keys = set(zip(home["סמל ישוב"], home["קלפי"])) - set(zip(cur["סמל ישוב"], cur["קלפי"]))
add("קלפיות 2026 שחסרות בניתוח", len(miss_keys), len(miss_keys) == 0)
add("סה\"כ מצביעים בקלפיות הביתיות – קובץ מול ניתוח", f"{home['מצביעים'].sum():,} / {cur['מצביעים'].sum():,}",
    home["מצביעים"].sum() == cur["מצביעים"].sum())

# 2. חשבון בתוך כל קלפי, בכל מערכת בחירות
for n in PRIOR + [CUR]:
    d = raw[n]
    pcs = [c for c in d.columns if c not in META]
    bad_sum = int((d["מצביעים"] != d["כשרים"] + d["פסולים"]).sum())
    bad_party = int((d[pcs].sum(axis=1) != d["כשרים"]).sum())
    over = int(((d["בזב"] > 0) & (d["מצביעים"] > d["בזב"])).sum())
    add(f"{NAMES[n]}: מצביעים = כשרים + פסולים", f"{bad_sum} חריגות", bad_sum == 0)
    add(f"{NAMES[n]}: סכום קולות המפלגות = כשרים", f"{bad_party} חריגות", bad_party == 0)
    add(f"{NAMES[n]}: קלפיות עם יותר מצביעים מבעלי זכות בחירה", f"{over} קלפיות", over == 0)

# 3. קובץ קלפיות מול קובץ יישובים (שני פרסומים נפרדים של ועדת הבחירות)
for n in PRIOR + [CUR]:
    b = raw[n].groupby("סמל ישוב")[["בזב", "מצביעים", "כשרים"]].sum()
    c = loc[n].groupby("סמל ישוב")[["בזב", "מצביעים", "כשרים"]].sum()
    j = b.join(c, rsuffix="_c", how="outer").fillna(0)
    diff = j[(j["בזב"] != j["בזב_c"]) | (j["מצביעים"] != j["מצביעים_c"]) | (j["כשרים"] != j["כשרים_c"])]
    add(f"{NAMES[n]}: קובץ קלפיות מול קובץ יישובים", f"{len(diff)} יישובים שונים מתוך {len(j)}",
        len(diff) == 0, "" if len(diff) == 0 else ", ".join(map(str, diff.index[:10])))
    tot_b, tot_c = raw[n]["מצביעים"].sum(), loc[n]["מצביעים"].sum()
    add(f"{NAMES[n]}: סה\"כ מצביעים ארצי (קלפיות / יישובים)", f"{tot_b:,} / {tot_c:,}", tot_b == tot_c)

# 4. ערכי שיעור הצבעה סבירים
now = cur[f"שיעור {NAMES[CUR]}"]
add("שיעור הצבעה 2026 מעל 100%", int((now > 1).sum()), (now > 1).sum() == 0)
hist = cur[tcols]
add("ערך היסטורי מעל 100% שנכנס לממוצע", int((hist > 1).sum().sum()), (hist > 1).sum().sum() == 0, "בקובץ ספט' 2019 יש 2 קלפיות (כרמים 1, תלם 1) עם יותר מצביעים מבעלי זכות בחירה – טעות בקובץ המקור; הערכים הוצאו מהממוצע.")
low = cur[(now < 0.05) & (cur["בזב"] >= 100)]
add("קלפיות 2026 עם פחות מ-5% הצבעה (בזב 100+)", len(low), True,
    ", ".join(f"{r['שם ישוב']} {r['קלפי']:g}" for _, r in low.head(10).iterrows()))
nohist = cur[cur["ממוצע 5 קודמות"].isna()]
add("קלפיות ללא היסטוריה כלל (יישוב חדש)", len(nohist), True,
    ", ".join(sorted(set(nohist["שם ישוב"]))))

# 5. יציבות ההיסטוריה – האם יש "קפיצות" בתוך הבסיס ההשוואתי
rng = (hist.max(axis=1) - hist.min(axis=1)) * 100
med = hist.median(axis=1)
outlier = (hist.sub(med, axis=0).abs() * 100 > 25).any(axis=1)
flagged = cur["סימון"].isin(BANDS)
add("קלפיות שבהן טווח ההיסטוריה (מקס׳ פחות מינ׳) מעל 30 נק'", f"{int((rng > 30).sum())} (מהן {int(((rng > 30) & flagged).sum())} מסומנות)",
    True, "רוב המקרים ביישובים בדואיים, שבהם שיעור ההצבעה תנודתי מאוד בין מערכות.")
add("קלפיות שבהן מערכת אחת רחוקה ביותר מ-25 נק' מהחציון", f"{int(outlier.sum())} (מהן {int((outlier & flagged).sum())} מסומנות)", True,
    "חשד להתאמה שגויה בין מערכות. מופיעות בלשונית 'קלפיות לבדיקה'.")

# 6. בדיקה עצמאית: חישוב מחדש של הממוצע לקלפיות שהותאמו ברמת קלפי בכל 5 המערכות
full_match = cur[(cur[[f"רמה {n}" for n in PRIOR]] == "קלפי").all(axis=1)]
sample = full_match.sample(min(300, len(full_match)), random_state=1)
grp = {n: raw[n][raw[n]["בזב"] > 0].assign(p=lambda d: d["קלפי"].astype(float).astype(int))
       .groupby(["סמל ישוב", "p"])[["בזב", "מצביעים"]].sum() for n in PRIOR}
errs = 0
for _, r in sample.iterrows():
    vals = [grp[n].loc[(r["סמל ישוב"], r["parent"]), "מצביעים"] / grp[n].loc[(r["סמל ישוב"], r["parent"]), "בזב"] for n in PRIOR]
    errs += abs(np.mean(vals) - r["ממוצע 5 קודמות"]) > 1e-9
add("חישוב עצמאי של הממוצע ל-300 קלפיות אקראיות", f"{errs} אי־התאמות", errs == 0)

# 7. סיווג ומיון
counts = cur["סימון"].value_counts()
add("כל קלפי קיבלה סימון אחד", f"{counts.sum()} מתוך {len(cur)}", counts.sum() == len(cur),
    "; ".join(f"{k}: {v}" for k, v in counts.items()))
dev = cur["שונות (נק' אחוז)"]
wrong = cur[cur["סימון"].isin(BANDS) & ~(
    ((cur["סימון"] == "אדום") & (dev >= 30)) | ((cur["סימון"] == "כתום") & (dev >= 15) & (dev < 30)) |
    ((cur["סימון"] == "צהוב") & (dev >= 10) & (dev < 15)))]
add("התאמת הצבע לגובה השונות", f"{len(wrong)} שגיאות", len(wrong) == 0)
ns = cur[cur["סימון"].str.contains("לא מובהק")]
reasons = {
    "בזב מתחת ל-100": int((ns["בזב"] < 100).sum()),
    "פחות מ-3 סטיות תקן": int((ns["סטיות תקן מעל הממוצע"] < 3).sum()),
    "פחות מ-3 מערכות בהיסטוריה": int((ns["מס' מערכות בהיסטוריה"] < 3).sum()),
}
add("קלפיות ברצועת צבע שלא עברו מבחן מובהקות", len(ns), True, "; ".join(f"{k}: {v}" for k, v in reasons.items()))
add("קלפיות מסומנות ללא קואורדינטות", int(cur.loc[flagged, "lat"].isna().sum()), cur.loc[flagged, "lat"].isna().sum() == 0)
add("קלפיות ללא מגזר", int(cur["מגזר"].isna().sum()), cur["מגזר"].isna().sum() == 0,
    "; ".join(f"{k}: {v}" for k, v in cur["מגזר"].value_counts().items()))
border = cur[cur["מגזר"].isin(["יהודי", "חרדי"]) & cur["חלק מפלגות ערביות"].between(0.3, 0.5)]
add("קלפיות 'יהודיות' עם 30%–50% למפלגות ערביות (סיווג גבולי)", len(border), True,
    ", ".join(f"{r['שם ישוב']} {r['קלפי']:g}" for _, r in border.head(12).iterrows()))
lvl = cur.loc[flagged, "רמת השוואה"].value_counts()
add("רמת השוואה בקלפיות המסומנות", "; ".join(f"{k}: {v}" for k, v in lvl.items()), True,
    "השוואה ברמת יישוב פחות מדויקת לקלפי בודדת.")

# 8. סכומים
exp_all = cur["מצביעים צפויים"].sum()
add("מצביעים בפועל פחות צפויים – כל הקלפיות", f"{int(cur['מצביעים'].sum() - exp_all):,}", True,
    "העלייה הארצית; הקלפיות המסומנות הן חלק ממנה.")

# --- קלפיות לבדיקה ידנית ---
review = cur[flagged & (outlier | (rng > 40) | (cur["רמת השוואה"] == "יישוב") & (cur["מגזר"].isin(["יהודי", "חרדי"])))].copy()
review["סיבה"] = np.select(
    [outlier[review.index], rng[review.index] > 40],
    ["מערכת אחת רחוקה מאוד מהחציון", "היסטוריה תנודתית מאוד"], "השוואה ברמת יישוב")
rev_x = review[["שם ישוב", "קלפי", "מגזר", "בזב", "סימון", "סיבה", "רמת השוואה"] + tcols +
               ["ממוצע 5 קודמות", f"שיעור {NAMES[CUR]}", "שונות (נק' אחוז)", "מצביעים שנוספו"]].copy()
rev_x[tcols + ["ממוצע 5 קודמות", f"שיעור {NAMES[CUR]}"]] = (rev_x[tcols + ["ממוצע 5 קודמות", f"שיעור {NAMES[CUR]}"]] * 100).round(1)
rev_x = rev_x.round(1).sort_values("שונות (נק' אחוז)", ascending=False)

chk = pd.DataFrame(checks)
with pd.ExcelWriter(XLSX, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
    chk.to_excel(xw, sheet_name="בדיקות תקינות", index=False)
    rev_x.to_excel(xw, sheet_name="קלפיות לבדיקה", index=False)
wb = load_workbook(XLSX)
for name in ("בדיקות תקינות", "קלפיות לבדיקה"):
    wb[name].sheet_view.rightToLeft = True
wb.save(XLSX)

with open("data/validation.txt", "w", encoding="utf-8") as fh:
    print(chk.to_string(), file=fh)
    print("\nלבדיקה:", len(rev_x), rev_x["סיבה"].value_counts().to_dict(), file=fh)
    print(rev_x.head(15).to_string(), file=fh)
