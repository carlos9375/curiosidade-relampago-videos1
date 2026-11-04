"""Curiosidade Relâmpago — Shorts em estilo mapa animado.
Uso: python3 render_mapa.py roteiro.json saida.mp4   (PREVIEW=1 para só gerar prévia)
"""
import json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
W, H, FPS = 1080, 1920, 30
CANAL = "@CuriosidadeRelampago"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_fc = {}
def F(s):
    s = int(s)
    if s not in _fc: _fc[s] = ImageFont.truetype(BOLD, s)
    return _fc[s]

CORES = {"amarelo": (250, 205, 30), "vermelho": (225, 45, 45), "azul": (40, 90, 220), "verde": (60, 200, 90),
         "laranja": (245, 130, 20), "roxo": (140, 60, 200), "ciano": (30, 190, 220), "branco": (240, 240, 240)}
WHT, YEL, BLK = (255, 255, 255), (255, 214, 0), (0, 0, 0)
SPW = 0.36

R = json.load(open(sys.argv[1], encoding="utf-8")); OUT = os.path.abspath(sys.argv[2])
TMP = os.path.join(os.path.dirname(OUT), "_cenas_mapa"); os.makedirs(TMP, exist_ok=True)

# ---------------- dados geográficos ----------------
def rings_of(geom):
    t, c = geom["type"], geom["coordinates"]
    polys = [c] if t == "Polygon" else c if t == "MultiPolygon" else []
    return [[np.array(r, dtype=float) for r in p] for p in polys]

FEATS = {}  # id -> list of polygons(list of rings)
NAMES = {}
for f in json.load(open(os.path.join(DATA, "ne_50m_admin_0_countries.geojson")))["features"]:
    p = f["properties"]; k = p["ADM0_A3"]
    FEATS[k] = rings_of(f["geometry"]); NAMES[k] = p.get("NAME_PT") or p["NAME"]
for f in json.load(open(os.path.join(DATA, "brazil-states.geojson")))["features"]:
    k = "BR-" + f["properties"]["sigla"]; FEATS[k] = rings_of(f["geometry"]); NAMES[k] = f["properties"]["name"]
BBOX = {k: (min(r[0][:, 0].min() for r in v), min(r[0][:, 1].min() for r in v), max(r[0][:, 0].max() for r in v), max(r[0][:, 1].max() for r in v)) for k, v in FEATS.items() if v}
LAND = [k for k in FEATS if not k.startswith("BR-")]
STATES = [k for k in FEATS if k.startswith("BR-")]
RIVERS = []
for f in json.load(open(os.path.join(DATA, "ne_10m_rivers_lake_centerlines.geojson")))["features"]:
    if f["properties"].get("scalerank", 9) > 4 or not f["geometry"]: continue
    g = f["geometry"]; ls = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
    for l in ls: RIVERS.append(np.array(l, dtype=float))

def sel_polys(spec):
    """spec: 'BRA' ou {'id':'FRA','bbox':[x0,y0,x1,y1]}"""
    if isinstance(spec, str): spec = {"id": spec}
    polys = FEATS.get(spec["id"], [])
    if "bbox" in spec:
        x0, y0, x1, y1 = spec["bbox"]
        polys = [p for p in polys if x0 <= p[0][:, 0].mean() <= x1 and y0 <= p[0][:, 1].mean() <= y1]
    return polys

def centroid(polys):
    big = max(polys, key=lambda p: len(p[0])); r = big[0]
    return float(r[:, 0].mean()), float(r[:, 1].mean())

# ---------------- câmera / projeção ----------------
class Cam:
    def __init__(s, lon, lat, larg): s.lon, s.lat, s.larg = lon, lat, larg
    def setup(s):
        s.k = math.cos(math.radians(max(-70, min(70, s.lat))))
        s.sc = W / (s.larg * s.k)  # px por grau de latitude
        s.view = (s.lon - s.larg / 2 - 1, s.lat - H / s.sc / 2 - 1, s.lon + s.larg / 2 + 1, s.lat + H / s.sc / 2 + 1)
    def P(s, a):
        x = (a[:, 0] - s.lon) * s.k * s.sc + W / 2; y = -(a[:, 1] - s.lat) * s.sc + H / 2 - 80
        return np.stack([x, y], 1)
    def p(s, lon, lat):
        q = s.P(np.array([[lon, lat]])); return float(q[0, 0]), float(q[0, 1])

def lerp_cam(a, b, t):
    t = 1 - (1 - t) ** 3 if t < 1 else 1
    lg = math.exp(math.log(a.larg) + (math.log(b.larg) - math.log(a.larg)) * t)
    c = Cam(a.lon + (b.lon - a.lon) * t, a.lat + (b.lat - a.lat) * t, lg); c.setup(); return c

def visible(k, cam):
    if k not in BBOX: return False
    x0, y0, x1, y1 = BBOX[k]; v = cam.view
    return not (x1 < v[0] or x0 > v[2] or y1 < v[1] or y0 > v[3])

# ---------------- texturas ----------------
rng = np.random.default_rng(3)
def noise_tex(base, amp, blur):
    n = rng.normal(0, 1, (H // 4, W // 4)); img = Image.fromarray(np.uint8(np.clip(128 + n * 60, 0, 255))).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(img, dtype=float)[..., None] / 255 - 0.5
    return Image.fromarray(np.uint8(np.clip(np.array(base, float) + a * amp, 0, 255)))
OCEAN = noise_tex((22, 52, 78), 40, 6)
LANDTEX = noise_tex((88, 98, 52), 70, 3)
LANDTEX2 = noise_tex((120, 92, 58), 70, 3)
LANDMIX = Image.blend(LANDTEX, LANDTEX2, 0.45)

# ---------------- desenho ----------------
def ease(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

def draw_polys(d, polys, cam, fill, outline=None, width=0):
    for p in polys:
        ext = cam.P(p[0])
        if len(ext) < 3: continue
        d.polygon([tuple(q) for q in ext], fill=fill)
        for hole in p[1:]:
            hh = cam.P(hole)
            if len(hh) >= 3: d.polygon([tuple(q) for q in hh], fill=0 if fill == 255 else None)
        if outline: d.line([tuple(q) for q in ext] + [tuple(ext[0])], fill=outline, width=width)

def base_map(cam, states):
    mask = Image.new("L", (W, H), 0); md = ImageDraw.Draw(mask)
    for k in LAND:
        if visible(k, cam): draw_polys(md, FEATS[k], cam, 255)
    img = Image.composite(LANDMIX, OCEAN, mask)
    d = ImageDraw.Draw(img)
    if cam.larg < 60:
        for r in RIVERS:
            if r[:, 0].max() < cam.view[0] or r[:, 0].min() > cam.view[2] or r[:, 1].max() < cam.view[1] or r[:, 1].min() > cam.view[3]: continue
            d.line([tuple(q) for q in cam.P(r)], fill=(70, 120, 150), width=2 if cam.larg > 25 else 3)
    for k in LAND:
        if visible(k, cam): draw_polys(d, FEATS[k], cam, None, (205, 205, 185), 2)
    if states:
        for k in STATES:
            if visible(k, cam): draw_polys(d, FEATS[k], cam, None, (200, 200, 170), 1)
    return img

def highlight(img, polys, cam, cor, a):
    if a <= 0 or not polys: return img
    lift = int(10 * a)
    sh = Image.new("L", (W, H), 0); draw_polys(ImageDraw.Draw(sh), polys, cam, 255)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * 0.55 * a)))
    img = img.convert("RGBA"); img.alpha_composite(shadow, (6, 10))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    col = CORES.get(cor, cor) if isinstance(cor, str) else tuple(cor)
    for p in polys:
        ext = cam.P(p[0]); ext[:, 1] -= lift
        if len(ext) >= 3:
            ld.polygon([tuple(q) for q in ext], fill=col + (int(235 * a),))
            ld.line([tuple(q) for q in ext] + [tuple(ext[0])], fill=(255, 255, 255, int(230 * a)), width=3)
    img.alpha_composite(lay)
    return img.convert("RGB")

def label(d, x, y, t, size=46, fill=WHT, bg=None):
    f = F(size); tw = d.textlength(t, font=f)
    if bg:
        d.rounded_rectangle([x - tw / 2 - 18, y - 8, x + tw / 2 + 18, y + size + 14], 14, fill=bg)
        d.text((x - tw / 2, y), t, font=f, fill=fill)
    else:
        d.text((x - tw / 2, y), t, font=f, fill=fill, stroke_width=6, stroke_fill=BLK)

def pin(d, x, y, a, col=(235, 50, 50)):
    if a <= 0: return
    yy = y - 60 * (1 - a) - 10 * abs(math.sin(a * math.pi))
    d.ellipse([x - 14 * 1.6, y - 6, x + 14 * 1.6, y + 6], fill=(0, 0, 0))
    d.ellipse([x - 26, yy - 78, x + 26, yy - 26], fill=col, outline=WHT, width=4)
    d.polygon([(x - 20, yy - 42), (x + 20, yy - 42), (x, yy)], fill=col)
    d.ellipse([x - 10, yy - 62, x + 10, yy - 42], fill=WHT)

def xmark(d, x, y, a):
    if a <= 0: return
    s = 40 * a
    for dx in (-1, 1):
        d.line([x - s, y - s * dx, x + s, y + s * dx], fill=BLK, width=22)
        d.line([x - s, y - s * dx, x + s, y + s * dx], fill=(235, 40, 40), width=12)

def border_line(img, polys_a, polys_b, cam, a, col=(255, 230, 60)):
    """Destaca a fronteira comum (pontos de A próximos de B)."""
    if a <= 0: return img
    pts_b = np.concatenate([p[0] for p in polys_b])
    d = ImageDraw.Draw(img)
    for p in polys_a:
        r = p[0]
        if len(pts_b) == 0: break
        dmin = np.min(np.hypot(r[:, None, 0] - pts_b[None, ::3, 0], r[:, None, 1] - pts_b[None, ::3, 1]), axis=1)
        near = dmin < 0.25
        seg = []
        for i, ok in enumerate(near):
            if ok: seg.append(r[i])
            elif len(seg) > 1:
                q = cam.P(np.array(seg)); d.line([tuple(v) for v in q], fill=col, width=int(10 * a)); seg = []
            else: seg = []
        if len(seg) > 1:
            q = cam.P(np.array(seg)); d.line([tuple(v) for v in q], fill=col, width=int(10 * a))
    return img

# ---------------- legenda ----------------
def chunks(text):
    ws, out, cur = text.split(), [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= 3 or (w[-1] in ".,?!:" and len(cur) >= 2): out.append(cur); cur = []
    if cur:
        if out and len(cur) == 1: out[-1] += cur
        else: out.append(cur)
    return out
def wdur(w): return SPW + (0.22 if w[-1] in ".!?" else 0.1 if w[-1] in ",:" else 0) + 0.02 * max(0, len(w) - 8)
def build_plan(text, start):
    plan, t = [], start
    for ch in chunks(text):
        st, tt = [], t
        for w in ch: st.append(tt); tt += wdur(w)
        plan.append((t, tt, ch, st)); t = tt
    return plan, t
def caption(d, lt, plan):
    for c0, c1, words, st in plan:
        if c0 <= lt < c1:
            f = F(66); sp = d.textlength(" ", font=f)
            tw = d.textlength(" ".join(words), font=f)
            if tw > 980: f = F(66 * 980 / tw); sp = d.textlength(" ", font=f); tw = d.textlength(" ".join(words), font=f)
            pop = ease((lt - c0) / 0.12); y = 1430 + (1 - pop) * 18; x = (W - tw) / 2
            act = max(i for i, s in enumerate(st) if s <= lt)
            for i, w in enumerate(words):
                d.text((x, y), w, font=f, fill=YEL if i == act else WHT, stroke_width=7, stroke_fill=BLK); x += d.textlength(w, font=f) + sp
            return

def chrome(img, tg, total):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    top = R.get("titulo_topo")
    if top:
        f = F(50); tw = d.textlength(top, font=f)
        d.rounded_rectangle([(W - tw) / 2 - 30, 150, (W + tw) / 2 + 30, 232], 40, fill=(0, 0, 0, 150))
        d.text(((W - tw) / 2, 162), top, font=f, fill=YEL + (255,))
    f = F(34); tw = d.textlength(CANAL, font=f); x = (W - tw) / 2
    d.rounded_rectangle([x - 24, 1660, x + tw + 24, 1718], 28, fill=(0, 0, 0, 110))
    d.text((x, 1668), CANAL, font=f, fill=(255, 255, 255, 160))
    d.rounded_rectangle([90, 1800, 990, 1812], 6, fill=(255, 255, 255, 120))
    d.rounded_rectangle([90, 1800, 90 + 900 * min(1, tg / total), 1812], 6, fill=YEL + (255,))
    return Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB")

# ---------------- cenas ----------------
import unicodedata
def norm(s): return "".join(ch for ch in unicodedata.normalize("NFD", s.lower()) if ch.isalnum())

def plan_in(text, t0, t1):
    """Distribui as palavras de forma proporcional dentro do intervalo falado [t0, t1]."""
    ws = text.split(); wt = [len(w) + 2 + (6 if w[-1] in ".!?" else 3 if w[-1] in ",:" else 0) for w in ws]
    k = (t1 - t0) / sum(wt); starts, t = [], t0
    for x in wt: starts.append(t); t += x * k
    plan, i = [], 0
    for ch in chunks(text):
        st = starts[i:i + len(ch)]; i += len(ch)
        end = starts[i] if i < len(starts) else t1 + 0.4
        plan.append((st[0], end, ch, st))
    return plan

NARR = None; BOUNDS = None
if R.get("narracao"):
    NARR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), R["narracao"]))
    ndur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", NARR], capture_output=True, text=True).stdout)
    log = subprocess.run(["ffmpeg", "-i", NARR, "-af", "silencedetect=n=-35dB:d=0.25", "-f", "null", "-"], capture_output=True, text=True).stderr
    import re
    ss = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]; se = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
    sil = list(zip(ss, se + [ndur] * (len(ss) - len(se))))
    speech0 = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0
    speech1 = sil[-1][0] if sil and sil[-1][1] >= ndur - 0.05 else ndur
    gaps = [(a, b) for a, b in sil if a > speech0 + 0.1 and b < speech1 - 0.1]
    lens = [len(c["texto"]) for c in R["cenas"]]; tot = sum(lens)
    # escolhe as pausas que separam as cenas (programação dinâmica: durações mais próximas do esperado pelo nº de letras)
    K = len(lens); rate = (speech1 - speech0) / tot
    pts = [(speech0, speech0)] + gaps + [(speech1, speech1)]
    INF = float("inf"); n = len(pts)
    best = [[INF] * n for _ in range(K + 1)]; back = [[-1] * n for _ in range(K + 1)]
    best[0][0] = 0.0
    for k in range(1, K + 1):
        for j in range(1, n):
            if k < K and j == n - 1: continue
            if k == K and j != n - 1: continue
            for i in range(j):
                if best[k - 1][i] == INF: continue
                dur_ = pts[j][0] - pts[i][1]; e = lens[k - 1] * rate
                c = best[k - 1][i] + (dur_ - e) ** 2 / e
                if c < best[k][j]: best[k][j] = c; back[k][j] = i
    idx = []; j = n - 1
    for k in range(K, 0, -1): idx.append(j); j = back[k][j]
    idx = idx[::-1][:-1]
    BOUNDS = [0.0] + [round((pts[j][0] + pts[j][1]) / 2 * FPS) / FPS for j in idx] + [round((ndur + 1.2) * FPS) / FPS]
    SPANS = []  # trecho falado de cada cena, em tempo local
    for i in range(len(lens)):
        a, b = BOUNDS[i], BOUNDS[i + 1]
        s0 = max([e for s_, e in sil if s_ <= a + 0.01 and e >= a - 0.01] + [a, speech0 if i == 0 else a])
        s1 = min([s_ for s_, e in sil if s_ >= s0 + 0.2 and s_ <= b + 0.01 and e >= b - 0.01] + [min(b, speech1)])
        SPANS.append((s0 - a, s1 - a))

# --- narração por cena: cada cena tem seu próprio áudio ("audio": caminho .wav/.pcm) ---
LEAD, TAIL = 0.25, 0.45
SCENE_AUDIO = []
if all(c.get("audio") for c in R["cenas"]):
    base = os.path.dirname(os.path.abspath(sys.argv[1])); BOUNDS = [0.0]; SPANS = []
    for c in R["cenas"]:
        p = os.path.join(base, c["audio"])
        if p.endswith(".pcm"):
            wav = p[:-4] + ".wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", p, wav], check=True); p = wav
        log = subprocess.run(["ffmpeg", "-i", p, "-af", "silencedetect=n=-38dB:d=0.15", "-f", "null", "-"], capture_output=True, text=True).stderr
        import re
        d_ = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
        ss = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]; se = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
        a0 = se[0] if ss and ss[0] < 0.05 and se else 0.0
        a1 = ss[-1] if ss and (len(se) < len(ss) or se[-1] >= d_ - 0.05) else d_
        SCENE_AUDIO.append(p)
        dur_ = round((LEAD + d_ + TAIL) * FPS) / FPS
        if c is R["cenas"][-1]: dur_ = round((LEAD + d_ + 1.3) * FPS) / FPS
        BOUNDS.append(BOUNDS[-1] + dur_); SPANS.append((LEAD + a0, LEAD + a1))
    NARR = "por-cena"

scenes, total = [], 0.0
prev = None; persist = []
for si, sc in enumerate(R["cenas"]):
    if BOUNDS:
        dur = BOUNDS[si + 1] - BOUNDS[si]; plan = plan_in(sc["texto"], *SPANS[si])
    else:
        plan, end = build_plan(sc["texto"], 0.3)
        dur = max(end + 0.5, sc.get("min", 0))
    c = sc.get("camera")
    if c: cam = Cam(c["lon"], c["lat"], c["largura"]); cam.setup()
    else: cam = None
    if sc.get("limpar"): persist = []
    hl = list(persist)
    for i, h in enumerate(sc.get("destaques", [])):
        h = dict(h); h["t0"] = h.get("atraso", 0.4 + (i * sc.get("passo", 0) if sc.get("passo") else 0)); h["polys"] = sel_polys(h)
        if BOUNDS and "atraso" not in h:  # com narração: acende quando o nome é falado
            alvo = norm(h.get("palavra") or h.get("rotulo") or NAMES.get(h["id"], ""))
            for _, _, ws_, st_ in plan:
                for w_, s_ in zip(ws_, st_):
                    if alvo and norm(w_).startswith(alvo.split()[0][:5]): h["t0"] = s_ - 0.05; break
                else: continue
                break
        hl.append(h)
    persist = [dict(h, t0=-9) for h in hl]
    def word_t(alvo, dflt):
        alvo = norm(alvo)
        for _, _, ws_, st_ in plan:
            for w_, s_ in zip(ws_, st_):
                if alvo and norm(w_).startswith(alvo[:5]): return s_ - 0.05
        return dflt
    ems = []
    for i, e in enumerate(sc.get("emojis", [])):
        e = dict(e); e["t0"] = e["atraso"] if "atraso" in e else word_t(e["palavra"], 0.3 + 0.35 * i) if e.get("palavra") else 0.3 + 0.35 * i; ems.append(e)
    if sc.get("comparar"):
        for k_, it in enumerate(sc["comparar"]):
            it["t0"] = it["atraso"] if "atraso" in it else word_t(it.get("palavra", ""), 0.4 + 1.2 * k_) if it.get("palavra") else 0.4 + 1.2 * k_
    if sc.get("contador") and sc["contador"].get("palavra") and BOUNDS:
        sc["contador"]["atraso"] = word_t(sc["contador"]["palavra"], sc["contador"].get("atraso", 0.4))
    for ln in sc.get("linhas", []):
        if ln.get("palavra"): ln["atraso"] = word_t(ln["palavra"], ln.get("atraso", 0.5))
    if cam is None: hl = []; persist = []
    scenes.append(dict(sc=sc, plan=plan, dur=dur, t0=total, cam=cam, prev=(prev or cam), hl=hl, ems=ems)); total += dur
    if cam: prev = cam

# ---------------- visuais sem mapa ----------------
EMOJI_FONT = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
_emc = {}
def emoji_img(ch):
    if ch not in _emc:
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((80, 80), ch, font=EMOJI_FONT, embedded_color=True, anchor="mm")
        bb = im.getbbox(); _emc[ch] = im.crop(bb) if bb else im
    return _emc[ch]

FUNDOS = {"roxo": ((48, 16, 92), (255, 110, 40)), "azul": ((8, 40, 90), (0, 190, 220)), "verde": ((10, 60, 35), (170, 230, 40)),
          "vermelho": ((80, 8, 20), (255, 90, 60)), "laranja": ((90, 35, 5), (255, 200, 40)), "rosa": ((80, 10, 60), (255, 120, 200)),
          "noite": ((6, 8, 30), (90, 110, 255))}
_bgc = {}
rng2 = np.random.default_rng(11)
BOKEH = [(rng2.random() * W, rng2.random() * H, rng2.uniform(8, 40), rng2.uniform(10, 45), rng2.uniform(0.15, 0.5)) for _ in range(36)]
def fundo(nome, t):
    a, b = FUNDOS.get(nome, FUNDOS["roxo"])
    if nome not in _bgc:
        g = np.linspace(0, 1, H)[:, None, None]
        arr = np.array(a, float)[None, None, :] * (1 - g * 0.7) + np.array(b, float)[None, None, :] * (g * 0.45)
        img = Image.fromarray(np.uint8(np.clip(np.repeat(arr, W, axis=1), 0, 255)))
        rays = Image.new("L", (W, H), 0); rd = ImageDraw.Draw(rays)
        for k in range(14):
            ang = k * math.pi / 7
            rd.polygon([(W / 2, H * 0.38), (W / 2 + 2000 * math.cos(ang), H * 0.38 + 2000 * math.sin(ang)), (W / 2 + 2000 * math.cos(ang + 0.12), H * 0.38 + 2000 * math.sin(ang + 0.12))], fill=28)
        _bgc[nome] = (img, rays.filter(ImageFilter.GaussianBlur(6)))
    base, rays = _bgc[nome]
    img = base.copy()
    r = rays.rotate(t * 6, center=(W / 2, H * 0.38))
    img = Image.composite(Image.new("RGB", (W, H), b), img, r)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    for x, y, rr, sp, al in BOKEH:
        yy = (y - t * sp) % (H + 100) - 50
        ld.ellipse([x - rr, yy - rr, x + rr, yy + rr], fill=(255, 255, 255, int(255 * al * 0.35)))
    img = Image.alpha_composite(img.convert("RGBA"), lay.filter(ImageFilter.GaussianBlur(3)))
    return img.convert("RGB")

def paste_emoji(img, ch, cx, cy, size, rot=0, alpha=1.0, shadow=True):
    e = emoji_img(ch); sc_ = size / max(e.size)
    e = e.resize((max(1, int(e.width * sc_)), max(1, int(e.height * sc_))), Image.LANCZOS)
    if rot: e = e.rotate(rot, expand=True, resample=Image.BICUBIC)
    if alpha < 1: e.putalpha(e.split()[3].point(lambda v: int(v * alpha)))
    img = img.convert("RGBA")
    if shadow:
        sh = Image.new("RGBA", e.size, (0, 0, 0, 0)); sh.putalpha(e.split()[3].point(lambda v: int(v * 0.45)))
        sh = sh.filter(ImageFilter.GaussianBlur(max(2, size // 30)))
        img.alpha_composite(sh, (int(cx - e.width / 2 + size * 0.03), int(cy - e.height / 2 + size * 0.06)))
    img.alpha_composite(e, (int(cx - e.width / 2), int(cy - e.height / 2)))
    return img.convert("RGB")

def draw_emojis(img, S, lt):
    for e in S.get("ems", []):
        a = (lt - e["t0"]) / 0.35
        if a <= 0: continue
        pop = 1 + 0.25 * math.sin(min(1, a) * math.pi) if a < 1 else 1.0
        sz = e.get("tam", 300) * min(1, ease(a)) * pop
        cx, cy = e.get("x", 0.5) * W, e.get("y", 0.38) * H
        rot = 0; anim = e.get("anim", "flutuar"); tt = lt - e["t0"]
        if anim == "flutuar": cy += 18 * math.sin(tt * 2.2)
        elif anim == "pulsar": sz *= 1 + 0.08 * max(0, math.sin(tt * 7.5)) ** 8
        elif anim == "girar": rot = (tt * 40) % 360
        elif anim == "tremer": cx += 6 * math.sin(tt * 40); rot = 4 * math.sin(tt * 30)
        elif anim == "balançar": rot = 12 * math.sin(tt * 3)
        if e.get("multiplicar"):
            n = int(min(e["multiplicar"], max(1, (lt - e["t0"]) / 0.12)))
            cols = e.get("colunas", 6); s2 = e.get("tam", 120)
            for k in range(n):
                xx = cx + (k % cols - (cols - 1) / 2) * s2 * 1.1; yy = cy + (k // cols) * s2 * 1.1
                img = paste_emoji(img, e["e"], xx, yy, s2, shadow=False)
            continue
        if sz > 4: img = paste_emoji(img, e["e"], cx, cy, sz, rot)
        if e.get("rotulo") and a > 0.8:
            d = ImageDraw.Draw(img); label(d, cx, cy + e.get("tam", 300) / 2 + 20, e["rotulo"], e.get("tam_rotulo", 54), CORES.get(e.get("cor_rotulo"), WHT))
    return img

def draw_comparar(img, sc, lt):
    items = sc.get("comparar")
    if not items: return img
    n = len(items); vmax = max(it.get("valor", 1) for it in items)
    d = ImageDraw.Draw(img); base_y = 1080; maxh = 430
    for k, it in enumerate(items):
        a = ease((lt - it["t0"]) / 0.6)
        if a <= 0: continue
        cx = W * (k + 1) / (n + 1); bw = min(240, W / (n + 1) * 0.7)
        h = maxh * (it.get("valor", 1) / vmax) * a
        col = CORES.get(it.get("cor", ["azul", "vermelho", "verde", "laranja"][k % 4]))
        d.rounded_rectangle([cx - bw / 2, base_y - h, cx + bw / 2, base_y], 18, fill=col, outline=WHT, width=4)
        if it.get("texto_valor") and a > 0.5: label(d, cx, base_y - h - 70, it["texto_valor"], 50)
        if it.get("rotulo"): label(d, cx, base_y + 20, it["rotulo"], 44)
        img = paste_emoji(img, it["e"], cx, base_y - h - (150 if it.get("texto_valor") else 90), 140 * min(1, a * 1.3)); d = ImageDraw.Draw(img)
    return img

def linha(img, cam, ln, lt):
    """Linha animada no mapa: {'pontos': [[lon,lat],...], 'voltas': n, 'cor':..., 'atraso':..., 'duracao':...}"""
    a = (lt - ln.get("atraso", 0.5)) / ln.get("duracao", 3.0)
    if a <= 0: return img
    pts = np.array(ln["pontos"], float); voltas = ln.get("voltas", 1)
    tot = min(a, 1) * voltas
    d = ImageDraw.Draw(img); col = CORES.get(ln.get("cor", "vermelho"))
    for v in range(int(math.ceil(tot))):
        frac = min(1, tot - v); m = max(2, int(len(pts) * frac))
        q = cam.P(pts[:m]); q[:, 1] += v * 14
        d.line([tuple(p) for p in q], fill=BLK, width=16); d.line([tuple(p) for p in q], fill=col, width=9)
    return img

def frame(S, lt, tg):
    sc = S["sc"]
    if S["cam"] is None:
        img = fundo(sc.get("fundo", "roxo"), lt + S["t0"])
        return finish(S, img, None, lt, tg)
    prv = S["prev"] if S["prev"] is not None else S["cam"]
    cam = lerp_cam(prv, S["cam"], lt / sc.get("viagem", 1.4))
    img = base_map(cam, sc.get("estados", False))
    for ln in sc.get("linhas", []):
        img = linha(img, cam, ln, lt)
    for h in S["hl"]:
        img = highlight(img, h["polys"], cam, h.get("cor", "amarelo"), ease((lt - h["t0"]) / 0.4))
    for b in sc.get("fronteiras", []):
        img = border_line(img, sel_polys(b["a"]), sel_polys(b["b"]), cam, ease((lt - b.get("atraso", 0.8)) / 0.5))
    d = ImageDraw.Draw(img)
    for h in S["hl"]:
        if h.get("rotulo") and h["polys"]:
            a = ease((lt - h["t0"] - 0.2) / 0.3)
            if a > 0:
                lon, lat = h.get("pos", centroid(h["polys"])); x, y = cam.p(lon, lat)
                label(d, x, y - 30 - 10 * a, h["rotulo"], h.get("tam", 44))
    for i, x_ in enumerate(sc.get("xis", [])):
        polys = sel_polys(x_); lon, lat = x_.get("pos") or centroid(polys); x, y = cam.p(lon, lat)
        t_x = x_.get("atraso")
        if t_x is None:
            t_x = next((h["t0"] + 0.35 for h in S["hl"] if h.get("id") == x_.get("id") and h["t0"] > -1), 1.0 + i * 0.4)
        xmark(d, x, y, ease((lt - t_x) / 0.25))
    for pn in sc.get("pinos", []):
        x, y = cam.p(pn["lon"], pn["lat"]); a = ease((lt - pn.get("atraso", 0.5)) / 0.4)
        pin(d, x, y, a)
        if pn.get("texto") and a > 0.6: label(d, x, y - 150, pn["texto"], 42, WHT, (0, 0, 0, 180) if False else None)
    for r_ in sc.get("rotulos", []):
        a = ease((lt - r_.get("atraso", 0.6)) / 0.3)
        if a > 0:
            x, y = cam.p(r_["lon"], r_["lat"]); label(d, x, y, r_["texto"], r_.get("tam", 44), CORES.get(r_.get("cor"), WHT))
    return finish(S, img, cam, lt, tg)

def finish(S, img, cam, lt, tg):
    sc = S["sc"]
    img = draw_emojis(img, S, lt)
    img = draw_comparar(img, sc, lt)
    d = ImageDraw.Draw(img)
    if sc.get("contador"):
        c = sc["contador"]; a = (lt - c.get("atraso", 0.4)) / c.get("duracao", 2.5)
        if a > 0 or c.get("seguir_destaques"):
            n = int(round(c["de"] + (c["ate"] - c["de"]) * min(1, a)))
            if c.get("seguir_destaques"): n = sum(1 for h in S["hl"] if h["t0"] > -1 and h["t0"] <= lt)
            rot = c.get("rotulo", ""); txt = f"{n:,}".replace(",", ".") + (rot if rot.startswith("%") else (" " + rot if rot else ""))
            f = F(96); tw = d.textlength(txt, font=f)
            if tw > 860: f = F(96 * 860 / tw); tw = d.textlength(txt, font=f)
            d.rounded_rectangle([(W - tw) / 2 - 40, 1150, (W + tw) / 2 + 40, 1290], 40, fill=(20, 170, 140), outline=WHT, width=5)
            d.text(((W - tw) / 2, 1165), txt, font=f, fill=WHT)
    if sc.get("grande"):
        g = sc["grande"]; a = ease((lt - 0.2) / 0.4)
        if a > 0:
            f = F(g.get("tam", 120)); lines = g["texto"].split("\n"); y = g.get("y", 300)
            for ln in lines:
                tw = d.textlength(ln, font=f); d.text(((W - tw) / 2, y + (1 - a) * 40), ln, font=f, fill=CORES.get(g.get("cor"), WHT), stroke_width=9, stroke_fill=BLK); y += f.size * 1.15
    caption(d, lt, S["plan"])
    img = chrome(img, tg, total)
    return img

if os.environ.get("PREVIEW"):
    import glob
    for f_ in glob.glob(os.path.join(TMP, "p*.png")): os.remove(f_)
    for k, S in enumerate(scenes):
        lt = S["dur"] * 0.85; frame(S, lt, S["t0"] + lt).resize((360, 640)).save(os.path.join(TMP, f"p{k}.png"))
    n = len(scenes); cols = min(4, n)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(TMP, "p%d.png"), "-vf", f"tile={cols}x{math.ceil(n / cols)}", os.path.join(TMP, "previa.png")])
    print("total", round(total, 1)); sys.exit()

files = []
for k, S in enumerate(scenes):
    tmp = os.path.join(TMP, f"c{k:02d}.tmp.mp4"); fin = os.path.join(TMP, f"c{k:02d}.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-g", "60", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    nfr = int(round(S["dur"] * FPS))
    for n in range(nfr):
        lt = n / FPS; img = frame(S, lt, S["t0"] + lt)
        fade = min(1, (S["dur"] - lt) / 0.15) if k < len(scenes) - 1 else min(1, (S["dur"] - lt) / 0.6)
        if fade < 1: img = Image.blend(Image.new("RGB", (W, H), (255, 255, 255) if k < len(scenes) - 1 else (0, 0, 0)), img, max(0, fade))
        p.stdin.write(img.tobytes())
        if n == nfr // 2 and k == 2: img.save(OUT.replace(".mp4", "_preview.png"))
    p.stdin.close()
    if p.wait() != 0: sys.exit(f"falha cena {k}")
    os.replace(tmp, fin); files.append(fin)

lst = os.path.join(TMP, "lista.txt"); open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
mudo = os.path.join(TMP, "mudo.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", mudo], check=True)
music = ("aevalsrc='0.30*sin(2*PI*55*t)*exp(-10*mod(t,0.5))+0.06*sin(2*PI*220*t)*exp(-6*mod(t+0.25,0.5))"
         "+0.05*sin(2*PI*(330+110*mod(floor(t/4),2))*t)*exp(-3*mod(t,1))+0.04*sin(2*PI*494*t)*exp(-4*mod(t+0.5,1))':s=44100")
if SCENE_AUDIO:
    narr = os.path.join(TMP, "narracao.wav")
    ins, flt = [], []
    for i, p in enumerate(SCENE_AUDIO):
        ins += ["-i", p]; ms = int((BOUNDS[i] + LEAD) * 1000)
        flt.append(f"[{i}:a]aresample=44100,adelay={ms}:all=1[a{i}]")
    flt.append("".join(f"[a{i}]" for i in range(len(SCENE_AUDIO))) + f"amix=inputs={len(SCENE_AUDIO)}:normalize=0:duration=longest[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-filter_complex", ";".join(flt), "-map", "[o]", narr], check=True)
    NARR = narr
if NARR:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mudo, "-f", "lavfi", "-t", f"{total:.2f}", "-i", music, "-i", NARR,
                    "-filter_complex", f"[1:a]volume=0.16,afade=t=in:d=0.5,afade=t=out:st={total - 1.2:.2f}:d=1.2[m];"
                    "[2:a]aresample=44100,loudnorm=I=-15:TP=-1.5:LRA=11,apad[v];[v][m]amix=inputs=2:duration=shortest:normalize=0[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", "-movflags", "+faststart", OUT], check=True)
else:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mudo, "-f", "lavfi", "-t", f"{total:.2f}", "-i", music,
                "-filter:a", f"volume=0.55,afade=t=in:d=0.5,afade=t=out:st={total - 1.2:.2f}:d=1.2",
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", OUT], check=True)
print(f"ok {total:.1f}s")
