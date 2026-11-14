import struct, json, sys
src, dst = (sys.argv[1], sys.argv[2])
f = open(src, 'rb').read()
L = struct.unpack('<I', f[12:16])[0]
j = json.loads(f[20:20 + L])
o = 20 + L
bl = struct.unpack('<I', f[o:o + 4])[0]
binc = f[o + 8:o + 8 + bl]
repl = {20: ('.cache/newtex/img20.jpg', 'image/jpeg'), 18: ('.cache/newtex/img18.png', 'image/png'), 30: ('.cache/newtex/img30.png', 'image/png'), 3: ('.cache/newtex/img03.png', 'image/png')}
img_bv = {im['bufferView']: i for i, im in enumerate(j['images'])}
out = bytearray()
for bi, bv in enumerate(j['bufferViews']):
    if bi in img_bv and img_bv[bi] in repl:
        p, mt = repl[img_bv[bi]]
        data = open(p, 'rb').read()
        j['images'][img_bv[bi]]['mimeType'] = mt
    else:
        s = bv.get('byteOffset', 0)
        data = binc[s:s + bv['byteLength']]
    while len(out) % 4:
        out.append(0)
    bv['byteOffset'] = len(out)
    bv['byteLength'] = len(data)
    out += data
while len(out) % 4:
    out.append(0)
j['buffers'][0]['byteLength'] = len(out)
j['asset'].setdefault('extras', {})['modified'] = 'Retextured for Trend Detective: monitor, corkboard, poster'
js = json.dumps(j, separators=(',', ':')).encode()
while len(js) % 4:
    js += b' '
total = 12 + 8 + len(js) + 8 + len(out)
g = struct.pack('<III', 1179937895, 2, total) + struct.pack('<II', len(js), 1313821514) + js + struct.pack('<II', len(out), 5130562) + out
open(dst, 'wb').write(g)
print('wrote', dst, len(g))
