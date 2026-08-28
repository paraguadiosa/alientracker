"""Verify heatmap cell rendering: box alignment + glyph scale + screenshot.

Usage:
  python deploy/verify_heatmap.py <base_url> <width> <out_path>

For a given viewport width:
1. cell, inner, icon, img boxes must all coincide (glyph centered in cell).
2. Element screenshots of cells must show the rounded-square glyph edges,
   i.e. glyph == cell size (a doubled glyph would fill the corners).
3. Saves a full-page screenshot.
"""

import io
import json
import sys
import time

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

base, width, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument(f"--window-size={width},900")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
d = webdriver.Chrome(options=opts)
d.set_window_size(width, 900)

d.get(f"{base}/demo")
WebDriverWait(d, 20).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/demo/habits/']"))
)
links = d.find_elements("css selector", "a[href*='/demo/habits/']")
habit_id = next(
    l.get_attribute("href").rstrip("/").split("/")[-1]
    for l in links
    if "/streak" not in l.get_attribute("href")
)
print("habit:", habit_id)
streak_url = f"{base}/demo/habits/{habit_id}/streak"

# The demo heatmap page sometimes needs a reload before it renders.
rows = None
for attempt in range(4):
    d.get(streak_url)
    n = 0
    for _ in range(12):
        time.sleep(2)
        n = d.execute_script(
            "return document.querySelectorAll('.theme-heatmap .q-checkbox').length"
        )
        if n > 0:
            break
    if n == 0:
        print(f"attempt {attempt}: heatmap not rendered after 24s, reloading")
        continue
    time.sleep(2)
    report = d.execute_script("""
const cells = document.querySelectorAll('.theme-heatmap .q-checkbox');
const box = (el) => { const r = el.getBoundingClientRect();
    return {x: Math.round(r.x * 10) / 10, y: Math.round(r.y * 10) / 10,
            w: Math.round(r.width * 10) / 10, h: Math.round(r.height * 10) / 10}; };
const row = [];
cells.forEach((c, i) => {
    if (i > 20) return;
    const inner = c.querySelector('.q-checkbox__inner');
    const icon = c.querySelector('.q-checkbox__icon');
    const img = c.querySelector('img');
    row.push({checked: c.getAttribute('aria-checked') === 'true',
        cell: box(c), inner: box(inner), icon: box(icon), img: box(img),
        innerFS: getComputedStyle(inner).fontSize,
        iconFS: getComputedStyle(icon).fontSize,
        labelDisplay: getComputedStyle(c.querySelector('.q-checkbox__label')).display});
});
return JSON.stringify(row);
""")
    rows = json.loads(report)
    break

if rows is None:
    print("FAIL: heatmap never rendered")
    sys.exit(2)

ok = True
for r in rows:
    cell = r["cell"]
    for name in ("inner", "icon", "img"):
        b = r[name]
        if (
            abs(b["x"] - cell["x"]) > 1
            or abs(b["y"] - cell["y"]) > 1
            or abs(b["w"] - cell["w"]) > 1
            or abs(b["h"] - cell["h"]) > 1
        ):
            print(f"MISALIGNED {name}: cell={cell} {name}={b}")
            ok = False
print(
    f"cell={rows[0]['cell']} innerFS={rows[0]['innerFS']} "
    f"iconFS={rows[0]['iconFS']} labelDisplay={rows[0]['labelDisplay']}"
)
print("boxes:", "OK" if ok else "FAIL")

# Glyph scale check: the svg square has rounded corners and a 5% inset,
# so the cell corners must show the page background, not glyph fill.
el = d.find_elements("css selector", ".theme-heatmap .q-checkbox")[0]
im = Image.open(io.BytesIO(el.screenshot_as_png)).convert("RGB")
px = im.load()
w, h = im.size
corner, center = px[1, 1], px[w // 2, h // 2]
print(f"cell px {w}x{h} corner={corner} center={center}")
if sum(corner) < sum(center):
    print("glyph scale: OK (rounded corners visible, glyph fits the cell)")
else:
    print("glyph scale: FAIL (glyph reaches the cell corners)")
    ok = False

d.save_screenshot(out_path)
print("screenshot:", out_path)
d.quit()
sys.exit(0 if ok else 1)
