"""Quiz de futebol "Monte a seleção" — Shorts verticais.
Uso: python3 render_quiz.py roteiro.json saida.mp4   (PREVIEW=1 só gera prévia)
roteiro: {"titulo": "...", "subtitulo": "...", "canal": "...",
          "rodadas": [{"pergunta": "ESCOLHA O GOLEIRO", "opcoes": [{"nome": "TAFFAREL", "numero": 1, "tipo": "goleiro|jogador|tecnico"}], "audio": "..."}],
          "audio_intro": "...", "audio_final": "...", "final": "texto da tela final"}
Cores do uniforme por roteiro: "camisa", "detalhe", "numero_cor" (RGB) — padrão: Brasil.
"""
import json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
EMOJI = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf", 109)
_f = {}
def F(s):
    s = int(s)
    if s not in _f: _f[s] = ImageFont.truetype(BOLD, s)
    return _f[s]

R = json.load(open(sys.argv[1], encoding="utf-8")); OUT = os.path.abspath(sys.argv[2])
BASE = os.path.dirname(os.path.abspath(sys.argv[1]))
TMP = os.path.join(os.path.dirname(OUT), "_cenas_quiz"); os.makedirs(TMP, exist_ok=True)
CANAL = R.get("canal", "QUIZ DO CRAQUE")
YEL, BLUE, DBLUE, WHT, BLK, GRN = (255, 205, 0), (20, 70, 200), (10, 30, 110), (255, 255, 255), (0, 0, 0), (0, 150, 70)
CAMISA = tuple(R.get("camisa", (250, 210, 0))); DETALHE = tuple(R.get("detalhe", (0, 140, 70))); NUMCOR = tuple(R.get("numero_cor", (20, 60, 180)))
TIMER = R.get("tempo_escolha", 4.0)

def ease(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3
def back(x):
    x = max(0.0, min(1.0, x)); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

# ---------------- fundo em espiral (como o modelo) ----------------
def make_swirl(c1, c2, size=2300):
    y, x = np.mgrid[-size // 2:size // 2, -size // 2:size // 2].astype(float)
    r = np.hypot(x, y); a = np.arctan2(y, x)
    v = np.sin(r / 55 + 4 * a + 3 * np.sin(r / 260))
    m = (v > 0).astype(float)[..., None]
    img = np.array(c1, float) * m + np.array(c2, float) * (1 - m)
    return Image.fromarray(np.uint8(img)).filter(ImageFilter.GaussianBlur(2))
SWIRLS = {"amarelo": make_swirl((255, 196, 20), (255, 160, 0)), "azul": make_swirl((40, 70, 210), (20, 40, 150)),
          "vermelho": make_swirl((200, 30, 60), (150, 15, 40))}
def fundo(nome, t):
    s = SWIRLS[nome].rotate(t * 12, resample=Image.BILINEAR)
    cx, cy = s.width // 2, s.height // 2
    return s.crop((cx - W // 2, cy - H // 2, cx + W // 2, cy + H // 2))

# ---------------- elementos ----------------
_em = {}
def emoji(ch, size):
    k = (ch, size)
    if k not in _em:
        im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((80, 80), ch, font=EMOJI, embedded_color=True, anchor="mm")
        im = im.crop(im.getbbox()); sc = size / max(im.size)
        _em[k] = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
    return _em[k]

def ctext(d, cx, y, t, f, fill, stroke=0, sf=BLK):
    w = d.textlength(t, font=f); d.text((cx - w / 2, y), t, font=f, fill=fill, stroke_width=stroke, stroke_fill=sf)

def fit(d, t, size, maxw):
    f = F(size)
    while d.textlength(t, font=f) > maxw and size > 20: size -= 2; f = F(size)
    return f

_cards = {}
def card(op, letra, cw=300, ch=470):
    k = (op["nome"], letra, cw)
    if k in _cards: return _cards[k]
    im = Image.new("RGBA", (cw + 40, ch + 60), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x0, y0 = 20, 30
    # sombra
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([x0 + 8, y0 + 14, x0 + cw + 8, y0 + ch + 14], 26, fill=(0, 0, 0, 110))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(im)
    # fundo do cartão: gradiente
    g = Image.new("RGBA", (cw, ch)); gd = ImageDraw.Draw(g)
    tipo = op.get("tipo", "jogador")
    top, bot = ((60, 90, 140), (25, 35, 70)) if tipo == "tecnico" else ((90, 170, 255), (20, 70, 190))
    for yy in range(ch):
        k_ = yy / ch; gd.line([0, yy, cw, yy], fill=tuple(int(top[i] * (1 - k_) + bot[i] * k_) for i in range(3)) + (255,))
    mask = Image.new("L", (cw, ch), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, cw - 1, ch - 1], 24, fill=255)
    im.paste(g, (x0, y0), mask)
    d.rounded_rectangle([x0, y0, x0 + cw, y0 + ch], 24, outline=WHT, width=7)
    # silhueta
    cx = x0 + cw / 2; hy = y0 + 120
    skin = (55, 45, 50)
    if tipo == "tecnico":
        body, coll = (40, 40, 48), (235, 235, 240)
    elif tipo == "goleiro":
        body, coll = (40, 170, 90), (20, 90, 50)
    else:
        body, coll = CAMISA, DETALHE
    d.polygon([(cx - 120, y0 + ch - 95), (cx - 110, hy + 120), (cx - 45, hy + 80), (cx + 45, hy + 80), (cx + 110, hy + 120), (cx + 120, y0 + ch - 95)], fill=body)
    d.rectangle([cx - 22, hy + 40, cx + 22, hy + 88], fill=skin)
    d.ellipse([cx - 62, hy - 70, cx + 62, hy + 62], fill=skin)
    if tipo == "tecnico":
        d.polygon([(cx - 30, hy + 80), (cx + 30, hy + 80), (cx, hy + 175)], fill=coll)
        d.polygon([(cx - 9, hy + 95), (cx + 9, hy + 95), (cx + 14, hy + 190), (cx, hy + 210), (cx - 14, hy + 190)], fill=(200, 30, 40))
    else:
        d.polygon([(cx - 45, hy + 80), (cx + 45, hy + 80), (cx, hy + 120)], fill=coll)
        if op.get("numero"):
            ctext(d, cx, hy + 140, str(op["numero"]), F(92), NUMCOR if tipo != "goleiro" else WHT)
    # faixa do nome
    by = y0 + ch - 92
    d.rounded_rectangle([x0 + 14, by, x0 + cw - 14, by + 74], 16, fill=BLUE, outline=WHT, width=4)
    f = fit(d, op["nome"], 40, cw - 50); ctext(d, cx, by + 37 - f.size * 0.6, op["nome"], f, WHT)
    # letra
    d.ellipse([x0 - 14, y0 - 22, x0 + 66, y0 + 58], fill=BLUE, outline=WHT, width=5)
    ctext(d, x0 + 26, y0 - 5, letra, F(44), WHT)
    _cards[k] = im
    return im

def header(img, num, texto, a):
    if a <= 0: return img
    d = ImageDraw.Draw(img)
    f = fit(d, texto, 62, 820); tw = d.textlength(texto, font=f)
    x0 = (W - tw) / 2 - 30 + 50; y = 250 - (1 - a) * 120
    d.rounded_rectangle([x0 - 120, y, x0 + tw + 50, y + 108], 18, fill=YEL, outline=DBLUE, width=6)
    d.rounded_rectangle([x0 - 108, y + 12, x0 - 22, y + 96], 14, fill=GRN, outline=WHT, width=4)
    ctext(d, x0 - 65, y + 20, str(num), F(58), WHT)
    d.text((x0 + 10, y + 54 - f.size * 0.6), texto, font=f, fill=DBLUE)
    return img

def timer(img, p, t):
    d = ImageDraw.Draw(img); x0, x1, y = 120, 960, 1130
    d.rounded_rectangle([x0, y, x1, y + 56], 28, fill=WHT, outline=DBLUE, width=6)
    w = (x1 - x0 - 16) * min(1, p)
    if w > 30:
        stripe = Image.new("RGB", (int(w), 40), (240, 90, 30)); sd = ImageDraw.Draw(stripe)
        for k in range(-60, int(w) + 60, 36): sd.polygon([(k + t * 120 % 36, 0), (k + 18 + t * 120 % 36, 0), (k + t * 120 % 36 - 22, 40), (k - 40 + t * 120 % 36, 40)], fill=(255, 190, 40))
        m = Image.new("L", stripe.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, stripe.width - 1, 39], 20, fill=255)
        img.paste(stripe, (x0 + 8, y + 8), m)
    ball = emoji("⚽", 92).rotate(-p * 720, resample=Image.BICUBIC, expand=False)
    img = img.convert("RGBA"); img.alpha_composite(ball, (int(x0 + 8 + w - 46), int(y - 18))); return img.convert("RGB")

def chrome(img, tg, total):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    f = F(36); tw = d.textlength(CANAL, font=f); x = (W - tw) / 2
    d.rounded_rectangle([x - 70, 1650, x + tw + 26, 1716], 33, fill=(0, 0, 0, 120))
    lay.alpha_composite(emoji("⚽", 44), (int(x - 58), 1661))
    d.text((x, 1662), CANAL, font=f, fill=(255, 255, 255, 190))
    d.rounded_rectangle([90, 1800, 990, 1812], 6, fill=(255, 255, 255, 120))
    d.rounded_rectangle([90, 1800, 90 + 900 * min(1, tg / total), 1812], 6, fill=(255, 255, 255, 255))
    return Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB")

# ---------------- áudio por cena ----------------
def audio_info(rel):
    if not rel: return None, 0.0
    p = os.path.join(BASE, rel)
    if p.endswith(".pcm"):
        wav = p[:-4] + ".wav"; subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", p, wav], check=True); p = wav
    d_ = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
    return p, d_

# ---------------- linha do tempo ----------------
scenes, total, VOZ = [], 0.0, []
p, d_ = audio_info(R.get("audio_intro")); dur = max(3.2, d_ + 0.8) if p else 3.2
if p: VOZ.append((p, total + 0.3))
scenes.append(dict(tipo="intro", dur=dur, t0=total)); total += dur
CORES_BG = ["azul", "vermelho", "amarelo"]
for i, rd in enumerate(R["rodadas"]):
    p, d_ = audio_info(rd.get("audio")); fala = d_ if p else 1.2
    t_cards = 0.35 + 0.0; t_timer = 0.35 + max(fala, 0.9) + 0.15
    dur = round((t_timer + TIMER + 0.5) * FPS) / FPS
    if p: VOZ.append((p, total + 0.25))
    scenes.append(dict(tipo="rodada", i=i, rd=rd, dur=dur, t0=total, t_timer=t_timer, bg=CORES_BG[i % 3])); total += dur
p, d_ = audio_info(R.get("audio_final")); dur = max(4.0, d_ + 1.4) if p else 4.0
if p: VOZ.append((p, total + 0.3))
scenes.append(dict(tipo="final", dur=dur, t0=total)); total += dur

def frame(S, lt):
    tg = S["t0"] + lt
    if S["tipo"] == "intro":
        img = fundo("amarelo", tg); d = ImageDraw.Draw(img)
        a = back(lt / 0.5)
        ball = emoji("⚽", int(260 * max(0.01, a))).rotate(lt * 90, resample=Image.BICUBIC)
        img = img.convert("RGBA"); img.alpha_composite(ball, (int(W / 2 - ball.width / 2), int(560 - ball.height / 2))); img = img.convert("RGB"); d = ImageDraw.Draw(img)
        b = ease((lt - 0.3) / 0.4)
        if b > 0:
            y = 760 + (1 - b) * 60
            for ln in R["titulo"].split("\n"):
                f = fit(d, ln, 100, 980); ctext(d, W / 2, y, ln, f, WHT, 10, DBLUE); y += f.size * 1.15
        c = ease((lt - 0.8) / 0.4)
        if c > 0 and R.get("subtitulo"):
            f = fit(d, R["subtitulo"], 50, 900); tw = d.textlength(R["subtitulo"], font=f)
            d.rounded_rectangle([(W - tw) / 2 - 30, 1130, (W + tw) / 2 + 30, 1130 + f.size + 40], 30, fill=BLUE, outline=WHT, width=5)
            ctext(d, W / 2, 1148, R["subtitulo"], f, WHT)
    elif S["tipo"] == "rodada":
        rd = S["rd"]; img = fundo(S["bg"], tg)
        img = header(img, S["i"] + 1, rd["pergunta"], ease(lt / 0.35))
        ops = rd["opcoes"]; n = len(ops); xs = {1: [0.5], 2: [0.3, 0.7], 3: [0.19, 0.5, 0.81]}[n]
        img = img.convert("RGBA")
        cw = 300 if n == 3 else 340
        for k, op in enumerate(ops):
            a = back((lt - 0.25 - 0.18 * k) / 0.45)
            if a <= 0.02: continue
            c = card(op, "ABC"[k], cw)
            s = max(0.05, a); cc = c.resize((int(c.width * s), int(c.height * s)), Image.BICUBIC) if abs(s - 1) > 0.01 else c
            img.alpha_composite(cc, (int(xs[k] * W - cc.width / 2), int(780 - cc.height / 2)))
        img = img.convert("RGB")
        if lt >= S["t_timer"] - 0.2:
            img = timer(img, (lt - S["t_timer"]) / TIMER, lt)
            d = ImageDraw.Draw(img)
            restante = max(0, math.ceil(TIMER - (lt - S["t_timer"])))
            if (lt - S["t_timer"]) < TIMER: ctext(d, W / 2, 1220, str(restante), F(110), WHT, 9, DBLUE)
            else: ctext(d, W / 2, 1240, "COMENTA A SUA!", F(70), YEL, 8, DBLUE)
    else:
        img = fundo("amarelo", tg); d = ImageDraw.Draw(img)
        a = back(lt / 0.5)
        ctext(d, W / 2, 330 + (1 - a) * 80, "E AÍ, QUAL É", fit(d, "E AÍ, QUAL É", 96, 960), WHT, 10, DBLUE)
        ctext(d, W / 2, 450 + (1 - a) * 80, "O SEU TIME?", fit(d, "O SEU TIME?", 96, 960), WHT, 10, DBLUE)
        # grade de respostas
        n = len(R["rodadas"]); cols = 4; bw, bh = 200, 120
        for k in range(n):
            b = ease((lt - 0.4 - 0.08 * k) / 0.3)
            if b <= 0: continue
            cx = W / 2 + (k % cols - 1.5) * (bw + 20); cy = 700 + (k // cols) * (bh + 26)
            d.rounded_rectangle([cx - bw / 2, cy, cx + bw / 2, cy + bh], 18, fill=BLUE, outline=WHT, width=5)
            ctext(d, cx, cy + 10, f"#{k + 1}", F(34), YEL); ctext(d, cx, cy + 54, "A / B / C", F(40), WHT)
        f = fit(d, R.get("final", "COMENTA SUAS ESCOLHAS!"), 64, 960)
        ctext(d, W / 2, 1060, R.get("final", "COMENTA SUAS ESCOLHAS!"), f, YEL, 8, DBLUE)
        ctext(d, W / 2, 1180, "E SEGUE PRO PRÓXIMO QUIZ ⚽".replace(" ⚽", ""), fit(d, "E SEGUE PRO PRÓXIMO QUIZ", 54, 960), WHT, 7, DBLUE)
    return chrome(img, tg, total)

if os.environ.get("PREVIEW"):
    import glob
    for f_ in glob.glob(os.path.join(TMP, "p*.png")): os.remove(f_)
    sel = [0, 1, 2, len(scenes) - 2, len(scenes) - 1]
    for j, k in enumerate(sel):
        S = scenes[k]; lt = S["dur"] * (0.75 if S["tipo"] == "rodada" else 0.9)
        frame(S, lt).resize((360, 640)).save(os.path.join(TMP, f"p{j}.png"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", os.path.join(TMP, "p%d.png"), "-vf", "tile=5x1", os.path.join(TMP, "previa.png")])
    print("total", round(total, 1)); sys.exit()

files = []
for k, S in enumerate(scenes):
    if os.environ.get("REMUX"): files.append(os.path.join(TMP, f"c{k:02d}.mp4")); continue
    tmp = os.path.join(TMP, f"c{k:02d}.tmp.mp4"); fin = os.path.join(TMP, f"c{k:02d}.mp4")
    pr = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "veryfast", "-crf", "31", "-tune", "animation", "-g", "60", "-pix_fmt", "yuv420p", tmp], stdin=subprocess.PIPE)
    nfr = int(round(S["dur"] * FPS))
    for n in range(nfr):
        img = frame(S, n / FPS)
        fade = min(1, (S["dur"] - n / FPS) / 0.12) if k < len(scenes) - 1 else min(1, (S["dur"] - n / FPS) / 0.6)
        if fade < 1: img = Image.blend(Image.new("RGB", (W, H), WHT if k < len(scenes) - 1 else BLK), img, max(0, fade))
        pr.stdin.write(img.tobytes())
    pr.stdin.close()
    if pr.wait() != 0: sys.exit(f"falha cena {k}")
    os.replace(tmp, fin); files.append(fin)

lst = os.path.join(TMP, "lista.txt"); open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
mudo = os.path.join(TMP, "mudo.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", mudo], check=True)
# música animada + tique-taque durante os cronômetros
ticks = "+".join(f"0.35*sin(2*PI*1500*t)*exp(-60*max(0,t-{S['t0'] + S['t_timer'] + j:.2f}))*gte(t,{S['t0'] + S['t_timer'] + j:.2f})"
                 for S in scenes if S["tipo"] == "rodada" for j in range(int(TIMER)))
music = ("0.28*sin(2*PI*55*t)*exp(-9*mod(t,0.4))+0.08*sin(2*PI*220*t)*exp(-7*mod(t+0.2,0.4))"
         "+0.05*sin(2*PI*(330+110*mod(floor(t/1.6),3))*t)*exp(-4*mod(t,0.8))+0.04*sin(2*PI*660*t)*exp(-12*mod(t+0.1,0.2))")
src = f"aevalsrc='{music}+{ticks}':s=44100" if ticks else f"aevalsrc='{music}':s=44100"
ins, flt = [], []
for i, (p_, t_) in enumerate(VOZ):
    ins += ["-i", p_]; flt.append(f"[{i}:a]aresample=44100,adelay={int(t_ * 1000)}:all=1[v{i}]")
nv = len(VOZ)
flt.append(f"[{nv + 1}:a]volume=0.35,afade=t=in:d=0.4,afade=t=out:st={total - 1:.2f}:d=1[m]")
if nv:
    flt.append("".join(f"[v{i}]" for i in range(nv)) + f"amix=inputs={nv}:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5,apad[v]")
    flt.append("[v][m]amix=inputs=2:duration=shortest:normalize=0[a]")
else:
    flt.append("[m]anull[a]")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *ins, "-i", mudo, "-f", "lavfi", "-t", f"{total:.2f}", "-i", src,
                "-filter_complex", ";".join(flt), "-map", f"{nv}:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                "-t", f"{total:.2f}", "-movflags", "+faststart", OUT], check=True)
print(f"ok {total:.1f}s")
