"""Render docs/demo.gif from a real run of the simulated compare. The per-batch log lines are condensed.

    uv run pinbench compare stable regressed -c examples/simulated > out.txt 2> err.txt
    uv run --no-project --with pillow==11.3.0 python scripts/make_demo_gif.py out.txt err.txt docs/demo.gif

Needs the macOS Menlo font; on another system, change the font path.
"""
import re, sys
from PIL import Image, ImageDraw, ImageFont

out_lines = open(sys.argv[1]).read().splitlines()
err_lines = open(sys.argv[2]).read().splitlines()
dest = sys.argv[3]
COLORS = {"bg": (13, 17, 23), "fg": (201, 209, 217), "dim": (139, 148, 158), "red": (248, 81, 73),
          "green": (63, 185, 80), "blue": (88, 166, 255), "yellow": (210, 153, 34)}
names = list(COLORS)
palette = [c for name in names for c in COLORS[name]] + [0] * (768 - 3 * len(names))
idx = {n: i for i, n in enumerate(names)}
font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 15)
W, H, PAD, LH = 980, 470, 18, 22

cmd = "uv run pinbench compare stable regressed -c examples/simulated"
batches = []
for line in err_lines:
    m = re.search(r"batch=(\d+) n_pairs=(\d+) n_discordant=(\d+) n_regress=(\d+) n_improve=(\d+) e_value=([\d.]+)", line)
    if m:
        b, p, d, r, i, e = m.groups()
        batches.append([("dim", f"batch {b}  pairs {int(p):>3}  discordant {int(d):>2} ({int(r):>2} regress / {int(i)} improve)  "),
                        ("red" if float(e) >= 20 else "fg", f"E = {float(e):6.2f}"), ("dim", "  (flag at E >= 20)")])
result = []
for line in out_lines:
    if line.startswith("report "):
        line = "report examples/simulated/.pinbench/reports/" + line.rsplit("/", 1)[1]
    colour = "red" if line.startswith("REGRESSION") else ("yellow" if "<- increase" in line else "fg")
    result.append([(colour, line)])

def frame(lines):
    im = Image.new("P", (W, H), idx["bg"]); im.putpalette(palette)
    d = ImageDraw.Draw(im)
    y = PAD
    for segs in lines:
        x = PAD
        for colour, text in segs:
            d.text((x, y), text, font=font, fill=idx[colour])
            x += d.textlength(text, font=font)
        y += LH
    return im

frames, durations = [], []
def add(lines, ms):
    frames.append(frame(lines)); durations.append(ms)

prompt = ("green", "$ ")
add([[prompt]], 700)
for n in range(3, len(cmd) + 3, 3):
    add([[prompt, ("blue", cmd[:n])]], 45)
shown = [[prompt, ("blue", cmd)]]
add(shown, 600)
for b in batches:
    shown = shown + [b]
    add(shown, 650)
shown = shown + [[]]
for r in result:
    shown = shown + [r]
    add(shown, 250)
add(shown, 6000)
frames[0].save(dest, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True, disposal=1)
print(len(frames), "frames,", sum(durations) / 1000, "s")
