from PIL import Image
import numpy as np, math
a = np.array(Image.open('assets/source/sprite_native.png')).astype(np.uint8)
H, W, _ = a.shape

def grey(p):
    r, g, b, al = [int(v) for v in p]
    return al > 0 and abs(r - g) < 14 and (abs(g - b) < 14) and (r > 100)
body = a.copy()
for y in range(39, H):
    for x in range(W):
        if int(body[y, x, 0]) >= 70:
            body[y, x] = 0
body[41:] = 0
for y in range(0, 14):
    for x in range(W):
        if grey(body[y, x]) and (not (y == 11 and x in (13, 14))):
            body[y, x] = 0
for y in range(14, 16):
    for x in range(16, W):
        if grey(body[y, x]):
            body[y, x] = 0
portrait_src = body.copy()
body = body[:41]
H = 41
PAD = 8
FW = W + 4
N = 12
tipx, tipy = (15, 11 + PAD)
frames = []
for f in range(N):
    fr = np.zeros((H + PAD, FW, 4), np.uint8)
    b = body.copy()
    if f >= 6:
        b2 = b.copy()
        b2[0:21, :16] = b[1:22, :16]
        b = b2
    fr[PAD:PAD + H, 0:W] = b
    for k in range(7):
        t = (f / N + k / 7) % 1.0
        h = t * 22
        x = tipx + 1 + h * 0.25 + math.sin(h * 0.45 + k) * 1.4
        y = tipy - 1 - h
        alpha = int(235 * (1 - t) ** 1.2)
        if alpha < 40:
            continue
        c = (150 + int(40 * t), 150 + int(40 * t), 158 + int(40 * t), alpha)
        xi, yi = (int(round(x)), int(round(y)))
        for dx, dy in [(0, 0)] if t < 0.35 else [(0, 0), (1, 0)] if t < 0.7 else [(0, 0), (1, 0), (0, -1)]:
            X, Y = (xi + dx, yi + dy)
            if 0 <= X < FW and 0 <= Y < H + PAD and (fr[Y, X, 3] == 0):
                fr[Y, X] = c
    frames.append(fr)
sheet = Image.fromarray(np.concatenate(frames, axis=1), 'RGBA')
sheet.resize((sheet.width * 8, sheet.height * 8), Image.NEAREST).save('src/assets/sprites/detective.png')
p = Image.fromarray(portrait_src[2:20, 4:16], 'RGBA').resize((120, 180), Image.NEAREST)
p.save('public/images/portrait.png')
full = Image.fromarray(portrait_src[1:34, 3:23], 'RGBA')
full.resize((full.width * 7, full.height * 7), Image.NEAREST).save('src/assets/sprites/speaker.png')
print('sprite ok')
