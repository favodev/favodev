"""Regenera assets/keynote-dark.svg y assets/keynote-light.svg del README de perfil.

Lee las contribuciones actuales desde la API GraphQL de GitHub y vuelve a dibujar el diseño
(gato, nombre, contador de contribuciones, línea semanal y terminal) con esos datos.

Uso:  GITHUB_TOKEN=... python scripts/build_profile.py <usuario> <carpeta_salida>
En GitHub Actions el token lo entrega el propio workflow.
Solo usa la librería estándar de Python. Las fuentes se incrustan como subset desde Google Fonts.
"""
import base64
import json
import math
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER, DEST = sys.argv[1], Path(sys.argv[2])

QUERY = """query($login: String!) {
  user(login: $login) {
    createdAt
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""
_req = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
    headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
             "Content-Type": "application/json", "User-Agent": "profile-readme-builder"},
)
_data = json.load(urllib.request.urlopen(_req, timeout=30))
if _data.get("errors"):
    raise SystemExit(f"GraphQL error: {_data['errors']}")
_user = _data["data"]["user"]
_cal = _user["contributionsCollection"]["contributionCalendar"]

WEEKLY = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in _cal["weeks"]]
TOTAL = _cal["totalContributions"]
MAXW = max(WEEKLY) or 1
TOP3 = ", ".join(str(v) for v in sorted(WEEKLY, reverse=True)[:3])
_created = datetime.fromisoformat(_user["createdAt"].replace("Z", "+00:00")).date()
YEARS = (datetime.now(timezone.utc).date() - _created).days // 365
UPTIME = f"up {YEARS} year{'' if YEARS == 1 else 's'} · load average: "

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
_font_cache = {}
OUT = Path(tempfile.mkdtemp())


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def font_face(family, weight, text, alias):
    """Descarga de Google Fonts solo los glifos de `text` y devuelve un @font-face base64."""
    chars = "".join(sorted(set(text + " ")))
    key = (family, weight, chars)
    if key not in _font_cache:
        q = urllib.parse.urlencode({"family": f"{family}:wght@{weight}", "text": chars})
        req = urllib.request.Request(f"https://fonts.googleapis.com/css2?{q}", headers={"User-Agent": UA})
        css = urllib.request.urlopen(req, timeout=30).read().decode()
        url = re.search(r"url\((https://[^)]+)\)", css).group(1)
        data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()
        _font_cache[key] = base64.b64encode(data).decode()
    return (f"@font-face{{font-family:'{alias}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{_font_cache[key]}) format('woff2');}}")


class Fonts:
    """Acumula el texto usado por cada fuente para pedir un subset exacto."""
    def __init__(self):
        self.used = {}

    def t(self, s, fam, w):
        self.used.setdefault((fam, w), []).append(s)
        return esc(s)

    def css(self):
        out = []
        for (fam, w), texts in self.used.items():
            alias = fam.replace(" ", "") + str(w)
            out.append(font_face(fam, w, "".join(texts), alias))
        return "".join(out)


def fam(f, w):
    alias = f.replace(" ", "") + str(w)
    fallback = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" if "Mono" in f else "-apple-system,'Segoe UI',Helvetica,Arial,sans-serif"
    return f"font-family:'{alias}',{fallback};font-weight:{w}"


def pct(t, T):
    return round(max(0.0, min(100.0, t / T * 100)), 3)


def write(name, body, w, h, fonts, css, title):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
           f'<title>{esc(title)}</title><style>{fonts.css()}{css}'
           '</style>'
           f'{body}</svg>')
    (OUT / name).write_text(svg, encoding="utf-8")
    print(f"{name}: {len(svg)//1024} KB")


def cat_mark(cx, cy, s, ear="#ffffff", eye="#c9d1d9", anim=True, eyes_open_color="#f5c542"):
    """Gato del avatar: orejas blancas, ojos cerrados, nariz. s = escala (1 = cabeza de ~140px)."""
    def P(x, y):
        return f"{cx + x*s:.2f} {cy + y*s:.2f}"
    ears = (f'<path d="M{P(-58,-8)} C{P(-60,-40)} {P(-54,-64)} {P(-44,-84)} C{P(-36,-66)} {P(-30,-48)} {P(-26,-22)} '
            f'C{P(-38,-26)} {P(-50,-20)} {P(-58,-8)}Z" fill="{ear}"/>'
            f'<path d="M{P(58,-8)} C{P(60,-40)} {P(54,-64)} {P(44,-84)} C{P(36,-66)} {P(30,-48)} {P(26,-22)} '
            f'C{P(38,-26)} {P(50,-20)} {P(58,-8)}Z" fill="{ear}"/>')
    sw = max(1.1, 1.7 * s)
    closed = (f'<g class="closed" fill="none" stroke="{eye}" stroke-width="{sw:.2f}" stroke-linecap="round">'
              f'<path d="M{P(-56,38)} Q{P(-38,52)} {P(-20,38)}"/><path d="M{P(20,38)} Q{P(38,52)} {P(56,38)}"/>'
              f'<path d="M{P(-56,38)} l{-4*s:.2f} {-3*s:.2f}"/><path d="M{P(56,38)} l{4*s:.2f} {-3*s:.2f}"/></g>')
    nose = f'<path d="M{P(-5,56)} Q{P(0,53)} {P(5,56)} Q{P(3,62)} {P(0,63)} Q{P(-3,62)} {P(-5,56)}Z" fill="{ear}"/>'
    return ears + closed + nose


def mini_terminal(F, css, x, y, w, h, c):
    T = 14.0
    bg = "#0b0f14"
    C = dict(g="#7ee787", cy="#56d4dd", w="#e6edf3", o="#c9d1d9", d="#6e7681", b="#79c0ff", y="#e3b341", ok="#3fb950")
    fs, cw, lh = 11, 6.6, 15
    lx = x + 16
    top, bot = y + 30, y + h - 8
    padt = 7
    V = int((bot - top - padt) // lh)
    out = [f'<rect x="{x+0.5:.1f}" y="{y+0.5:.1f}" width="{w-1:.1f}" height="{h-1:.1f}" rx="16" fill="{bg}" stroke="{c["line"]}"/>']
    out.append("".join(f'<circle cx="{x+18+i*13}" cy="{y+16}" r="4" fill="{col}"/>' for i, col in enumerate(["#ff5f57", "#febc2e", "#28c840"])))
    out.append(f'<text x="{x+w/2:.1f}" y="{y+19.5}" text-anchor="middle" fill="#6e7681" style="{fam("Geist Mono",400)};font-size:10px">{F.t("favodev@github: ~","Geist Mono",400)}</text>')

    kv = lambda k, v: ("row", [(f"{k:<9}", C["b"]), (v, C["o"])])
    script = [("cmd", "whoami"), ("out", [("Fernando Vergara", C["w"])]),
              ("blank", None), ("cmd", "cat profile.yml"),
              kv("degree:", "Ingeniero Civil Informático"), kv("role:", "full-stack & mobile developer"), kv("also:", "devops"),
              ("blank", None), ("cmd", "cat stack.yml"),
              kv("mobile:", "flutter · dart · react native"), kv("web:", "typescript · react · node"),
              kv("backend:", "java · go · python"), kv("systems:", "rust · tauri · c++"),
              kv("infra:", "docker · terraform · ci/cd"), kv("extra:", "ai development · linux"),
              ("blank", None), ("cmd", "uptime"),
              ("out", [(UPTIME, C["o"]), (TOP3, C["y"])]), ("prompt", None)]

    # tiempos de aparición
    t = 0.5
    times = []
    for kind, val in script:
        if kind == "cmd":
            times.append(t)
            t += 0.3 + len(val) * 0.07 + 0.35
        elif kind == "blank":
            times.append(None)
        elif kind == "row":
            times.append(t)
            t += 0.38
        else:
            times.append(t)
            t += 0.45
    for i in range(len(times) - 1, -1, -1):
        if times[i] is None:
            times[i] = times[i + 1]
    assert t < T * 0.8, t

    p = lambda tt: pct(tt, T)
    lines = []
    shift_pts = [(0.0, 0.0)]
    prev = 0.0
    for i, ((kind, val), ti) in enumerate(zip(script, times)):
        by = top + padt + (i + 1) * lh - 4
        sh = max(0, i + 1 - V) * lh
        if sh > prev:
            shift_pts += [(ti, prev), (ti + 0.28, sh)]
            prev = sh
        k = f"m{i}"
        css.append(f"@keyframes {k}{{0%,{max(p(ti)-0.01,0)}%{{opacity:0}}{p(ti)}%,93%{{opacity:1}}96.5%,100%{{opacity:0}}}}")
        anim = f"animation:{k} {T}s infinite"
        st = f'{fam("Geist Mono",400)};font-size:{fs}px;white-space:pre'
        if kind == "blank":
            continue
        if kind in ("cmd", "prompt"):
            pre = (f'<tspan fill="{C["cy"]}">{F.t("~ ","Geist Mono",400)}</tspan>'
                   f'<tspan fill="{C["g"]}">{F.t("$ ","Geist Mono",400)}</tspan>')
            sx = lx + 4 * cw
            if kind == "prompt":
                lines.append(f'<g style="{anim}"><text x="{lx}" y="{by:.1f}" xml:space="preserve" style="{st}">{pre}</text>'
                             f'<rect class="mblink" x="{sx:.1f}" y="{by-10:.1f}" width="{cw:.1f}" height="12" fill="{C["g"]}"/></g>')
                continue
            n = len(val)
            te = ti + 0.3 + n * 0.07
            css.append(f"@keyframes mt{i}{{0%,{p(ti+0.3)}%{{transform:translateX(0)}}{p(te)}%,100%{{transform:translateX({n*cw:.1f}px)}}}}"
                       f"@keyframes mc{i}{{0%,{max(p(ti)-0.01,0)}%{{opacity:0}}{p(ti)}%,{p(te+0.3)}%{{opacity:1}}{p(te+0.31)}%,100%{{opacity:0}}}}")
            lines.append(f'<g style="{anim}"><text x="{lx}" y="{by:.1f}" xml:space="preserve" style="{st}">{pre}'
                         f'<tspan fill="{C["w"]}">{F.t(val,"Geist Mono",400)}</tspan></text>'
                         f'<g style="animation:mt{i} {T}s infinite;animation-timing-function:steps({n},end)">'
                         f'<rect x="{sx-1:.1f}" y="{by-11:.1f}" width="{n*cw+10:.1f}" height="15" fill="{bg}"/>'
                         f'<rect x="{sx:.1f}" y="{by-10:.1f}" width="{cw:.1f}" height="12" fill="{C["g"]}" style="animation:mc{i} {T}s infinite"/></g></g>')
        else:
            tsp = "".join(f'<tspan fill="{col}">{F.t(txt,"Geist Mono",400)}</tspan>' for txt, col in val)
            lines.append(f'<text x="{lx}" y="{by:.1f}" xml:space="preserve" style="{st};{anim}">{tsp}</text>')

    # desplazamiento suave del contenido a medida que avanza
    fin = prev
    kf = "".join(f"{p(tt)}%{{transform:translateY({-v:.1f}px)}}" for tt, v in shift_pts)
    kf += f"93%{{transform:translateY({-fin:.1f}px)}}97.9%{{transform:translateY({-fin:.1f}px)}}98%,100%{{transform:translateY(0)}}"
    css.append(f"@keyframes mscroll{{{kf}}}.mscroll{{animation:mscroll {T}s ease-in-out infinite}}"
               ".mblink{animation:mbl 1.05s steps(1) infinite}@keyframes mbl{50%{opacity:0}}")
    out.append(f'<clipPath id="mclip"><rect x="{x+2}" y="{top}" width="{w-4}" height="{bot-top}"/></clipPath>'
               f'<g clip-path="url(#mclip)"><g class="mscroll">{"".join(lines)}</g></g>'
               f'<defs><linearGradient id="mfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{bg}"/>'
               f'<stop offset="1" stop-color="{bg}" stop-opacity="0"/></linearGradient></defs>'
               f'<rect class="mfadeR" x="{x+2}" y="{top}" width="{w-4}" height="12" fill="url(#mfade)"/>')
    ft = shift_pts[1][0] if len(shift_pts) > 1 else T
    css.append(f"@keyframes mfd{{0%,{p(ft)}%{{opacity:0}}{p(ft+0.28)}%,97.9%{{opacity:1}}98%,100%{{opacity:0}}}}.mfadeR{{animation:mfd {T}s infinite}}")
    return "".join(out)


def build_bento2(theme, stack=True):
    F = Fonts()
    dark = theme == "dark"
    c = dict(tile="#11161d" if dark else "#f6f8fa", line="#262d36" if dark else "#d8dee4",
             ink="#e6edf3" if dark else "#1f2328", mut="#8b949e" if dark else "#59636e", acc="#f5c542" if dark else "#b07d00",
             hero="#000000" if dark else "#0d1117", heroink="#f0f3f6", chip="#1a2029" if dark else "#eaeef2")
    W, g, LW = 840, 12, 450
    RW = W - LW - g
    R1, R2, R3 = 150, 150, 112
    H = R1 + g + R2 + ((g + R3) if stack else 0)
    T = 12.0
    parts, css = [], []

    def box(x, y, w, h, fill):
        return f'<rect x="{x+0.5:.1f}" y="{y+0.5:.1f}" width="{w-1:.1f}" height="{h-1:.1f}" rx="16" fill="{fill}" stroke="{c["line"]}"/>'

    # --- héroe: gato que despierta + nombre en una línea
    x, y, w, h = 0, 0, LW, R1 + g + R2
    parts.append('<defs><linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/>'
                 '<stop offset=".5" stop-color="#ffffff" stop-opacity=".08"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'
                 f'<clipPath id="hc"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16"/></clipPath></defs>')
    parts.append(box(x, y, w, h, c["hero"]))
    parts.append(f'<g clip-path="url(#hc)"><rect class="sheen" x="{x-260}" y="{y}" width="200" height="{h}" fill="url(#sheen)" transform="skewX(-18)"/></g>')
    s, ccx, ccy = 0.62, x + 84, y + 112
    parts.append(cat_mark(ccx, ccy, s, ear="#ffffff", eye="#bfc3c8"))
    k_ = s / 0.52
    for i in range(3):
        parts.append(f'<text class="z z{i}" x="{ccx+(24+8*i)*k_:.1f}" y="{ccy+(-50-10*i)*k_:.1f}" fill="#9aa4af" '
                     f'style="{fam("Geist Mono",400)};font-size:{(9+2*i)*k_:.1f}px">{F.t("z","Geist Mono",400)}</text>')
    parts.append(f'<text x="{x+28}" y="{y+218}" fill="{c["heroink"]}" style="{fam("Geist",600)};font-size:40px;letter-spacing:-1px">{F.t("Fernando Vergara","Geist",600)}</text>')
    parts.append(f'<text x="{x+29}" y="{y+250}" fill="#9aa4af" style="{fam("Geist",400)};font-size:15.5px">{F.t("Full-stack & mobile developer · DevOps","Geist",400)}</text>')
    parts.append(f'<circle cx="{x+34}" cy="{y+278}" r="4" fill="#3fb950" class="pulse"/>'
                 f'<text x="{x+46}" y="{y+282}" fill="#8b949e" style="{fam("Geist Mono",400)};font-size:12.5px">{F.t("coding","Geist Mono",400)}'
                 + "".join(f'<tspan class="cd cd{i}">{F.t(".","Geist Mono",400)}</tspan>' for i in range(3)) + '</text>')
    # --- contribuciones (igual que v1, ajustada al nuevo ancho)
    x, y, w, h = LW + g, 0, RW, R1
    parts.append(box(x, y, w, h, c["tile"]))
    parts.append(f'<clipPath id="odo"><rect x="{x+20}" y="{y+22}" width="170" height="46"/></clipPath><g clip-path="url(#odo)">')
    dx, di = x + 22, 0
    for ch in f"{TOTAL:,}":
        if ch == ",":
            parts.append(f'<text x="{dx}" y="{y+60}" fill="{c["ink"]}" style="{fam("Geist",600)};font-size:44px">{F.t(",","Geist",600)}</text>')
            dx += 12
            continue
        d = int(ch)
        col = "".join(f'<text x="{dx}" y="{y+60+k*50}" fill="{c["ink"]}" style="{fam("Geist",600)};font-size:44px">{F.t(str(k % 10),"Geist",600)}</text>' for k in range(11 + d))
        parts.append(f'<g style="animation:r{di} 1.6s cubic-bezier(.2,.8,.2,1) {0.3+0.15*di:.2f}s both">{col}</g>')
        css.append(f"@keyframes r{di}{{from{{transform:translateY(0)}}to{{transform:translateY({-(10+d)*50}px)}}}}")
        dx += 26
        di += 1
    parts.append('</g>')
    parts.append(f'<text x="{x+22}" y="{y+90}" fill="{c["mut"]}" style="{fam("Geist",400)};font-size:13.5px">{F.t("contributions / 12 months","Geist",400)}</text>')
    sx0, sx1, sy0, sy1 = x + 204, x + w - 20, y + 28, y + h - 26
    pts = [(sx0 + i * (sx1 - sx0) / (len(WEEKLY) - 1), sy1 - v / MAXW * (sy1 - sy0)) for i, v in enumerate(WEEKLY)]
    dpath = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    parts.append(f'<path d="{dpath} L{sx1:.1f} {sy1} L{sx0:.1f} {sy1}Z" fill="{c["acc"]}" class="area" opacity="0"/>'
                 f'<path d="{dpath}" fill="none" stroke="{c["acc"]}" stroke-width="1.8" stroke-linejoin="round" class="spark" style="stroke-dasharray:{L:.0f};stroke-dashoffset:{L:.0f}"/>')
    ex, ey = pts[-1]
    parts.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.2" fill="{c["acc"]}" class="endp"/>'
                 f'<text x="{sx0}" y="{y+h-10}" fill="{c["mut"]}" style="{fam("Geist Mono",400)};font-size:10px">{F.t(f"{len(WEEKLY)} weeks","Geist Mono",400)}</text>'
                 f'<text x="{sx1}" y="{y+h-10}" text-anchor="end" fill="{c["mut"]}" style="{fam("Geist Mono",400)};font-size:10px">{F.t(f"peak {MAXW}/wk","Geist Mono",400)}</text>')
    # --- terminal mini (reemplaza "runs on")
    x, y, w, h = LW + g, R1 + g, RW, R2
    parts.append(mini_terminal(F, css, x, y, w, h, c))
    # --- stack (opcional)
    if stack:
        x, y, w, h = 0, R1 + g + R2 + g, W, R3
        parts.append(box(x, y, w, h, c["tile"]))
        parts.append(f'<text x="{x+22}" y="{y+30}" fill="{c["mut"]}" style="{fam("Geist",400)};font-size:13.5px">{F.t("stack","Geist",400)}</text>')
        seq = "  ·  ".join(STACK) + "  ·  "
        fs = 22
        seg_w = len(seq) * fs * 0.6
        parts.append(f'<clipPath id="mq"><rect x="{x+1}" y="{y+40}" width="{w-2}" height="{h-46}"/></clipPath>'
                     f'<g clip-path="url(#mq)"><g style="animation:mq 38s linear infinite">'
                     f'<text x="{x+22}" y="{y+80}" fill="{c["ink"]}" xml:space="preserve" style="{fam("Geist Mono",400)};font-size:{fs}px;white-space:pre">{F.t(seq*2,"Geist Mono",400)}</text></g></g>'
                     f'<defs><linearGradient id="fadeL" x1="0" x2="1"><stop offset="0" stop-color="{c["tile"]}"/><stop offset="1" stop-color="{c["tile"]}" stop-opacity="0"/></linearGradient>'
                     f'<linearGradient id="fadeR" x1="1" x2="0"><stop offset="0" stop-color="{c["tile"]}"/><stop offset="1" stop-color="{c["tile"]}" stop-opacity="0"/></linearGradient></defs>'
                     f'<rect x="{x+1}" y="{y+44}" width="60" height="{h-50}" fill="url(#fadeL)"/><rect x="{x+w-61}" y="{y+44}" width="60" height="{h-50}" fill="url(#fadeR)"/>')
        css.append(f"@keyframes mq{{to{{transform:translateX({-seg_w:.0f}px)}}}}")
    css.append(".spark{animation:draw 2.4s ease-out .5s forwards}@keyframes draw{to{stroke-dashoffset:0}}"
               ".area{animation:af 1s ease 2.4s forwards}@keyframes af{to{opacity:.12}}"
               ".endp{animation:ep 2s ease-in-out 2.8s infinite;transform-box:fill-box;transform-origin:center}@keyframes ep{0%,100%{transform:scale(1)}50%{transform:scale(1.8);opacity:.5}}"
               ".pulse{animation:ep 2.2s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
               ".sheen{animation:sh 7s ease-in-out 1s infinite}@keyframes sh{0%{transform:skewX(-18deg) translateX(0)}35%,100%{transform:skewX(-18deg) translateX(820px)}}"
               ".cd0{animation:cd0 2s steps(1) infinite}.cd1{animation:cd1 2s steps(1) infinite}.cd2{animation:cd2 2s steps(1) infinite}@keyframes cd0{0%,14%{opacity:0}15%,85%{opacity:1}86%,100%{opacity:0}}@keyframes cd1{0%,34%{opacity:0}35%,85%{opacity:1}86%,100%{opacity:0}}@keyframes cd2{0%,54%{opacity:0}55%,85%{opacity:1}86%,100%{opacity:0}}"
               + ".z{opacity:0;animation:zz 3.6s ease-in infinite}.z1{animation-delay:1.2s}.z2{animation-delay:2.4s}"
               f"@keyframes zz{{0%{{opacity:0;transform:translate(0,0)}}20%{{opacity:.9}}100%{{opacity:0;transform:translate({8*k_:.1f}px,-{16*k_:.1f}px)}}}}")
    name = f"keynote2-{theme}{'' if stack else '-nostack'}.svg"
    write(name, "".join(parts), W, H, F, "".join(css), "Fernando Vergara: gato que despierta, contribuciones, plataformas y stack")

if __name__ == "__main__":
    # se construyen ambas versiones en una carpeta temporal y solo al final se reemplazan
    build_bento2("dark", False)
    build_bento2("light", False)
    DEST.mkdir(parents=True, exist_ok=True)
    for theme in ("dark", "light"):
        shutil.move(str(OUT / f"keynote2-{theme}-nostack.svg"), str(DEST / f"keynote-{theme}.svg"))
    print(f"total={TOTAL} peak={MAXW} top3={TOP3} years={YEARS} weeks={len(WEEKLY)}")
