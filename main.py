#!/usr/bin/env python3
"""The World Today - front page for Thursday 26 November 2026.

Pure Python standard library. Draws a 1024x1024 newspaper front page that
sums up six stories first reported on 26 November 2026, and writes it to
<output>/entry.png. Deterministic: two runs write identical bytes.

Run: mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import hashlib
import math
import os
import struct
import zlib

W, H = 1024, 1024
PAPER = (246, 241, 227)
INK = (25, 25, 25)
RED = (163, 22, 33)
ORANGE = (217, 79, 30)
GOLD = (232, 160, 32)
SMOKE = (154, 147, 138)

# 5x7 bitmap font, uppercase + digits + punctuation. Each glyph is 7 rows
# of 5 characters; '#' is ink, '.' is blank.
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "...#.", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".....", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ":": (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ";": (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    "?": (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    "%": ("#...#", "#..#.", "...#.", "..#..", ".#...", "#..#.", "#...#"),
    "(": ("...##", "..#..", ".#...", ".#...", ".#...", "..#..", "...##"),
    ")": ("##...", "..#..", "...#.", "...#.", "...#.", "..#..", "##..."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '"': (".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."),
    "/": ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    "+": (".....", "..#..", "..#..", ".###.", "..#..", "..#..", "....."),
    "=": (".....", ".....", ".###.", ".....", ".###.", ".....", "....."),
    "$": ("..#..", ".####", "#.#..", ".###.", "..#.#", "####.", "..#.."),
    "&": (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
}


def new_canvas():
    return bytearray(bytes(PAPER) * (W * H))


def set_px(buf, x, y, color):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        buf[i], buf[i + 1], buf[i + 2] = color


def fill_rect(buf, x, y, w, h, color):
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, W), min(y + h, H)
    for yy in range(y0, y1):
        base = (yy * W + x0) * 3
        for xx in range(x0, x1):
            i = base + (xx - x0) * 3
            buf[i], buf[i + 1], buf[i + 2] = color


def hline(buf, x, y, w, color, thick=1):
    fill_rect(buf, x, y, w, thick, color)


def draw_line(buf, x0, y0, x1, y1, color):
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        set_px(buf, x, y, color)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def fill_circle(buf, cx, cy, r, color):
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        fill_rect(buf, cx - dx, cy + dy, 2 * dx + 1, 1, color)


def fill_polygon(buf, points, color):
    # Scanline fill; points are (x, y) vertices in order.
    ys = [p[1] for p in points]
    for y in range(max(0, min(ys)), min(H, max(ys)) + 1):
        xs = []
        n = len(points)
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        if len(xs) >= 2:
            xs.sort()
            fill_rect(buf, int(xs[0]), y, int(xs[-1]) - int(xs[0]) + 1, 1, color)


def text_width(s, scale):
    return len(s) * 6 * scale - scale if s else 0


def draw_text(buf, x, y, s, scale, color):
    cx = x
    for ch in s:
        glyph = FONT.get(ch, FONT[" "])
        for r in range(7):
            row = glyph[r]
            for c in range(5):
                if row[c] == "#":
                    fill_rect(buf, cx + c * scale, y + r * scale, scale, scale, color)
        cx += 6 * scale
    return cx


def draw_text_centered(buf, x0, x1, y, s, scale, color):
    w = text_width(s, scale)
    draw_text(buf, x0 + (x1 - x0 - w) // 2, y, s, scale, color)


def wrap_text(s, scale, max_w):
    lines, cur = [], ""
    for word in s.split(" "):
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_block(buf, x, y, lines, scale, color, gap):
    for line in lines:
        draw_text(buf, x, y, line, scale, color)
        y += 7 * scale + gap
    return y


def rule(buf, y, thick=2):
    fill_rect(buf, 40, y, 944, thick, INK)


def draw_blast(buf, cx, cy):
    # Smoke puffs above the burst.
    for sx, sy, r in ((700, 232, 34), (792, 206, 42), (882, 234, 36)):
        fill_circle(buf, sx, sy, r, SMOKE)
        fill_circle(buf, sx, sy, r - 12, (168, 161, 152))
    # Starburst: 12 spikes alternating long and short. Kept clear of the
    # ground line and the caption below it.
    points = []
    for i in range(24):
        ang = math.pi * 2 * i / 24
        rad = 102 if i % 2 == 0 else 62
        points.append((cx + int(rad * math.cos(ang)), cy + int(rad * math.sin(ang))))
    fill_polygon(buf, points, ORANGE)
    # Hot core.
    fill_circle(buf, cx, cy, 52, GOLD)
    fill_circle(buf, cx, cy, 34, ORANGE)
    fill_circle(buf, cx, cy, 16, RED)
    # Ground line and rubble.
    fill_rect(buf, 620, 420, 364, 4, INK)
    for rx, rw in ((650, 26), (700, 14), (880, 20), (930, 30)):
        fill_rect(buf, rx, 412, rw, 8, INK)


def draw_cell(buf, x, y, w, kicker, headline, body):
    fill_rect(buf, x, y, w, 3, INK)
    draw_text(buf, x, y + 12, kicker, 2, RED)
    head_lines = wrap_text(headline, 3, w)[:2]
    by = draw_block(buf, x, y + 34, head_lines, 3, INK, 4)
    body_lines = wrap_text(body, 2, w)[:3]
    draw_block(buf, x, by + 6, body_lines, 2, INK, 5)


def build():
    buf = new_canvas()
    # Double border frame.
    fill_rect(buf, 20, 20, 984, 3, INK)
    fill_rect(buf, 20, 1001, 984, 3, INK)
    fill_rect(buf, 20, 20, 3, 984, INK)
    fill_rect(buf, 1001, 20, 3, 984, INK)
    fill_rect(buf, 28, 28, 968, 1, INK)
    fill_rect(buf, 28, 995, 968, 1, INK)
    fill_rect(buf, 28, 28, 1, 968, INK)
    fill_rect(buf, 995, 28, 1, 968, INK)

    # Masthead.
    draw_text_centered(buf, 40, 984, 52, "THE WORLD TODAY", 7, INK)
    fill_rect(buf, 40, 116, 944, 3, INK)
    fill_rect(buf, 40, 122, 944, 1, INK)
    # Dateline.
    draw_text(buf, 40, 138, "THURSDAY, 26 NOVEMBER 2026", 2, INK)
    right = "SIX STORIES THAT SHAPED THE DAY"
    draw_text(buf, 984 - text_width(right, 2), 138, right, 2, RED)
    rule(buf, 164, 1)

    # Lead story: the Iowa detonation.
    draw_text(buf, 40, 184, "IOWA, USA", 2, RED)
    draw_block(
        buf, 40, 210,
        ["ARMY DETONATES", "5 TONS OF UNSTABLE", "EXPLOSIVE IN IOWA"],
        4, INK, 4,
    )
    lead_body = (
        "THE ARMY DETONATED NEARLY FIVE TONS OF UNSTABLE LEAD AZIDE AT AN "
        "AMMUNITION PLANT IN IOWA. THE BLAST, MORE THAN 9,700 POUNDS OF THE "
        "VOLATILE COMPOUND, FOLLOWED WEEKS OF DELAYS AND A STATE DISASTER "
        "EMERGENCY."
    )
    draw_block(buf, 40, 322, wrap_text(lead_body, 2, 540), 2, INK, 6)
    draw_blast(buf, 802, 318)
    draw_text_centered(buf, 620, 984, 438, "THE BLAST IN IOWA", 2, INK)
    rule(buf, 478, 2)

    # Markets strip.
    draw_text(buf, 40, 500, "MARKETS", 2, RED)
    draw_text(buf, 40, 524, "NASDAQ SINKS NEARLY 4%", 3, INK)
    market_body = (
        "THE NASDAQ FELL NEARLY 4 PERCENT AS AN AI SELL-OFF DEEPENED AND "
        "NEW TARIFF FEARS SPOOKED TRADERS."
    )
    draw_block(buf, 40, 556, wrap_text(market_body, 2, 560), 2, INK, 5)
    # Down-bar chart: baseline, red bar falling below it, -4% label.
    hline(buf, 680, 545, 280, INK, 2)
    draw_line(buf, 690, 505, 690, 538, INK)
    fill_polygon(buf, [(678, 538), (702, 538), (690, 552)], INK)
    fill_rect(buf, 720, 545, 80, 55, RED)
    draw_text(buf, 820, 556, "-4%", 4, RED)
    draw_text(buf, 720, 608, "NASDAQ", 2, INK)
    draw_text(buf, 662, 538, "0", 2, INK)
    rule(buf, 628, 2)

    # Four-story grid, 2 x 2.
    draw_cell(
        buf, 40, 644, 452, "TRADE",
        "US READIES NEW TARIFFS ON CHINA, EU",
        "WASHINGTON PLANS HIGHER DUTIES ON CHINA, THE EU AND A DOZEN "
        "PARTNERS, WITH CHINA RATES NEARING 45 PERCENT.",
    )
    draw_cell(
        buf, 532, 644, 452, "ENERGY",
        "RUSSIAN REFINING AT 20-YEAR LOW",
        "UKRAINIAN STRIKES ON AT LEAST 18 REFINERIES DROVE RUSSIAN OIL "
        "REFINING TO ITS LOWEST IN MORE THAN 20 YEARS.",
    )
    draw_cell(
        buf, 40, 806, 452, "THE GULF",
        "IRAN SAYS SHIPS HIT MINES IN HORMUZ",
        "TEHRAN SAID VESSELS STRUCK UNDERWATER MINES IN THE STRAIT OF "
        "HORMUZ AND WARNED SHIPS TO COORDINATE PASSAGE.",
    )
    draw_cell(
        buf, 532, 806, 452, "TECH",
        "HUAWEI CONVICTED OF STEALING US SECRETS",
        "A US COURT CONVICTED HUAWEI ON 10 COUNTS, INCLUDING THEFT OF "
        "AMERICAN TRADE SECRETS.",
    )

    # Footer.
    fill_rect(buf, 40, 966, 944, 2, INK)
    draw_text_centered(
        buf, 40, 984, 976,
        "THE WORLD TODAY - 26 NOVEMBER 2026 - SIX STORIES, ONE PAGE",
        2, INK,
    )
    return bytes(buf)


def png_bytes(rgb):
    raw = b"".join(b"\x00" + rgb[y * W * 3:(y + 1) * W * 3] for y in range(H))

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main():
    rgb = build()
    data = png_bytes(rgb)
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} {len(data)} bytes sha256={hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
