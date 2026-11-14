import struct, json, os
f = open('assets/source/office_original.glb', 'rb').read()
L = struct.unpack('<I', f[12:16])[0]
j = json.loads(f[20:20 + L])
o = 20 + L
bl = struct.unpack('<I', f[o:o + 4])[0]
b = f[o + 8:o + 8 + bl]
os.makedirs('.cache/tex', exist_ok=True)
for i, im in enumerate(j['images']):
    bv = j['bufferViews'][im['bufferView']]
    s = bv.get('byteOffset', 0)
    open(f".cache/tex/img{i:02d}.{('jpg' if 'jpeg' in im['mimeType'] else 'png')}", 'wb').write(b[s:s + bv['byteLength']])
print('extracted', len(j['images']))
