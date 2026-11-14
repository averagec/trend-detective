import json, math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
W = '.cache'
F = lambda n, s: ImageFont.truetype(f'scripts/fonts/{n}.ttf', s)
flipv = lambda im: im.transpose(Image.FLIP_TOP_BOTTOM)
PAPER = (239, 235, 225)
INK = (29, 27, 23)
RED = (176, 40, 30)
GREEN = (120, 255, 150)
AMBER = (245, 196, 107)

def monitor():
    src = Image.open(f'{W}/tex/img20.jpg').convert('RGB')
    S = Image.new('RGB', (912, 512), (14, 26, 64))
    d = ImageDraw.Draw(S)
    g = (236, 230, 214)
    gd = (120, 150, 205)
    d.rectangle([0, 0, 912, 34], fill=(40, 78, 160))
    d.text((18, 6), 'TD-OS  //  EARTH SYSTEM CASE TERMINAL', font=F('VT323', 26), fill=g)
    d.text((740, 6), '23:47  SGT', font=F('VT323', 26), fill=g)
    cx, cy, r = (456, 200, 92)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=g, width=4)
    for k in (0.35, 0.7):
        d.ellipse([cx - r * k, cy - r, cx + r * k, cy + r], outline=g, width=2)
    for la in (-0.5, 0, 0.5):
        yy = cy + la * r
        half = math.sqrt(max(0, r * r - (la * r) ** 2))
        d.line([cx - half, yy, cx + half, yy], fill=g, width=2)
    d.ellipse([cx - 150, cy - 34, cx + 150, cy + 34], outline=(90, 205, 190), width=2)
    d.rectangle([cx + 138, cy - 22, cx + 154, cy - 10], fill=(240, 180, 60))
    t = 'TREND DETECTIVE'
    fnt = F('VT323', 78)
    tw = d.textlength(t, font=fnt)
    d.text((cx - tw / 2, 306), t, font=fnt, fill=g)
    s = '4 CASES PENDING  .  1 HYPOTHESIS UNSEALED'
    f2 = F('VT323', 30)
    d.text((cx - d.textlength(s, font=f2) / 2, 392), s, font=f2, fill=gd)
    s = '> CLICK TO LOG IN_'
    f3 = F('VT323', 40)
    d.text((cx - d.textlength(s, font=f3) / 2, 440), s, font=f3, fill=(90, 205, 190))
    glow = S.filter(ImageFilter.GaussianBlur(4))
    S = Image.blend(S, glow, 0.2)
    a = np.array(S).astype(np.float32)
    a[::3] *= 0.72
    S = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    src.paste(flipv(S), (0, 0))
    return src

def icon(d, kind, box, col):
    x0, y0, x1, y1 = box
    w, h = (x1 - x0, y1 - y0)
    P = lambda u, v: (x0 + u * w, y0 + v * h)
    lw = 3
    if kind == 'trend':
        d.line([P(0.1, 0.85), P(0.9, 0.15)], fill=col, width=lw)
        d.line([P(0.7, 0.15), P(0.9, 0.15), P(0.9, 0.35)], fill=col, width=lw)
    elif kind == 'season':
        pts = [P(i / 40, 0.5 - 0.35 * math.sin(i / 40 * math.pi * 4)) for i in range(41)]
        d.line(pts, fill=col, width=lw)
    elif kind == 'noise':
        import random
        rnd = random.Random(3)
        pts = [P(i / 16, 0.5 + rnd.uniform(-0.35, 0.35)) for i in range(17)]
        d.line(pts, fill=col, width=lw)
    elif kind == 'spike':
        for i, hh in enumerate([0.3, 0.4, 0.9, 0.35, 0.45]):
            u = 0.12 + i * 0.18
            d.line([P(u, 0.9), P(u, 0.9 - hh * 0.8)], fill=col, width=6)
    elif kind == 'calendar':
        d.rectangle([P(0.15, 0.2), P(0.85, 0.9)], outline=col, width=lw)
        d.line([P(0.15, 0.38), P(0.85, 0.38)], fill=col, width=lw)
        d.line([P(0.3, 0.62), P(0.45, 0.76), P(0.72, 0.5)], fill=col, width=lw)
    elif kind == 'swap':
        d.rectangle([P(0.1, 0.25), P(0.4, 0.55)], outline=col, width=lw)
        d.rectangle([P(0.6, 0.25), P(0.9, 0.55)], outline=col, width=lw)
        d.line([P(0.4, 0.4), P(0.6, 0.4)], fill=col, width=lw)
        d.line([P(0.25, 0.55), P(0.25, 0.8), P(0.75, 0.8), P(0.75, 0.55)], fill=col, width=lw)
    elif kind == 'sat':
        d.rectangle([P(0.4, 0.38), P(0.6, 0.62)], outline=col, width=lw)
        d.rectangle([P(0.05, 0.43), P(0.33, 0.57)], fill=col)
        d.rectangle([P(0.67, 0.43), P(0.95, 0.57)], fill=col)
    elif kind == 'station':
        d.line([P(0.5, 0.2), P(0.5, 0.9)], fill=col, width=lw)
        d.line([P(0.3, 0.9), P(0.7, 0.9)], fill=col, width=lw)
        d.ellipse([P(0.42, 0.08), P(0.58, 0.24)], outline=col, width=lw)
        d.line([P(0.5, 0.35), P(0.25, 0.5)], fill=col, width=lw)
        d.line([P(0.5, 0.35), P(0.75, 0.5)], fill=col, width=lw)
    elif kind == 'drop':
        pts = [P(0.5, 0.1)] + [P(0.5 + 0.28 * math.sin(t), 0.62 - 0.28 * math.cos(t)) for t in [i / 20 * math.pi * 2 - math.pi / 2 for i in range(5, 16)]] + [P(0.5, 0.1)]
        d.line(pts, fill=col, width=lw)
    elif kind == 'model':
        for i in range(3):
            d.rectangle([P(0.15 + i * 0.1, 0.2 + i * 0.12), P(0.65 + i * 0.1, 0.55 + i * 0.12)], outline=col, width=2)
    elif kind == 'chart':
        import random
        rnd = random.Random(9)
        p = 0
        pts = []
        for i in range(30):
            p = 0.5 * p + rnd.uniform(-0.12, 0.12)
            pts.append(P(i / 29, 0.75 - i / 29 * 0.45 + p))
        d.line(pts, fill=col, width=2)
        d.line([P(0, 0.8), P(1, 0.25)], fill=RED, width=3)
    elif kind == 'hist':
        for i in range(10):
            hh = math.exp(-(i - 4) ** 2 / 5)
            u = 0.08 + i * 0.086
            d.rectangle([P(u, 0.9 - hh * 0.7), P(u + 0.07, 0.9)], fill=AMBER if i >= 8 else col)
    elif kind == 'lineup':
        for i in range(4):
            d.rectangle([P(0.08 + i * 0.23, 0.3), P(0.26 + i * 0.23, 0.85)], outline=AMBER if i == 2 else col, width=2)
        d.line([P(0, 0.2), P(1, 0.2)], fill=col, width=1)

def cards():
    src = Image.open(f'{W}/tex/img18.png').convert('RGBA')
    alpha = src.getchannel('A')
    boxes = [(20, 0, 91, 113), (131, 0, 95, 112), (555, 4, 115, 131), (344, 7, 105, 123), (922, 9, 94, 115), (824, 15, 87, 110), (239, 20, 96, 116), (679, 107, 139, 159), (12, 116, 103, 152), (128, 116, 100, 150), (336, 137, 110, 123), (828, 144, 89, 119), (557, 145, 107, 114), (451, 146, 91, 99), (927, 146, 89, 120), (242, 148, 88, 116)]
    items = [('trend', 'A REAL\nTREND', False, 'prime'), ('season', 'THE\nSEASONS', True, ''), ('noise', 'RANDOM\nNOISE', True, ''), ('spike', 'FREAK\nYEAR', False, ''), ('calendar', 'CHERRY-\nPICKED', True, ''), ('swap', 'INSTRUMENT\nCHANGE', True, ''), ('sat', 'MERRA-2', False, ''), ('chart', 'EXHIBIT A\nSINGAPORE', False, ''), ('sat', 'GRACE-FO', False, ''), ('model', 'GLDAS\nMODEL', False, ''), ('station', 'STATION\nRECORD', False, ''), ('drop', 'RAINFALL\nIMERG', False, ''), ('hist', '23 / 1000', False, ''), ('lineup', 'LINEUP\nNO. 4', False, ''), ('noise', 'CASE 004\nTOO NOISY?', False, ''), ('sat', 'TERRA\n23:47', False, '')]
    out = src.copy()
    for (x, y, w, h), (ic, label, xed, tag) in zip(boxes, items):
        t = Image.new('RGBA', (w, h), PAPER + (255,))
        d = ImageDraw.Draw(t)
        m = 6
        ph = int(h * 0.58)
        dark = (24, 32, 44)
        d.rectangle([m, m, w - m, ph], fill=dark)
        icon(d, ic, (m + 8, m + 8, w - m - 8, ph - 8), (220, 228, 236))
        fs = 15 if w > 100 else 13
        fnt = F('SpecialElite', fs)
        ty = ph + 5
        for line in label.split('\n'):
            tw = d.textlength(line, font=fnt)
            d.text(((w - tw) / 2, ty), line, font=fnt, fill=INK)
            ty += fs + 2
        if tag == 'prime':
            d.ellipse([3, 3, w - 3, h - 3], outline=RED, width=4)
        if xed:
            d.line([8, 8, w - 8, h - 8], fill=RED + (255,), width=9)
            d.line([w - 8, 8, 8, h - 8], fill=RED + (255,), width=9)
        tt = flipv(t)
        if label.startswith('LINEUP'):
            tt = tt.rotate(180)
        out.paste(tt, (x, y))
    MW, MH = (1024, 754)
    M = Image.new('RGBA', (MW, MH), (226, 218, 196, 255))
    d = ImageDraw.Draw(M)
    lon0, lon1, lat0, lat1 = (60, 123, -9, 38)
    px = lambda lo, la: (14 + (lo - lon0) / (lon1 - lon0) * (MW - 28), 10 + (lat1 - la) / (lat1 - lat0) * (MH - 20))
    d.rectangle([14, 10, MW - 14, MH - 10], fill=(200, 210, 206))
    geo = json.load(open('assets/source/asia.json'))
    for g in geo:
        pts = [px(lo, la) for lo, la in g['ring'] if -20 < lo < 180]
        if len(pts) > 2:
            d.polygon(pts, fill=(236, 228, 206), outline=(96, 82, 62))
    for lo in range(60, 124, 10):
        x, _ = px(lo, 0)
        for yy in range(10, MH - 10, 12):
            d.line([x, yy, x, yy + 5], fill=(120, 110, 90), width=1)
        d.text((x + 3, MH - 30), f'{lo}°E', font=F('PlexMono', 13), fill=(90, 80, 60))
    for la in range(-0, 40, 10):
        _, y = px(60, la)
        for xx in range(14, MW - 14, 12):
            d.line([xx, y, xx + 5, y], fill=(120, 110, 90), width=1)
        d.text((20, y - 16), f'{la}°N', font=F('PlexMono', 13), fill=(90, 80, 60))
    reg = [px(73.5, 32.5), px(78, 33), px(80.5, 29.5), px(78, 26.5), px(74, 27.5), px(72.5, 30)]
    pins = {'sg': px(103.8, 1.35), 'in': px(76.5, 29.8), 'my': px(101.7, 4.5)}
    for k, (x, y) in pins.items():
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=RED, outline=(80, 10, 5), width=2)
    lab = F('SpecialElite', 24)

    def tag(xy, text, dx, dy):
        x, y = (xy[0] + dx, xy[1] + dy)
        tw = d.textlength(text, font=lab)
        d.rectangle([x - 6, y - 4, x + tw + 6, y + 30], fill=PAPER, outline=INK, width=2)
        d.text((x, y), text, font=lab, fill=INK)
    tag(pins['sg'], 'CASE 001  SINGAPORE', 18, 6)
    tag(pins['my'], 'CASE 004  SG + MY', -250, -40)
    tag(pins['in'], 'CASE 003  NORTHERN INDIA', 22, -60)
    tb = F('SpecialElite', 30)
    d.rectangle([MW - 380, 26, MW - 30, 128], fill=PAPER, outline=INK, width=3)
    d.text((MW - 362, 36), 'EARTH SYSTEM DESK', font=tb, fill=RED)
    d.text((MW - 362, 76), 'CASE MAP . S + SE ASIA', font=F('SpecialElite', 22), fill=INK)
    d.text((MW - 362, 102), 'NASA EO RECORDS  .  1:20M', font=F('PlexMono', 13), fill=INK)
    for fx in (MW // 3, 2 * MW // 3):
        d.line([fx, 10, fx, MH - 10], fill=(180, 170, 150), width=2)
    d.line([14, MH // 2, MW - 14, MH // 2], fill=(180, 170, 150), width=2)
    a = np.array(M).astype(np.float32)
    rng = np.random.default_rng(4)
    a[:, :, :3] *= 0.94 + 0.06 * rng.random((MH, MW, 1))
    M = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    out.paste(flipv(M), (0, 270))
    out.putalpha(alpha)
    return out

def poster():
    src = Image.open(f'{W}/tex/img30.png').convert('RGB').resize((1024, 1024), Image.LANCZOS)
    logo = Image.open('assets/source/spaceapps_sg.png').convert('RGB')
    bg = logo.getpixel((5, 5))
    P = Image.new('RGB', (736, 1024), (250, 238, 210))
    inner = Image.new('RGB', (680, 968), bg)
    L = logo.crop((150, 150, 874, 874)).resize((680, 680), Image.LANCZOS)
    inner.paste(L, (0, 120))
    d = ImageDraw.Draw(inner)
    f2 = F('PlexMono', 40)
    for i, t in enumerate(['EARTH SYSTEM', 'TREND DETECTIVE']):
        d.text(((680 - d.textlength(t, font=f2)) / 2, 816 + i * 54), t, font=f2, fill=(230, 232, 240))
    P.paste(inner, (28, 28))
    src.paste(flipv(P), (0, 0))
    return src

def mousepad():
    src = Image.open(f'{W}/tex/img03.png').convert('RGB')
    up = flipv(src)
    d = ImageDraw.Draw(up)
    bg = src.getpixel((40, 40))
    d.rectangle([70, 256 - 128, 190, 256 - 84], fill=bg)
    f = F('Oswald', 30)
    t = 'NASA'
    tw = d.textlength(t, font=f)
    d.text(((256 - tw) / 2, 256 - 126), t, font=f, fill=(229, 196, 90))
    return flipv(up)
if __name__ == '__main__':
    import os
    os.makedirs(f'{W}/newtex', exist_ok=True)
    monitor().save(f'{W}/newtex/img20.jpg', quality=92)
    cards().save(f'{W}/newtex/img18.png')
    poster().save(f'{W}/newtex/img30.png')
    mousepad().save(f'{W}/newtex/img03.png')
    for n in ['img20.jpg', 'img18.png', 'img30.png']:
        im = Image.open(f'{W}/newtex/{n}')
        flipv(im.convert('RGB')).save(f"{W}/newtex/preview_{n.split('.')[0]}.png")
    print('done')
