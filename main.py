#!/usr/bin/env python3
"""news-image-20261126: a newspaper front page of Thursday 26 November 2026.

Pure Python 3.13 standard library. No network, no clock, no randomness:
two runs write byte-identical PNGs. The page is drawn with a hand-rolled
5x7 bitmap font on an RGB canvas, then encoded to PNG by hand
(zlib + CRC32, filter 0 scanlines).

Six stories, all first reported 26 November 2026:
 1. U.S. Army detonates nearly 5 tons of unstable lead azide in Iowa
 2. Nasdaq sinks nearly 4% as the AI selloff deepens
 3. U.S. plans new tariffs; China rate near 45% under Section 301
 4. Ukraine hits 18 refineries; Russian refining at a 20-year low
 5. Iran says a vessel struck a mine in the Strait of Hormuz
 6. Huawei found guilty on 10 counts, including trade-secret theft

Usage: mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
Writes <out>/entry.png (1024x1024, well under 1 MiB).
"""

import hashlib
import math
import os
import struct
import zlib
from pathlib import Path

W, H = 1024, 1024
PAPER = (246, 241, 227)
INK = (26, 26, 26)
RED = (164, 30, 34)
BLUE = (31, 78, 121)
ORANGE = (214, 110, 30)
YELLOW = (232, 178, 44)
GREY = (120, 116, 104)
LIGHT = (232, 226, 208)

# 5x7 bitmap font. Each glyph is 7 rows; a row's low 5 bits are pixels,
# bit 4 (0x10) is the leftmost pixel. Only the characters the page uses.
FONT = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
    " ": (0, 0, 0, 0, 0, 0, 0),
    ".": (0, 0, 0, 0, 0, 0x0C, 0x0C),
    ",": (0, 0, 0, 0, 0x0C, 0x04, 0x08),
    "-": (0, 0, 0, 0x0E, 0, 0, 0),
    "'": (0x04, 0x04, 0x08, 0, 0, 0, 0),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0, 0x04),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0, 0x04),
    "%": (0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13),
    "+": (0, 0x04, 0x04, 0x0E, 0x04, 0x04, 0),
    "=": (0, 0, 0x0E, 0, 0x0E, 0, 0),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "/": (0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10),
    "&": (0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D),
    "$": (0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04),
    '"': (0x0A, 0x0A, 0x0A, 0, 0, 0, 0),
    ";": (0, 0x0C, 0, 0, 0x0C, 0x04, 0x08),
    ":": (0, 0x0C, 0, 0, 0x0C, 0, 0),
}


class Canvas:
    """An RGB pixel buffer with simple filled-shape and text drawing."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def hline(self, x, y, w, color, thick=1):
        self.rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.rect(x, y, thick, h, color)

    def line(self, x0, y0, x1, y1, color):
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def triangle(self, x0, y0, x1, y1, x2, y2, color):
        (ax, ay), (bx, by), (cx, cy) = sorted(
            [(x0, y0), (x1, y1), (x2, y2)], key=lambda p: p[1]
        )

        def edge_x(y, p, q):
            if q[1] == p[1]:
                return p[0]
            return p[0] + (q[0] - p[0]) * (y - p[1]) / (q[1] - p[1])

        for y in range(ay, cy + 1):
            xa = edge_x(y, (ax, ay), (bx, by)) if y < by else edge_x(y, (bx, by), (cx, cy))
            xb = edge_x(y, (ax, ay), (cx, cy))
            lo, hi = sorted([int(round(xa)), int(round(xb))])
            self.rect(lo, y, hi - lo + 1, 1, color)

    def text(self, x, y, s, scale, color):
        cx = x
        for ch in s.upper():
            glyph = FONT.get(ch, FONT[" "])
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits & (0x10 >> col):
                        self.rect(cx + col * scale, y + row * scale, scale, scale, color)
            cx += 6 * scale
        return cx

    def text_width(self, s, scale):
        return len(s) * 6 * scale - scale

    def text_centered(self, y, s, scale, color):
        self.text((self.w - self.text_width(s, scale)) // 2, y, s, scale, color)

    def wrap(self, s, max_w, scale):
        lines, cur = [], ""
        for word in s.split(" "):
            trial = (cur + " " + word).strip()
            if self.text_width(trial, scale) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines

    def paragraph(self, x, y, s, max_w, scale, color, leading):
        yy = y
        for line in self.wrap(s, max_w, scale):
            self.text(x, yy, line, scale, color)
            yy += leading
        return yy


def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def encode_png(canvas):
    raw = bytearray()
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.buf[y * canvas.w * 3 : (y + 1) * canvas.w * 3]
    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def burst(cv, cx, cy, color, core):
    """A stylised explosion: twelve spikes around a bright core."""
    for k in range(12):
        a = k * math.pi / 6
        r1 = 78 if k % 2 == 0 else 46
        x1 = cx + int(r1 * math.cos(a))
        y1 = cy + int(r1 * math.sin(a))
        a2 = a + math.pi / 12
        x2 = cx + int(30 * math.cos(a2))
        y2 = cy + int(30 * math.sin(a2))
        a3 = a - math.pi / 12
        x3 = cx + int(30 * math.cos(a3))
        y3 = cy + int(30 * math.sin(a3))
        cv.triangle(x1, y1, x2, y2, x3, y3, color)
    cv.circle(cx, cy, 34, ORANGE)
    cv.circle(cx, cy, 20, core)


def draw_page():
    cv = Canvas(W, H, PAPER)
    mx = 32  # side margin
    # double border frame
    cv.rect(12, 12, W - 24, 2, INK)
    cv.rect(12, H - 14, W - 24, 2, INK)
    cv.rect(12, 12, 2, H - 24, INK)
    cv.rect(W - 14, 12, 2, H - 24, INK)

    # masthead
    cv.text_centered(30, "THE WORLD TODAY", 10, INK)
    cv.hline(mx, 116, W - 2 * mx, INK, 3)
    cv.hline(mx, 122, W - 2 * mx, INK, 1)
    cv.text(mx, 132, "WORLD EDITION", 2, GREY)
    cv.text_centered(132, "THURSDAY, 26 NOVEMBER 2026", 2, INK)
    right = "PRICE: $1"
    cv.text(W - mx - cv.text_width(right, 2), 132, right, 2, GREY)

    # ---- lead story: Iowa detonation ----
    cv.text(mx, 162, "IOWA, UNITED STATES", 2, RED)
    for i, line in enumerate(
        ["ARMY DETONATES NEARLY", "5 TONS OF UNSTABLE", "EXPLOSIVE IN IOWA"]
    ):
        cv.text(mx, 186 + i * 44, line, 5, INK)
    cv.paragraph(
        mx,
        330,
        "THE U.S. ARMY DETONATED MORE THAN 9,700 POUNDS OF UNSTABLE LEAD "
        "AZIDE AT A SITE IN IOWA AFTER WEEKS OF DELAYS, ENDING A STANDOFF "
        "THAT HAD PUT THE STATE UNDER A DISASTER EMERGENCY.",
        560,
        2,
        INK,
        18,
    )
    burst(cv, 830, 285, RED, YELLOW)
    # caption sits under the burst, clear of the lead body text
    label = "9,700 LB OF LEAD AZIDE"
    cv.text(830 - cv.text_width(label, 2) // 2, 392, label, 2, RED)
    cv.hline(mx, 448, W - 2 * mx, INK, 2)

    # ---- markets strip: Nasdaq ----
    cv.text(mx, 466, "MARKETS", 2, RED)
    cv.text(mx, 490, "NASDAQ SINKS NEARLY 4%", 4, INK)
    cv.paragraph(
        mx,
        536,
        "STOCKS FELL AS THE AI SELLOFF DEEPENED AND TARIFF WORRIES SPREAD, "
        "WITH THE NASDAQ LEADING THE LOSSES.",
        500,
        2,
        INK,
        18,
    )
    # falling bars + big -4%
    base = 612
    heights = [118, 98, 80, 58, 36]
    for i, hh in enumerate(heights):
        bx = 600 + i * 74
        cv.rect(bx, base - hh, 52, hh, RED if i == len(heights) - 1 else BLUE)
    cv.hline(590, base, 400, INK, 2)
    cv.line(600, base - 118, 600 + 4 * 74 + 26, base - 36, RED)
    cv.text(700, 470, "-4%", 5, RED)
    cv.hline(mx, 640, W - 2 * mx, INK, 2)

    # ---- 2x2 grid of the other four stories ----
    cells = [
        (
            "U.S. PLANS NEW TARIFFS ON CHINA, EU AND OTHERS",
            "THE CHINA RATE WOULD BE NEAR 45 PERCENT UNDER SECTION 301.",
            "pct",
        ),
        (
            "UKRAINE HITS 18 REFINERIES",
            "RUSSIAN REFINING FALLS TO ITS LOWEST IN MORE THAN 20 YEARS.",
            "flame",
        ),
        (
            "MINE STRIKE IN STRAIT OF HORMUZ",
            "IRAN SAYS A VESSEL STRUCK A MINE AND WARNS SHIPS TO COORDINATE TRANSIT.",
            "ship",
        ),
        (
            "HUAWEI GUILTY ON 10 COUNTS",
            "THE VERDICT INCLUDES STEALING U.S. TRADE SECRETS.",
            "court",
        ),
    ]
    col_w = 464
    for idx, (head, body, icon) in enumerate(cells):
        col = idx % 2
        row = idx // 2
        x = mx + col * (col_w + 32)
        y = 662 + row * 152
        cv.hline(x, y, col_w, INK, 2)
        yy = cv.paragraph(x, y + 12, head, col_w - 70, 3, INK, 26)
        cv.paragraph(x, yy + 4, body, col_w, 2, INK, 18)
        ix, iy = x + col_w - 56, y + 10
        if icon == "pct":
            cv.text(ix, iy, "%", 6, BLUE)
        elif icon == "flame":
            cv.triangle(ix + 26, iy, ix + 2, iy + 52, ix + 50, iy + 52, ORANGE)
            cv.triangle(ix + 26, iy + 22, ix + 14, iy + 52, ix + 38, iy + 52, YELLOW)
        elif icon == "ship":
            cv.rect(ix + 4, iy + 30, 48, 14, BLUE)
            cv.triangle(ix + 4, iy + 30, ix + 52, iy + 30, ix + 44, iy + 44, BLUE)
            cv.vline(ix + 26, iy + 6, 26, INK, 3)
            cv.triangle(ix + 28, iy + 6, ix + 28, iy + 26, ix + 48, iy + 26, RED)
            cv.hline(ix, iy + 50, 56, BLUE, 2)
        else:  # court
            cv.triangle(ix, iy + 18, ix + 56, iy + 18, ix + 28, iy, BLUE)
            for k in range(3):
                cv.vline(ix + 8 + k * 20, iy + 22, 26, INK, 4)
            cv.hline(ix, iy + 50, 56, INK, 3)

    # footer
    cv.hline(mx, 972, W - 2 * mx, INK, 2)
    cv.text_centered(984, "THE WORLD TODAY - 26 NOVEMBER 2026 - SIX STORIES", 2, GREY)
    return cv


def main():
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    png = encode_png(draw_page())
    target = out_dir / "entry.png"
    target.write_bytes(png)
    print(
        f"wrote {target} {len(png)} bytes "
        f"sha256={hashlib.sha256(png).hexdigest()}"
    )


if __name__ == "__main__":
    main()
