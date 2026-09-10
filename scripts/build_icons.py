"""Build favicon sizes from the supplied, unchanged RANT R glyph.

Maintainer-only: npm ci in sever-ide and the base Python requirements.
The two original wordmark SVG files are never modified.
"""
import copy
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import json
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'sever-ide/public'
source = ET.parse(PUBLIC / 'brand/rant-agent-dark-v1.svg').getroot()
glyph = copy.deepcopy(next(node for node in source.iter() if node.get('id') == 'R_Main'))
values = list(map(float, re.findall(r'-?\d+(?:\.\d+)?', glyph.get('d'))))
left, right = min(values[::2]), max(values[::2])
top, bottom = min(values[1::2]), max(values[1::2])
scale = min(308 / (right - left), 320 / (bottom - top))
x, y = (512 - (right - left) * scale) / 2, (512 - (bottom - top) * scale) / 2
ET.register_namespace('', 'http://www.w3.org/2000/svg')
svg = ET.Element('svg', {'viewBox': '0 0 512 512', 'width': '512', 'height': '512'})
ET.SubElement(svg, 'rect', {'width': '512', 'height': '512', 'rx': '124', 'fill': '#2478FF'})
group = ET.SubElement(svg, 'g', {'transform': f'translate({x} {y}) scale({scale}) translate({-left} {-top})'})
group.append(glyph)
data = ET.tostring(svg, encoding='utf-8', xml_declaration=True)
(PUBLIC / 'favicon.svg').write_bytes(data)
icons = ROOT / 'sever-ide/chrome-extension/icons'
icons.mkdir(exist_ok=True)
targets = [(str(PUBLIC / name), size) for name, size in [('icon-512.png',512),('icon-192.png',192),('apple-touch-icon.png',180)]]
targets += [(str(icons / f'icon-{size}.png'), size) for size in [16,32,48,128]]
script = "import sharp from 'sharp'; for (const [path,size] of JSON.parse(process.argv[1])) await sharp('public/favicon.svg').resize(size,size).png().toFile(path);"
subprocess.run(['node','--input-type=module','-e',script,json.dumps(targets)],cwd=ROOT/'sever-ide',check=True)
with Image.open(PUBLIC / 'icon-512.png') as image:
    image.save(PUBLIC / 'favicon.ico', sizes=[(16,16),(32,32),(48,48)])
print('Built favicon, touch icons and Chrome extension icons from the supplied R glyph.')

# UI wordmarks: keep the supplied paths and remove only the artboard background.
for theme in ('dark', 'white'):
    root = ET.parse(PUBLIC / f'brand/rant-agent-{theme}-v1.svg').getroot()
    for child in list(root):
        if child.get('id') == 'Background':
            root.remove(child)
    (PUBLIC / f'brand/rant-agent-{theme}-transparent.svg').write_bytes(ET.tostring(root, encoding='utf-8', xml_declaration=True))
