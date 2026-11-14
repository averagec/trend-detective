import math
import numpy as np
from PIL import Image, ImageDraw
N = 32
K = (0, 0, 0, 255)
T = (0, 0, 0, 0)

def C(h, a=255):
    return tuple((int(h[i:i + 2], 16) for i in (1, 3, 5))) + (a,)

def canvas():
    return Image.new('RGBA', (N, N), T)

def outline(im, col=K):
    a = np.array(im)
    al = a[:, :, 3] > 0
    out = a.copy()
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        sh = np.roll(np.roll(al, dy, 0), dx, 1)
        edge = sh & ~al
        out[edge] = col
    return Image.fromarray(out, 'RGBA')

def shadow(im, col=(0, 0, 0, 110)):
    a = np.array(im)
    al = a[:, :, 3] > 0
    sh = np.roll(np.roll(al, 1, 0), 1, 1) & ~al
    out = a.copy()
    out[sh] = col
    return Image.fromarray(out, 'RGBA')

def checker(x, y):
    return (x + y) % 2 == 0

def bevel(im, box, light, dark, ditherdark=None, cols=2):
    x0, y0, x1, y1 = box
    px = im.load()
    for x in range(x0, x1 + 1):
        px[x, y0] = light
        px[x, y1] = dark
    for y in range(y0, y1 + 1):
        px[x0, y] = light
        px[x1, y] = dark
    dd = ditherdark or dark
    for y in range(y0 + 1, y1):
        for x in range(x1 - cols, x1):
            if checker(x, y) and px[x, y][3] and (px[x, y] not in (light,)):
                px[x, y] = dd
    for x in range(x0 + 1, x1):
        if checker(x, y1 - 1) and px[x, y1 - 1] not in (light,):
            px[x, y1 - 1] = dd

def shade(im, strength=1.0):
    a = np.array(im).astype(np.float32)
    al = a[:, :, 3] > 0
    ys, xs = np.nonzero(al)
    if not len(xs):
        return im
    x0, x1, y0, y1 = (xs.min(), xs.max(), ys.min(), ys.max())
    out = a.copy()
    for y, x in zip(ys, xs):
        r, g, b = a[y, x, :3]
        if r + g + b < 60:
            continue
        sc = ((x - x0) / max(1, x1 - x0) + (y - y0) / max(1, y1 - y0)) / 2
        f = 1.0
        if sc > 0.82:
            f = 0.62 if checker(x, y) else 0.74
        elif sc > 0.62 and checker(x, y):
            f = 0.8
        edge = (y == 0 or not al[y - 1, x]) or (x == 0 or not al[y, x - 1])
        if edge and sc < 0.5:
            f = 1.28
        out[y, x, :3] = np.clip(a[y, x, :3] * (1 + (f - 1) * strength), 0, 255)
    return Image.fromarray(out.astype(np.uint8), 'RGBA')

def folder():
    im = canvas()
    d = ImageDraw.Draw(im)
    body, light, dark = (C('#f6df7a'), C('#fff4b8'), C('#c9a63a'))
    d.polygon([(4, 9), (12, 9), (14, 11), (26, 11), (26, 13), (4, 13)], fill=C('#e9c95a'))
    d.rectangle([3, 12, 27, 26], fill=body)
    d.line([(4, 13), (26, 13)], fill=light)
    d.line([(4, 13), (4, 25)], fill=light)
    d.line([(27, 13), (27, 26)], fill=dark)
    d.line([(4, 26), (27, 26)], fill=dark)
    px = im.load()
    for y in range(15, 26):
        for x in range(12, 27):
            if checker(x, y) and x - 12 + (y - 15) * 1.4 > 7 and (px[x, y] == body):
                px[x, y] = C('#f3b58f')
    return shadow(outline(im))

def trash():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.polygon([(6, 10), (24, 10), (22, 28), (8, 28)], fill=C('#c7c7c7'))
    d.polygon([(17, 10), (24, 10), (22, 28), (17, 28)], fill=C('#8e8e8e'))
    d.line([(7, 11), (9, 27)], fill=C('#efefef'))
    d.polygon([(7, 6), (11, 3), (14, 6), (18, 3), (23, 7), (24, 10), (6, 10)], fill=C('#ffffff'))
    d.line([(9, 6), (12, 8)], fill=C('#b5b5b5'))
    d.line([(17, 5), (19, 8)], fill=C('#b5b5b5'))
    g = C('#2f9a3a')
    for t in range(0, 360, 12):
        if t // 40 % 3 == 2:
            continue
        x = 14 + 4 * math.cos(math.radians(t))
        y = 19 + 4 * math.sin(math.radians(t))
        im.putpixel((int(round(x)), int(round(y))), g)
    for p in [(18, 16), (17, 15), (11, 22), (12, 23), (16, 23)]:
        im.putpixel(p, g)
    return shadow(outline(im))

def chart():
    im = canvas()
    d = ImageDraw.Draw(im)
    px = im.load()
    d.line([(4, 3), (4, 28)], fill=C('#e8e8e8'), width=2)
    d.line([(4, 27), (29, 27)], fill=C('#e8e8e8'), width=2)
    for y in (8, 14, 20):
        px[2, y] = C('#e8e8e8')
        px[3, y] = C('#e8e8e8')
    for i, h in enumerate([16, 11, 18, 12]):
        x0 = 8 + i * 5
        y0 = 26 - h
        d.rectangle([x0, y0, x0 + 3, 25], fill=C('#2f6fd0'))
        for y in range(y0, 26):
            px[x0, y] = C('#7fb8ff')
            px[x0 + 3, y] = C('#173c8a')
            if checker(x0 + 2, y):
                px[x0 + 2, y] = C('#1f4fa0')
        d.line([(x0, y0), (x0 + 3, y0)], fill=C('#bfe0ff'))
    d.line([(6, 22), (11, 18), (15, 20), (20, 13), (24, 17), (29, 10)], fill=C('#ff7a2a'), width=2)
    d.line([(6, 21), (11, 17), (15, 19), (20, 12), (24, 16), (29, 9)], fill=C('#ffc08a'), width=1)
    return shadow(outline(im))

def picture():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.polygon([(6, 3), (21, 3), (26, 8), (26, 29), (6, 29)], fill=C('#d8e4fa'))
    d.rectangle([8, 5, 24, 16], fill=C('#c4d6f5'))
    d.polygon([(10, 9), (12, 7), (15, 7), (16, 9), (18, 9), (18, 11), (10, 11)], fill=C('#ffffff'))
    d.polygon([(8, 27), (8, 22), (13, 17), (18, 20), (24, 15), (24, 27)], fill=C('#4cb040'))
    d.line([(8, 22), (13, 17)], fill=C('#8fd67f'))
    d.polygon([(21, 3), (21, 8), (26, 8)], fill=C('#ffffff'))
    d.line([(21, 3), (21, 8), (26, 8)], fill=C('#8a8a8a'))
    d.line([(26, 9), (26, 29)], fill=C('#8fa3c8'))
    d.line([(6, 29), (26, 29)], fill=C('#8fa3c8'))
    d.line([(6, 3), (6, 29)], fill=C('#ffffff'))
    for y in range(10, 29):
        if checker(25, y):
            im.putpixel((25, y), C('#b3c4e6'))
    return shadow(outline(im, C('#6e6e6e')))

def magnifier():
    im = canvas()
    px = im.load()
    cx, cy, r = (13, 12, 9)
    for y in range(N):
        for x in range(N):
            dd = math.hypot(x - cx, y - cy)
            if dd <= r - 2:
                px[x, y] = C('#ffffff')
            elif dd <= r:
                px[x, y] = C('#8a8a8a')
    for a in range(200, 260, 8):
        px[int(cx + 5 * math.cos(math.radians(a))), int(cy + 5 * math.sin(math.radians(a)))] = C('#9cc2ff')
    for y in range(cy, cy + 7):
        for x in range(cx, cx + 7):
            if checker(x, y) and math.hypot(x - cx, y - cy) <= r - 2 and (math.hypot(x - cx, y - cy) > 3):
                px[x, y] = C('#c6dcff')
    d = ImageDraw.Draw(im)
    d.line([(19, 19), (27, 27)], fill=C('#5a5a5a'), width=4)
    d.line([(20, 19), (27, 26)], fill=C('#d0d0d0'), width=1)
    return shadow(outline(im))

def globe():
    im = canvas()
    px = im.load()
    cx, cy, r = (15.5, 15.5, 12)
    blobs = [(-0.5, -0.45, 0.38), (-0.2, 0.35, 0.32), (0.55, -0.2, 0.42), (0.75, 0.45, 0.22), (0.1, -0.05, 0.12)]
    land = lambda u, v: any(((u - a) ** 2 + ((v - b) * 1.3) ** 2 < r * r for a, b, r in blobs))
    for y in range(N):
        for x in range(N):
            dx, dy = ((x - cx) / r, (y - cy) / r)
            if dx * dx + dy * dy > 1:
                continue
            dz = math.sqrt(1 - dx * dx - dy * dy)
            lit = -0.55 * dx - 0.55 * dy + 0.6 * dz
            u, v = (math.atan2(dx, dz), math.asin(dy))
            if land(u, v):
                col = C('#7be35a') if lit > 0.75 else C('#2fae3a') if lit > 0.25 else C('#1b6a24')
            else:
                col = C('#5fd6ff') if lit > 0.75 else C('#2f7dff') if lit > 0.25 else C('#1a3fb0')
            if 0.62 < lit < 0.82 and checker(x, y):
                col = C('#bdf3ff') if not land(u, v) else C('#b9f59c')
            px[x, y] = col
    return shadow(outline(im))

def notepad():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle([7, 5, 25, 28], fill=C('#fff8d8'))
    d.rectangle([7, 5, 25, 8], fill=C('#5b8de0'))
    for x in range(9, 25, 3):
        d.point((x, 4), fill=K)
        d.point((x, 5), fill=C('#cfcfcf'))
    for y in range(11, 27, 3):
        d.line([(9, y), (23, y)], fill=C('#9db6e8'))
    bevel(im, (7, 9, 25, 28), C('#ffffff'), C('#c9bd8a'), C('#efe2a8'))
    for y in range(11, 27, 3):
        d.line([(9, y), (22, y)], fill=C('#9db6e8'))
    return shadow(outline(im))

def idcard():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle([3, 8, 28, 25], fill=C('#e8eef8'))
    d.rectangle([3, 8, 28, 11], fill=C('#1f4fa0'))
    d.rectangle([6, 13, 12, 22], fill=C('#c9d6ee'))
    d.ellipse([7, 14, 11, 17], fill=C('#c08a5a'))
    d.rectangle([7, 18, 11, 22], fill=C('#2a2a2a'))
    for y in (14, 17, 20):
        d.line([(15, y), (25, y)], fill=C('#7a8aa8'))
    bevel(im, (3, 12, 28, 25), C('#ffffff'), C('#9aa6bf'), C('#c9d3e6'))
    d.point((26, 9), fill=C('#ffe600'))
    d.point((25, 9), fill=C('#ffe600'))
    return shadow(outline(im))

def dish():
    im = canvas()
    px = im.load()
    d = ImageDraw.Draw(im)
    d.polygon([(17, 18), (22, 16), (24, 25), (18, 26)], fill=C('#a6a6a6'))
    d.line([(17, 18), (18, 26)], fill=C('#e2e2e2'))
    d.line([(22, 16), (24, 25)], fill=C('#4e4e4e'))
    for y in range(18, 25):
        for x in range(20, 23):
            if checker(x, y) and px[x, y][3]:
                px[x, y] = C('#7c7c7c')
    d.rectangle([11, 26, 28, 28], fill=C('#b6b6b6'))
    d.line([(11, 26), (28, 26)], fill=C('#f0f0f0'))
    d.line([(12, 28), (28, 28)], fill=C('#5a5a5a'))
    for x in range(20, 28):
        if checker(x, 27):
            px[x, 27] = C('#8e8e8e')
    cx, cy, rx, ry, ang = (18.0, 12.0, 12.2, 6.6, math.radians(-42))
    ca, sa = (math.cos(ang), math.sin(ang))
    for y in range(N):
        for x in range(N):
            u = (x + 0.5 - cx) * ca + (y + 0.5 - cy) * sa
            v = -(x + 0.5 - cx) * sa + (y + 0.5 - cy) * ca
            q = (u / rx) ** 2 + (v / ry) ** 2
            if q > 1:
                continue
            if q > 0.8:
                col = C('#ffffff') if v < 0.6 else C('#5e5e5e')
            elif v < -2.2:
                col = C('#d6d6d6')
            elif v < 0.4:
                col = C('#b4b4b4') if not checker(x, y) else C('#c6c6c6')
            elif v < 2.6:
                col = C('#969696') if checker(x, y) else C('#a8a8a8')
            else:
                col = C('#7a7a7a')
            px[x, y] = col
    d.rectangle([17, 11, 18, 12], fill=C('#4a4a4a'))
    d.line([(17, 11), (10, 5)], fill=K)
    d.line([(18, 11), (11, 5)], fill=C('#3a3a3a'))
    d.rectangle([8, 3, 10, 5], fill=C('#9a9a9a'))
    px[8, 3] = C('#ffffff')
    px[10, 5] = C('#4a4a4a')
    im = shadow(outline(im)).copy()
    px = im.load()
    for x, y in [(6, 2), (5, 3), (5, 4), (5, 5), (6, 6), (3, 0), (2, 1), (2, 2), (1, 3), (1, 4), (1, 5), (2, 6), (2, 7), (3, 8)]:
        px[x, y] = C('#ff2a2a')
    return im

def lock():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle([7, 14, 24, 27], fill=C('#e9b43a'))
    bevel(im, (7, 14, 24, 27), C('#ffe08a'), C('#9a6a12'), C('#c8902a'), cols=3)
    d.arc([10, 5, 21, 20], 180, 360, fill=C('#9a9a9a'), width=3)
    d.rectangle([15, 18, 16, 23], fill=K)
    return shadow(outline(im))

def disk():
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle([4, 4, 27, 27], fill=C('#2b4fa8'))
    d.rectangle([9, 4, 22, 12], fill=C('#c9c9c9'))
    d.rectangle([17, 6, 20, 10], fill=C('#2b4fa8'))
    d.rectangle([7, 16, 24, 27], fill=C('#f4f4f4'))
    for y in (19, 22, 25):
        d.line([(9, y), (22, y)], fill=C('#9db6e8'))
    bevel(im, (4, 4, 27, 27), C('#6f95e8'), C('#16306e'), C('#213f8a'))
    bevel(im, (7, 16, 24, 26), C('#ffffff'), C('#a9b4c8'), C('#d9dee8'), cols=1)
    for y in (19, 22):
        d.line([(9, y), (21, y)], fill=C('#9db6e8'))
    return shadow(outline(im))

def dish_from_source():
    src = Image.open('assets/source/dish_native.png').convert('RGBA')
    c = canvas()
    c.alpha_composite(src, ((N - src.width) // 2, (N - src.height) // 2))
    return c
ICONS = {'folder': folder, 'trash': trash, 'chart': chart, 'picture': picture, 'mag': magnifier, 'globe': globe, 'doc': notepad, 'id': idcard, 'dish': dish_from_source, 'lock': lock, 'disk': disk}
if __name__ == '__main__':
    for k, f in ICONS.items():
        f().resize((64, 64), Image.NEAREST).save(f'public/images/icons/{k}.png')
    print('icons ok')
