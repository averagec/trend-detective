# Desktop TUTORIAL icon: the yellow ? pixel sprite, cut out from its white background
# and scaled to the 64px icon size with nearest-neighbour (keeps the pixel edges).
from PIL import Image
import numpy as np

SRC = 'assets/source/question_sprite.png'
DST = 'public/images/icons/question.png'
S = 64

im = Image.open(SRC).convert('RGBA')
a = np.array(im)
white = a[:, :, :3].min(axis=2) >= 238
a[white, 3] = 0
im = Image.fromarray(a, 'RGBA')
im = im.crop(im.getbbox())
w, h = im.size
k = 56 / max(w, h)
im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.NEAREST)
out = Image.new('RGBA', (S, S), (0, 0, 0, 0))
out.paste(im, ((S - im.size[0]) // 2, (S - im.size[1]) // 2), im)
out.save(DST)
print('wrote', DST, out.size)
