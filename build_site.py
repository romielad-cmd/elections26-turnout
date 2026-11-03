"""בונה גרסה עצמאית של הדשבורד לפרסום ב-GitHub Pages (תיקיית docs/).

לוקח את dashboard/index.html (אותו קוד של הדשבורד ב-claude.ai), עוטף אותו בדף HTML מלא
עם ערכות צבע, ומחליף את ממשק ה-dash של claude.ai בשכבה קטנה שטוענת את קובצי הנתונים מ-docs/data.
"""
import os
import shutil

SOURCES = {
    "flagged_ballots": "flagged_ballots.csv",
    "party_added": "party_added.csv",
    "bloc_added": "bloc_added.csv",
    "sector_summary": "sector_summary.csv",
    "band_summary": "band_summary.csv",
    "summary": "summary.csv",
    "israel_outline": "israel_outline.json",
}

os.makedirs("docs/data", exist_ok=True)
for f in SOURCES.values():
    shutil.copy(os.path.join("data/dash", f), os.path.join("docs/data", f))
shutil.copy("ניתוח_שיעור_הצבעה_כנסת26.xlsx", "docs/data/elections26_turnout_analysis.xlsx")

page = open("dashboard/index.html", encoding="utf-8").read().replace('<meta name="dash-one-writer">\n', "")
sources_js = ",\n    ".join(f'{k}: "data/{v}"' for k, v in SOURCES.items())

HEAD = """<!doctype html>
<html lang="he" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>קפיצות בשיעור ההצבעה – כנסת 26</title>
<meta name="description" content="קלפיות שבהן שיעור ההצבעה בבחירות 2026 קפץ חריגות מעל ממוצע חמש מערכות הבחירות הקודמות, ולאן הלכו הקולות הנוספים.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Assistant:wght@400;500;600&family=Frank+Ruhl+Libre:wght@400;500&display=swap">
<style>
  /* פריסה: עמודה אחת ברוחב מלא עם שוליים; ערכת צבעים בהירה וכהה */
  :root {
    --font-anthropic-sans: "Assistant", "Segoe UI", Arial, sans-serif;
    --font-anthropic-serif: "Frank Ruhl Libre", "David", Georgia, serif;
    --color-bg: #f6f6f3; --color-panel: #ffffff; --color-fg: #1f2328; --color-fg-muted: #5d636b;
    --color-border-line: #dedfdb; --color-bad: #c2362f; --color-ok: #2e7d4f; --color-warn: #a86b00;
    --cds-chart-muted: #b9bcbf; --cds-chart-axis: #8c9096; --cds-chart-grid: #e6e7e4; --cds-chart-status-critical: #c2362f;
    --cds-surface-popover: #ffffff; --cds-border: #d4d6d2; --cds-shadow-popover: 0 4px 16px rgba(20, 24, 28, .12);
    --cds-text-secondary: #5d636b;
    --cds-font-size-caption: 0.8125rem; --cds-font-size-body: 1rem; --cds-font-size-heading: 1.125rem; --cds-font-size-title: 1.75rem;
    --cds-font-weight-medium: 600;
    --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 16px; --cds-gap-lg: 24px; --cds-gap-xl: 36px;
    --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-md: 12px; --cds-pad-lg: 18px;
    --cds-radius: 6px; --cds-dur-slow: 300ms;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --color-bg: #15171a; --color-panel: #1d2024; --color-fg: #e8e9ea; --color-fg-muted: #a2a7ad;
      --color-border-line: #33373c; --cds-chart-muted: #5b6066; --cds-chart-axis: #7d838a; --cds-chart-grid: #2a2d31;
      --cds-surface-popover: #24282d; --cds-border: #3a3f45; --cds-text-secondary: #a2a7ad; color-scheme: dark;
    }
  }
  :root[data-theme="dark"] {
    --color-bg: #15171a; --color-panel: #1d2024; --color-fg: #e8e9ea; --color-fg-muted: #a2a7ad;
    --color-border-line: #33373c; --cds-chart-muted: #5b6066; --cds-chart-axis: #7d838a; --cds-chart-grid: #2a2d31;
    --cds-surface-popover: #24282d; --cds-border: #3a3f45; --cds-text-secondary: #a2a7ad; color-scheme: dark;
  }
  html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); }
  body { padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); padding-block: 28px 48px; }
  #dash-root { max-width: 80rem; margin-inline: auto; }
  .dash-skeleton { background: linear-gradient(90deg, var(--color-border-line), transparent); opacity: .35; border-radius: var(--cds-radius); }
  .tv-foot { max-width: 80rem; margin: 40px auto 0; font-family: var(--font-anthropic-sans); font-size: 0.8125rem; color: var(--color-fg-muted); direction: rtl; display: flex; flex-wrap: wrap; gap: 8px 20px; }
  .tv-foot a { color: inherit; }
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<script>
  // שכבה שמחליפה את ממשק ה-dash של claude.ai: טוענת קבצים, מריצה חישובים וציורים
  (function () {
    const SOURCES = {
    __SOURCES__
    };
    const store = {}, draws = {}, calcs = {};
    window.dash = {
      colors: ["#3b6fb6", "#2f9e8f", "#8a5cc2", "#e08a2e", "#7a8a99"],
      data(id) { return id in store ? { status: "ok", data: store[id] } : { status: "loading", data: [] }; },
      draw(name, fn) {
        if (fn) { draws[name] = fn; return; }
        document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => draws[name] && draws[name](el));
      },
      calc(id, spec) { calcs[id] = spec; },
      onData() {},
    };
    const drawAll = () => Object.keys(draws).forEach((n) => window.dash.draw(n));
    window.addEventListener("DOMContentLoaded", async () => {
      await Promise.all(Object.entries(SOURCES).map(async ([id, url]) => {
        store[id] = url.endsWith(".json") ? await d3.json(url) : await d3.csv(url);
      }));
      for (const [id, spec] of Object.entries(calcs)) store[id] = spec.fn(...spec.inputs.map((i) => store[i]));
      drawAll();
      let w = window.innerWidth;
      window.addEventListener("resize", () => { if (Math.abs(window.innerWidth - w) > 40) { w = window.innerWidth; drawAll(); } });
    });
  })();
</script>
</head>
<body>
<div id="dash-root">
""".replace("__SOURCES__", sources_js)

FOOT = """
</div>
<footer class="tv-foot">
  <span>מקור הנתונים: ועדת הבחירות המרכזית (תוצאות לפי קלפי, כנסות 21–26) והלמ"ס (קובץ יישובים).</span>
  <a href="data/elections26_turnout_analysis.xlsx">הורדת קובץ ה־Excel המלא</a>
  <a href="https://github.com/__REPO__">קוד ונתונים ב־GitHub</a>
</footer>
</body>
</html>
"""
repo = os.environ.get("REPO", "OWNER/REPO")
open("docs/index.html", "w", encoding="utf-8").write(HEAD + page + FOOT.replace("__REPO__", repo))
open("docs/.nojekyll", "w").close()
print("docs/index.html", os.path.getsize("docs/index.html"))
