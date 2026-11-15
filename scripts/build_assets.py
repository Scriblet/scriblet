"""Generates the profile README artwork in assets/.

Usage: python3 scripts/build_assets.py [--fonts DIR] [--shots DIR]

--fonts points to the @fontsource-variable folder (Bricolage Grotesque,
Schibsted Grotesk, Martian Mono). --shots holds the source images:
portrait.jpg, portfolio-dark.png, portfolio-light.png and ervas.png.
Fonts are instanced, subset to the glyphs used and embedded as woff2, so the
SVGs render with the brand typography inside GitHub's <img> sandbox.
"""
import argparse
import base64
import io
import math
import random
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

THEMES = {
    "dark": dict(
        bg="#08120c", bg2="#0c1910", surface="#13241a", deep="#203d22",
        text="#ebefe6", text2="#b9c4b3", muted="#8f9d8d",
        accent="#8fca7f", emph="#e0a85a", border="#ebefe6", border_op=0.13,
        shadow="#08120c", highlight="#e3ecdc", line="#8fca7f", glow="#203d22",
    ),
    "light": dict(
        bg="#f1f0ec", bg2="#faf9f6", surface="#faf9f6", deep="#c9d6e3",
        text="#10202b", text2="#3f4b52", muted="#5d6a72",
        accent="#163f66", emph="#4d6577", border="#10202b", border_op=0.14,
        shadow="#10202b", highlight="#f3f2ee", line="#22547f", glow="#c9d6e3",
    ),
}

FONT_SPECS = {
    "display": ("bricolage-grotesque/files/bricolage-grotesque-latin-standard-normal.woff2",
                {"wght": 800, "opsz": 96, "wdth": 88}),
    "body": ("schibsted-grotesk/files/schibsted-grotesk-latin-wght-normal.woff2", {"wght": 450}),
    "mono": ("martian-mono/files/martian-mono-latin-standard-normal.woff2", {"wght": 560, "wdth": 87.5}),
}


class Fonts:
    def __init__(self, base: Path):
        self.tt = {}
        for key, (rel, axes) in FONT_SPECS.items():
            font = instancer.instantiateVariableFont(TTFont(base / rel), axes)
            self.tt[key] = font

    def width(self, key, text, size, tracking=0.0):
        font = self.tt[key]
        cmap = font.getBestCmap()
        hmtx = font["hmtx"]
        upm = font["head"].unitsPerEm
        adv = sum(hmtx[cmap.get(ord(c), cmap[32])][0] for c in text)
        return adv / upm * size + tracking * size * max(len(text) - 1, 0)

    def face(self, key, chars):
        buf = io.BytesIO()
        font = TTFont()
        font = self.tt[key]
        tmp = io.BytesIO()
        font.save(tmp)
        tmp.seek(0)
        sub = TTFont(tmp)
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        sub_obj = subset.Subsetter(opts)
        sub_obj.populate(text="".join(sorted(set(chars))) + " ")
        sub_obj.subset(sub)
        sub.flavor = "woff2"
        sub.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        return f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,{data}) format('woff2');}}"


class Doc:
    """Collects SVG nodes and the glyphs each font needs."""

    def __init__(self, fonts, width, height, title):
        self.fonts, self.w, self.h, self.title = fonts, width, height, title
        self.nodes, self.chars, self.css = [], {k: set() for k in FONT_SPECS}, []

    def add(self, node):
        self.nodes.append(node)

    def text(self, x, y, s, font, size, fill, tracking=0.0, anchor="start", cls="", opacity=1.0):
        self.chars[font].update(s)
        ls = f' letter-spacing="{tracking * size:.2f}"' if tracking else ""
        c = f' class="{cls}"' if cls else ""
        op = f' opacity="{opacity}"' if opacity != 1 else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" '
                 f'fill="{fill}" text-anchor="{anchor}"{ls}{c}{op}>{escape(s)}</text>')

    def render(self, defs=""):
        faces = "".join(self.fonts.face(k, v) for k, v in self.chars.items() if v)
        css = faces + "".join(self.css) + (
            "@media (prefers-reduced-motion: reduce){*{animation:none!important}}")
        return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                f'width="{self.w}" height="{self.h}" viewBox="0 0 {self.w} {self.h}" role="img" '
                f'aria-label="{escape(self.title)}"><title>{escape(self.title)}</title>'
                f'<style>{css}</style><defs>{defs}</defs>{"".join(self.nodes)}</svg>')


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def duotone(img, shadow, highlight):
    gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    return ImageOps.colorize(gray, hex_rgb(shadow), hex_rgb(highlight))


def data_uri(img, quality=80):
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def pill(doc, x, y, label, t, font="mono", size=13, dot=None, fill=None, color=None, pad=16, h=34):
    w = doc.fonts.width(font, label, size, 0.04) + pad * 2 + (18 if dot else 0)
    doc.add(f'<rect x="{x}" y="{y}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
            f'fill="{fill or t["surface"]}" stroke="{t["border"]}" stroke-opacity="{t["border_op"]}"/>')
    tx = x + pad
    if dot:
        doc.add(f'<circle cx="{tx + 4}" cy="{y + h / 2}" r="4" fill="{dot}"/>'
                f'<circle cx="{tx + 4}" cy="{y + h / 2}" r="4" fill="none" stroke="{dot}" class="ping"/>')
        tx += 18
    doc.text(tx, y + h / 2 + size * 0.36, label, font, size, color or t["text2"], tracking=0.04)
    return w


def flow_lines(t, w, h, n, y0, amp, seed, cls_prefix="flow"):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        y = y0 + i * 9
        a = amp * (0.7 + 0.6 * rnd.random())
        ph = rnd.random() * math.pi
        pts = []
        for k in range(0, 41):
            x = w * k / 40
            pts.append((x, y + a * math.sin(k / 40 * math.pi * 2.2 + ph + i * 0.12)))
        d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        op = 0.08 + 0.22 * (1 - abs(i - n / 2) / (n / 2))
        out.append(f'<path d="{d}" fill="none" stroke="{t["line"]}" stroke-width="1.1" '
                   f'stroke-opacity="{op:.2f}" class="{cls_prefix} {cls_prefix}{i % 3}"/>')
    return "".join(out)


def particles(t, w, h, n, seed, x0=0):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        x, y = x0 + rnd.random() * (w - x0), rnd.random() * h
        r = 0.6 + rnd.random() * 1.4
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{t["text"]}" '
                   f'class="tw tw{i % 4}" opacity="{0.15 + rnd.random() * 0.45:.2f}"/>')
    return "".join(out)


BASE_CSS = (
    "@keyframes drift{0%{transform:translateX(0)}50%{transform:translateX(-24px)}100%{transform:translateX(0)}}"
    ".flow{animation:drift 14s ease-in-out infinite}.flow1{animation-duration:18s}.flow2{animation-duration:22s}"
    "@keyframes tw{0%,100%{opacity:.08}50%{opacity:.7}}"
    ".tw{animation:tw 5s ease-in-out infinite}.tw1{animation-delay:1.3s}.tw2{animation-delay:2.6s}.tw3{animation-delay:3.9s}"
    "@keyframes ping{0%{r:4;opacity:.9}80%,100%{r:13;opacity:0}}"
    ".ping{animation:ping 2.2s cubic-bezier(0,0,.2,1) infinite}"
)


def header(fonts, mode, portrait):
    t = THEMES[mode]
    W, H = 1280, 460
    doc = Doc(fonts, W, H, "Lucas Nonato, AI Consultant and Software Engineer")
    doc.css.append(BASE_CSS)
    pw, ph = 600, H
    src = portrait.copy()
    sw, sh = src.size
    crop_h = int(sw * ph / pw)
    top = int(sh * 0.02)
    src = src.crop((0, top, sw, min(top + crop_h, sh))).resize((pw * 2, ph * 2), Image.LANCZOS)
    photo = data_uri(duotone(src, t["shadow"], t["highlight"]), 78)
    defs = (
        f'<radialGradient id="glow" cx="72%" cy="38%" r="60%"><stop offset="0" stop-color="{t["glow"]}" stop-opacity=".9"/>'
        f'<stop offset="1" stop-color="{t["bg"]}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="fadeX" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".45" stop-color="#fff" stop-opacity="1"/></linearGradient>'
        f'<linearGradient id="fadeY" x1="0" y1="0" x2="0" y2="1"><stop offset=".6" stop-color="#fff"/>'
        f'<stop offset="1" stop-color="#000"/></linearGradient>'
        f'<mask id="pm"><rect x="{W - pw}" y="0" width="{pw}" height="{ph}" fill="url(#fadeX)"/></mask>'
        f'<mask id="pm2"><rect x="{W - pw}" y="0" width="{pw}" height="{ph}" fill="url(#fadeY)"/></mask>'
        f'<clipPath id="card"><rect width="{W}" height="{H}" rx="28"/></clipPath>'
    )
    doc.add(f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{t["bg"]}"/>'
            f'<rect width="{W}" height="{H}" fill="url(#glow)"/>')
    doc.add(f'<g mask="url(#pm2)"><image href="{photo}" x="{W - pw}" y="0" width="{pw}" height="{ph}" '
            f'mask="url(#pm)" preserveAspectRatio="xMidYMid slice"/></g>')
    doc.add(f'<g opacity=".9">{flow_lines(t, W + 60, H, 14, 300, 46, 7)}</g>')
    doc.add(particles(t, W, H, 46, 3, x0=420))
    x = 64
    doc.add('<g class="in d1">')
    pill(doc, x, 58, "AI CONSULTANT · SOFTWARE ENGINEER", t, size=12, dot=t["accent"])
    doc.add('</g><g class="in d2">')
    doc.text(x - 4, 186, "Lucas Nonato", "display", 96, t["text"], tracking=-0.035)
    doc.add('</g><g class="in d3">')
    doc.text(x - 2, 248, "Turning AI into products", "display", 46, t["emph"], tracking=-0.02)
    doc.text(x - 2, 300, "people actually use.", "display", 46, t["emph"], tracking=-0.02)
    doc.add('</g><g class="in d4">')
    doc.text(x, 346, "End-to-end engineer from São Paulo. LLMs, agents and accessible", "body", 20, t["text2"])
    doc.text(x, 374, "interfaces built with architecture and real results in mind.", "body", 20, t["text2"])
    doc.add('</g><g class="in d5">')
    cx = x
    for label, dot in [("NOW · VIVO, AURA AI PLATFORM", t["emph"]), ("7+ YEARS", None), ("TS · REACT · NODE.JS", None)]:
        cx += pill(doc, cx, 398, label, t, size=11, dot=dot, h=30, pad=14) + 10
    doc.add("</g>")
    doc.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="28" fill="none" '
            f'stroke="{t["border"]}" stroke-opacity="{t["border_op"]}"/></g>')
    return doc.render(defs)


PROJECTS = {
    "ervas": dict(
        name="Ervas Sagradas", kind="DIGITAL ENCYCLOPEDIA", status="LIVE",
        tagline="71 sacred herbs of Umbanda and Afro-Brazilian traditions,",
        tagline2="searchable, with ritual uses, baths and safety notes.",
        stack=["React", "Vite", "Tailwind", "Vercel"], url="ervassagradas.com",
        shots={"dark": "ervas.png", "light": "ervas.png"},
    ),
    "portfolio": dict(
        name="Portfolio 2025", kind="PERSONAL SITE · OPEN SOURCE", status="LIVE",
        tagline="Mata e mar design system, AI maturity map and",
        tagline2="case studies. WCAG 2.2 AA, PWA, tested end to end.",
        stack=["React 19", "TypeScript", "MUI", "Vitest", "Cypress"], url="lucas-nonato.netlify.app",
        shots={"dark": "portfolio-dark.png", "light": "portfolio-light.png"},
    ),
}


def card(fonts, mode, key, shots):
    t = THEMES[mode]
    p = PROJECTS[key]
    W, H = 640, 520
    sh_h = 320
    doc = Doc(fonts, W, H, f'{p["name"]}: {p["tagline"]} {p["tagline2"]}')
    doc.css.append(BASE_CSS)
    img = Image.open(shots / p["shots"][mode]).convert("RGB")
    iw = img.size[0]
    iw -= 16  # drop the browser scrollbar
    img = img.crop((0, 0, iw, int(iw * sh_h / W))).resize((W * 2, sh_h * 2), Image.LANCZOS)
    photo = data_uri(img, 76)
    defs = (f'<clipPath id="c"><rect width="{W}" height="{H}" rx="24"/></clipPath>'
            f'<linearGradient id="sf" x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stop-color="{t["surface"]}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{t["surface"]}" stop-opacity="1"/></linearGradient>')
    doc.add(f'<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{t["surface"]}"/>'
            f'<image href="{photo}" x="0" y="0" width="{W}" height="{sh_h}" preserveAspectRatio="xMidYMin slice"/>'
            f'<rect y="0" width="{W}" height="{sh_h}" fill="url(#sf)"/>')
    pill(doc, W - 96, 22, p["status"], t, size=11, dot="#3fb950" if mode == "dark" else "#1a7f37",
         fill=t["bg"], color=t["text"], h=30, pad=12)
    y = sh_h + 14
    doc.text(28, y, p["kind"], "mono", 11, t["accent"] if mode == "light" else t["emph"], tracking=0.08)
    doc.text(W - 28, y, p["url"], "mono", 11, t["muted"], anchor="end", tracking=0.02)
    doc.text(26, y + 46, p["name"], "display", 40, t["text"], tracking=-0.03)
    arrow_x = W - 64
    doc.add(f'<g transform="translate({arrow_x},{y + 22})"><circle cx="16" cy="16" r="20" fill="{t["text"]}"/>'
            f'<path d="M10 22 L22 10 M12 10 H22 V20" stroke="{t["bg"]}" stroke-width="2.2" fill="none" stroke-linecap="round"/></g>')
    doc.text(28, y + 80, p["tagline"], "body", 17, t["text2"])
    doc.text(28, y + 103, p["tagline2"], "body", 17, t["text2"])
    cx = 28
    for s in p["stack"]:
        cx += pill(doc, cx, y + 122, s, t, size=11, h=28, pad=12, fill=t["bg"]) + 8
    doc.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="24" fill="none" '
            f'stroke="{t["border"]}" stroke-opacity="{t["border_op"] + 0.04}"/></g>')
    return doc.render(defs)


CAREER = [
    ("MAR 2026 – NOW", "Vivo", ["AI Consultant ·", "AI Software Engineer"], True),
    ("JAN 2024 – MAR 2026", "Porto Seguro", ["Software Developer"], False),
    ("APR 2022 – AUG 2023", "Thoughtworks", ["Consultant Developer"], False),
    ("JUN 2021 – MAR 2022", "ArcoTech", ["Full Stack Developer"], False),
    ("AUG 2019 – JUN 2021", "Finger", ["Founder & UX Designer"], False),
]


def timeline(fonts, mode):
    t = THEMES[mode]
    W, H = 1280, 250
    doc = Doc(fonts, W, H, "Career: " + "; ".join(f"{c[1]}, {' '.join(c[2])} ({c[0]})" for c in CAREER))
    doc.css.append(BASE_CSS + "@keyframes dash{to{stroke-dashoffset:-40}}.dash{animation:dash 2.4s linear infinite}")
    defs = (f'<linearGradient id="tl" x1="0" x2="1"><stop offset="0" stop-color="{t["emph"]}"/>'
            f'<stop offset=".25" stop-color="{t["accent"]}"/><stop offset="1" stop-color="{t["accent"]}" stop-opacity=".15"/></linearGradient>')
    doc.add(f'<rect width="{W}" height="{H}" rx="24" fill="{t["bg"]}" stroke="{t["border"]}" stroke-opacity="{t["border_op"]}"/>')
    line_y = 74
    col = (W - 96) / len(CAREER)
    doc.add(f'<line x1="48" y1="{line_y}" x2="{W - 48}" y2="{line_y}" stroke="url(#tl)" stroke-width="2" '
            f'stroke-dasharray="6 14" class="dash"/>')
    for i, (period, company, role, current) in enumerate(CAREER):
        x = 48 + col * i + 8
        doc.add(f'<g class="in d{i + 1}">')
        color = t["emph"] if current else t["accent"]
        doc.add(f'<circle cx="{x + 8}" cy="{line_y}" r="8" fill="{t["bg"]}" stroke="{color}" stroke-width="2.5"/>'
                f'<circle cx="{x + 8}" cy="{line_y}" r="3.5" fill="{color}"/>')
        if current:
            doc.add(f'<circle cx="{x + 8}" cy="{line_y}" r="4" fill="none" stroke="{color}" class="ping"/>')
        doc.text(x, 40, period, "mono", 11, t["muted"], tracking=0.06)
        doc.text(x - 2, 136, company, "display", 34, t["text"], tracking=-0.03)
        for j, r in enumerate(role):
            doc.text(x, 170 + j * 24, r, "body", 18, t["text2"])
        doc.add("</g>")
    return doc.render(defs)


def footer(fonts, mode):
    t = THEMES[mode]
    W, H = 1280, 150
    doc = Doc(fonts, W, H, "Folha, fé e fundamento. Thanks for stopping by.")
    doc.css.append(BASE_CSS)
    defs = (f'<linearGradient id="fg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["bg"]}" stop-opacity="0"/>'
            f'<stop offset="1" stop-color="{t["glow"]}" stop-opacity=".9"/></linearGradient>'
            f'<clipPath id="c"><rect width="{W}" height="{H}" rx="24"/></clipPath>')
    doc.add(f'<g clip-path="url(#c)"><rect width="{W}" height="{H}" fill="{t["bg"]}"/><rect width="{W}" height="{H}" fill="url(#fg)"/>'
            f'{flow_lines(t, W + 60, H, 10, 70, 22, 11)}{particles(t, W, H, 28, 5)}')
    doc.text(W / 2, 72, "Thanks for stopping by.", "display", 34, t["text"], anchor="middle", tracking=-0.03)
    doc.text(W / 2, 104, "BUILT WITH CARE IN SÃO PAULO · MATA E MAR DESIGN SYSTEM", "mono", 11, t["muted"],
             anchor="middle", tracking=0.08)
    doc.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="24" fill="none" stroke="{t["border"]}" '
            f'stroke-opacity="{t["border_op"]}"/></g>')
    return doc.render(defs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fonts", type=Path,
                    default=Path.home() / "repos/portfolio-2025/node_modules/@fontsource-variable")
    ap.add_argument("--shots", type=Path, default=Path.home() / "work")
    args = ap.parse_args()
    fonts = Fonts(args.fonts)
    portrait = Image.open(args.shots / "portrait.jpg").convert("RGB")
    OUT.mkdir(exist_ok=True)
    for mode in THEMES:
        files = {
            f"header-{mode}.svg": header(fonts, mode, portrait),
            f"timeline-{mode}.svg": timeline(fonts, mode),
            f"footer-{mode}.svg": footer(fonts, mode),
        }
        for key in PROJECTS:
            files[f"project-{key}-{mode}.svg"] = card(fonts, mode, key, args.shots)
        for name, svg in files.items():
            (OUT / name).write_text(svg, encoding="utf-8")
            print(f"{name}: {len(svg.encode()) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
