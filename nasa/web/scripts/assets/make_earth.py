import numpy as np
from PIL import Image
BAYER = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) + 0.5) / 16
PALETTE = [(6, 9, 18), (14, 26, 64), (31, 79, 160), (59, 125, 221), (127, 214, 232), (236, 230, 214), (108, 191, 90), (60, 110, 60), (166, 140, 96), (217, 74, 54)]

def palette_dither(img, size, palette=PALETTE, amount=40):
    a = np.array(img.convert('RGB').resize(size, Image.LANCZOS)).astype(np.float32)
    h, w, _ = a.shape
    threshold = (np.tile(BAYER, (h // 4 + 1, w // 4 + 1))[:h, :w] - 0.5) * amount
    a = a + threshold[:, :, None]
    p = np.array(palette, np.float32)
    idx = ((a[:, :, None, :] - p[None, None]) ** 2).sum(-1).argmin(-1)
    return Image.fromarray(p[idx].astype(np.uint8), 'RGB')
if __name__ == '__main__':
    earth = Image.open('assets/source/earth.jpg')
    palette_dither(earth, (160, 160), amount=48).resize((480, 480), Image.NEAREST).save('public/images/earth.png')
    print('wrote public/images/earth.png')
