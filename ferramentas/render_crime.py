"""Dossiê Sombrio — piloto. Uso: python3 render_crime.py roteiro.json saida.mp4"""
import json, math, os, random, subprocess, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
CANAL = "@DossieSombrio-e3o"
B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
_fc = {}
def F(s, p=B):
    k = (s, p)
    if k not in _fc: _fc[k] = ImageFont.truetype(p, s)
    return _fc[k]

RED, DRED, WHT, YEL, PAPER, INK = (220, 30, 40), (120, 10, 15), (240, 240, 240), (255, 200, 40), (225, 214, 186), (40, 30, 25)
SPW = 0.34  # segundos por palavra

R = json.load(open(sys.argv[1], encoding="utf-8")); OUT = sys.argv[2]
TMP = os.path.join(os.path.dirname(os.path.abspath(OUT)), "_cenas"); os.makedirs(TMP, exist_ok=True)

def ease(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3

# ---------- fundo ----------
random.seed(1)
def make_bg():
    img = Image.new("RGB", (W, H), (8, 6, 8)); d = ImageDraw.Draw(img)
    v = Image.new("L", (W // 4, H // 4), 0); dv = ImageDraw.Draw(v)
    dv.ellipse([-60, 40, W // 4 + 60, H // 4 - 40], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(60)).resize((W, H))
    red = Image.new("RGB", (W, H), (45, 8, 12))
    img = Image.composite(red, img, v)
    return img
BG = make_bg()
NOISE = []
for i in range(4):
    n = Image.effect_noise((W // 2, H // 2), 40).resize((W, H)).convert("RGB")
    NOISE.append(n)

def ctext(d, cx, y, t, f, fill, stroke=0, sf=(0, 0, 0)):
    w = d.textlength(t, font=f); d.text((cx - w / 2, y), t, font=f, fill=fill, stroke_width=stroke, stroke_fill=sf)

def zodiac(d, cx, cy, r, col, w=10):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=w)
    d.line([cx - r - 30, cy, cx + r + 30, cy], fill=col, width=w)
    d.line([cx, cy - r - 30, cx, cy + r + 30], fill=col, width=w)

def stamp(img, text, cx, cy, a, col=RED, size=64, rot=-12):
    if a <= 0 or not text: return img
    f = F(size); tw = ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f); CW = int(tw + 120)
    tmp = Image.new("RGBA", (CW, 220), (0, 0, 0, 0)); d = ImageDraw.Draw(tmp); x0 = (CW - tw) / 2
    d.rounded_rectangle([x0 - 26, 50, x0 + tw + 26, 60 + size + 40], 12, outline=col + (230,), width=8)
    d.text((x0, 65), text, font=f, fill=col + (230,))
    s = 1.6 - 0.6 * a
    tmp = tmp.rotate(rot, expand=True, resample=Image.BICUBIC)
    tmp = tmp.resize((int(tmp.width * s), int(tmp.height * s)))
    al = tmp.split()[3].point(lambda p: int(p * min(1, a * 1.5)))
    tmp.putalpha(al)
    img = img.convert("RGBA"); img.alpha_composite(tmp, (int(cx - tmp.width / 2), int(cy - tmp.height / 2)))
    return img.convert("RGB")

GLYPHS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ+/<>^#%&@=")
def cipher(d, x0, y0, cols, rows, cell, reveal, seed):
    rnd = random.Random(seed); n = int(cols * rows * reveal)
    for i in range(cols * rows):
        if i >= n: break
        c, r = i % cols, i // cols
        g = rnd.choice(GLYPHS)
        flip = rnd.random() < 0.3
        d.text((x0 + c * cell, y0 + r * cell), g.lower() if flip else g, font=F(int(cell * 0.8), M), fill=INK)

def paper(img, box, rot=0):
    x0, y0, x1, y1 = box
    p = Image.new("RGBA", (x1 - x0, y1 - y0), PAPER + (255,))
    pd = ImageDraw.Draw(p)
    for y in range(0, y1 - y0, 4):
        pd.line([0, y, x1 - x0, y], fill=(215 - (y % 12), 203 - (y % 12), 175 - (y % 12), 255))
    if rot: p = p.rotate(rot, expand=True, resample=Image.BICUBIC)
    sh = Image.new("RGBA", (p.width + 40, p.height + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([20, 30, p.width + 20, p.height + 30], fill=(0, 0, 0, 160))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    img = img.convert("RGBA"); img.alpha_composite(sh, (x0 - 20, y0 - 20)); img.alpha_composite(p, (x0, y0))
    return img.convert("RGB")

# ---------- visuais por cena ----------
D = {}
def vis(kind, img, lt, dur):
    d = ImageDraw.Draw(img); a = ease(lt / 0.6)
    if kind == "titulo":
        zodiac(d, W / 2, 560, int(150 * (0.7 + 0.3 * a)), RED, 14)
        t = D.get("linha1", "").upper(); n = int(len(t) * min(1, lt / 0.8))
        ctext(d, W / 2, 780, t[:n], F(96, SERIF), WHT, 4)
        t2 = D.get("linha2", "").upper(); n2 = int(len(t2) * min(1, max(0, lt - 0.6) / 0.8))
        ctext(d, W / 2, 890, t2[:n2], F(110, SERIF), RED, 4)
    elif kind == "mapa":
        img = paper(img, (130, 400, 950, 1040), 0); d = ImageDraw.Draw(img)
        rnd = random.Random(4)
        pts = [(160 + i * 26, 520 + int(90 * math.sin(i / 5)) + rnd.randint(-12, 12)) for i in range(31)]
        d.line(pts, fill=(120, 110, 90), width=6)
        for i in range(8):
            d.line([150, 450 + i * 75, 930, 450 + i * 75], fill=(200, 188, 160), width=2)
        py = 720 - 40 * ease(lt / 0.4)
        d.ellipse([520, py - 40, 600, py + 40], fill=RED); d.polygon([(528, py + 20), (592, py + 20), (560, py + 95)], fill=RED)
        d.ellipse([545, py - 15, 575, py + 15], fill=PAPER)
        ctext(d, W / 2, 860, D.get("local", "").upper(), F(56), INK)
        if lt > 0.7: ctext(d, W / 2, 940, D.get("data", "").upper(), F(50, M), DRED)
    elif kind == "carta":
        img = paper(img, (180, 380, 900, 1060), 0); d = ImageDraw.Draw(img)
        ctext(d, 540, 420, D.get("cabecalho", "").upper(), F(30, M), INK)
        lines = int(9 * min(1, lt / 1.6))
        rnd = random.Random(9)
        for i in range(lines):
            w = rnd.randint(380, 600); d.line([240, 520 + i * 52, 240 + w, 520 + i * 52], fill=(70, 60, 140), width=7)
        if lt > 1.0: zodiac(d, 780, 960, 48, (70, 60, 140), 7)
    elif kind in ("cifra408", "cifra340", "documento"):
        img = paper(img, (110, 380, 970, 1060), 0); d = ImageDraw.Draw(img)
        cipher(d, 150, 410, 17, 13, 47, min(1, lt / 1.8), (hash(D.get("carimbo", "")) % 50))
        if D.get("contador"):
            yrs = int(D["contador"] * min(1, max(0, lt - 0.8) / 2.0))
            d.rounded_rectangle([300, 1080, 780, 1160], 16, fill=(0, 0, 0))
            ctext(d, 540, 1088, f"{yrs} ANOS" if yrs < D["contador"] else D.get("faixa", f"{yrs} ANOS").upper(), F(48, M), YEL)
        s = max(0, (lt - (3.2 if D.get("contador") else 1.6)) / 0.3)
        img = stamp(img, D.get("carimbo", "ARQUIVADO").upper(), 560, 720, ease(s))
    elif kind == "citacao":
        img = paper(img, (120, 420, 960, 1020), 2); d = ImageDraw.Draw(img)
        q = D.get("texto", R.get("citacao", "")); n = int(len(q) * min(1, lt / 2.2))
        words, line, y = q[:n].split(" "), "", 500
        for w in words:
            t = (line + " " + w).strip()
            if d.textlength(t, font=F(54, M)) > 740: d.text((170, y), line, font=F(54, M), fill=(70, 60, 140)); y += 78; line = w
            else: line = t
        d.text((170, y), line + ("_" if int(lt * 3) % 2 else ""), font=F(54, M), fill=(70, 60, 140))
        if lt > 2.4: d.text((170, 900), "— " + D.get("fonte", ""), font=F(34, M), fill=INK)
    elif kind == "numeros":
        b = ease(lt / 0.5)
        d.text((150, 470), D.get("rotulo1", "").upper(), font=F(54), fill=(170, 170, 170))
        ctext(d, 270, 540, str(int(D.get("valor1", 0) * b)), F(220, SERIF), WHT, 4)
        d.text((610, 470), D.get("rotulo2", "").upper(), font=F(54), fill=(170, 170, 170))
        c = ease((lt - 0.6) / 0.5)
        ctext(d, 790, 540, str(int(D.get("valor2", 0) * c)), F(220, SERIF), RED, 4)
        d.line([540, 480, 540, 800], fill=(90, 90, 90), width=4)
        img = stamp(img, D.get("carimbo", "").upper(), 540, 950, ease((lt - 1.6) / 0.3), RED, 50, -6)
    elif kind == "final":
        zodiac(d, W / 2, 640, 150, DRED, 12)
        ctext(d, W / 2, 610, "?", F(200, SERIF), WHT, 6)
        if lt > 0.4: ctext(d, W / 2, 880, D.get("status", "CASO AINDA ABERTO").upper(), F(70), RED, 4)
    return img

# ---------- legenda em blocos (2-4 palavras, palavra ativa destacada) ----------
def chunks(text):
    ws, out, cur = text.split(), [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= 4 or w[-1] in ".,?!:" and len(cur) >= 2:
            out.append(cur); cur = []
    if cur:
        if out and len(cur) == 1: out[-1] += cur
        else: out.append(cur)
    return out

def wdur(w): return SPW + (0.22 if w[-1] in ".!?" else 0.1 if w[-1] in ",:" else 0) + 0.02 * max(0, len(w) - 8)

def caption(d, lt, plan):
    for c0, c1, words, starts in plan:
        if c0 <= lt < c1:
            f = F(76)
            space = d.textlength(" ", font=f)
            lines, cur = [], []
            for i, w in enumerate(words):
                if cur and d.textlength(" ".join(x for _, x in cur + [(i, w)]), font=f) > 920:
                    lines.append(cur); cur = []
                cur.append((i, w))
            lines.append(cur)
            pop = ease((lt - c0) / 0.15)
            y = 1250 - (len(lines) - 1) * 50 + (1 - pop) * 25
            active = max(i for i, s in enumerate(starts) if s <= lt)
            for ln in lines:
                tw = d.textlength(" ".join(w for _, w in ln), font=f); x = (W - tw) / 2
                for i, w in ln:
                    col = YEL if i == active else WHT
                    d.text((x, y), w.upper() if False else w, font=f, fill=col, stroke_width=7, stroke_fill=(0, 0, 0))
                    x += d.textlength(w, font=f) + space
                y += 100
            return

def build_plan(text, start):
    plan, t = [], start
    for ch in chunks(text):
        starts, tt = [], t
        for w in ch: starts.append(tt); tt += wdur(w)
        plan.append((t, tt, ch, starts)); t = tt
    return plan, t

def chrome(img, t_global, total, case_no):
    d = ImageDraw.Draw(img)
    d.text((70, 120), "DOSSIÊ SOMBRIO", font=F(40, M), fill=RED)
    tw = d.textlength(case_no, font=F(40, M)); d.text((W - 70 - tw, 120), case_no, font=F(40, M), fill=(170, 170, 170))
    d.line([70, 180, W - 70, 180], fill=DRED, width=3)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
    f = F(36); tw = ld.textlength(CANAL, font=f); x = (W - tw) / 2
    ld.rounded_rectangle([x - 26, 1650, x + tw + 26, 1712], 30, fill=(0, 0, 0, 120))
    ld.text((x, 1660), CANAL, font=f, fill=(255, 255, 255, 150))
    ld.rectangle([70, 1800, 70 + 940 * min(1, t_global / total), 1808], fill=RED + (230,))
    img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    return img

# ---------- monta e renderiza cenas ----------
def plan_in(text, t0, t1):
    ws = text.split(); wt = [len(w) + 2 + (6 if w[-1] in ".!?" else 3 if w[-1] in ",:" else 0) for w in ws]
    k = (t1 - t0) / sum(wt); starts, t = [], t0
    for x in wt: starts.append(t); t += x * k
    plan, i = [], 0
    for ch in chunks(text):
        st = starts[i:i + len(ch)]; i += len(ch)
        plan.append((st[0], starts[i] if i < len(starts) else t1 + 0.4, ch, st))
    return plan

import re
LEAD, TAIL = 0.3, 0.5
SCENE_AUDIO = []
NARRADO = all(c.get("audio") for c in R["cenas"])
scenes, total = [], 0.0
for si, sc in enumerate(R["cenas"]):
    if NARRADO:
        p_ = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), sc["audio"])
        if p_.endswith(".pcm"):
            wav = p_[:-4] + ".wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", p_, wav], check=True); p_ = wav
        d_ = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p_], capture_output=True, text=True).stdout)
        log = subprocess.run(["ffmpeg", "-i", p_, "-af", "silencedetect=n=-38dB:d=0.15", "-f", "null", "-"], capture_output=True, text=True).stderr
        ss = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]; se = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
        a0 = se[0] if ss and ss[0] < 0.05 and se else 0.0
        a1 = ss[-1] if ss and (len(se) < len(ss) or se[-1] >= d_ - 0.05) else d_
        SCENE_AUDIO.append((p_, total + LEAD))
        dur = round((LEAD + d_ + (1.5 if si == len(R["cenas"]) - 1 else TAIL)) * FPS) / FPS
        plan = plan_in(sc["texto"], LEAD + a0, LEAD + a1)
    else:
        plan, end = build_plan(sc["texto"], 0.25)
        dur = max(end + 0.45, sc.get("min", 0))
    scenes.append((sc["visual"], plan, dur, total, sc.get("dados", {}))); total += dur

if os.environ.get("PREVIEW"):
    for k, (kind, plan, dur, t0, dd) in enumerate(scenes):
        D.clear(); D.update(dd); lt = dur * 0.8
        img = vis(kind, BG.copy(), lt, dur); caption(ImageDraw.Draw(img), lt, plan)
        img = chrome(img, t0 + lt, total, R["caso"]); img.resize((360, 640)).save(os.path.join(TMP, f"p{k}.png"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(TMP, "p%d.png"), "-vf", "tile=4x2", os.path.join(TMP, "previa.png")])
    print("total", round(total, 1)); sys.exit()

files = []
for k, (kind, plan, dur, t0, dd) in enumerate(scenes):
    D.clear(); D.update(dd)
    tmp = os.path.join(TMP, f"c{k:02d}.tmp.mp4"); fin = os.path.join(TMP, f"c{k:02d}.mp4")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-tune", "stillimage", "-g", "60", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    nfr = int(round(dur * FPS))
    for n in range(nfr):
        lt = n / FPS
        img = BG.copy()
        img = vis(kind, img, lt, dur)
        d = ImageDraw.Draw(img); caption(d, lt, plan)
        img = chrome(img, t0 + lt, total, R["caso"])
        img = Image.blend(img, NOISE[0], 0.04)
        fade = min(1, lt / 0.2, (dur - lt) / 0.2)
        if fade < 1: img = Image.blend(Image.new("RGB", (W, H)), img, max(0, fade))
        p.stdin.write(img.tobytes())
        if k == 3 and n == nfr - 5: img.save(OUT.replace(".mp4", "_prev1.png"))
        if k == 1 and n == int(nfr * 0.6): img.save(OUT.replace(".mp4", "_prev0.png"))
    p.stdin.close()
    if p.wait() == 0: os.replace(tmp, fin); files.append(fin)
    else: sys.exit("falha cena %d" % k)

lst = os.path.join(TMP, "lista.txt"); open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
silent = os.path.join(TMP, "mudo.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
music = ("aevalsrc='0.20*sin(2*PI*55*t)*(0.6+0.4*sin(2*PI*0.25*t))+0.12*sin(2*PI*82.4*t)*(0.5+0.5*sin(2*PI*0.13*t))"
         "+0.06*sin(2*PI*110*t+3*sin(2*PI*0.5*t))+0.25*sin(2*PI*45*t)*exp(-4*mod(t,1.6))"
         "+0.03*sin(2*PI*660*t)*exp(-2*mod(t+0.8,3.2))':s=44100")
if SCENE_AUDIO:
    ins, flt = [], []
    for i, (p_, t_) in enumerate(SCENE_AUDIO):
        ins += ["-i", p_]; flt.append(f"[{i}:a]aresample=44100,adelay={int(t_ * 1000)}:all=1[a{i}]")
    n = len(SCENE_AUDIO)
    flt.append("".join(f"[a{i}]" for i in range(n)) + f"amix=inputs={n}:normalize=0:duration=longest,loudnorm=I=-15:TP=-1.5:LRA=11,apad[v]")
    flt.append(f"[{n + 1}:a]volume=0.22,lowpass=f=2500,afade=t=in:d=1,afade=t=out:st={total-1.5:.2f}:d=1.5[m]")
    flt.append("[v][m]amix=inputs=2:duration=shortest:normalize=0[a]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-i", silent, "-f", "lavfi", "-t", f"{total:.2f}", "-i", music,
                    "-filter_complex", ";".join(flt), "-map", f"{n}:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                    "-t", f"{total:.2f}", "-movflags", "+faststart", OUT], check=True)
else:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-f", "lavfi", "-t", f"{total:.2f}", "-i", music,
                "-filter:a", f"volume=0.7,lowpass=f=2500,afade=t=in:d=1,afade=t=out:st={total-1.5:.2f}:d=1.5",
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", OUT], check=True)
print(f"ok {total:.1f}s")
