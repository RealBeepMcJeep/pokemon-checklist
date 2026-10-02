#!/usr/bin/env python3
"""Build locally signed experimental ordinary Dex QRs; console acceptance unknown."""
from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from typing import Any

from PIL import Image
import qrcode
import zxingcpp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_qr_gallery import GalleryBuildError, PKHEX_COMMIT, _escape, _form_label, _render_card, shared_type_styles
from tools.qr_codec import decode_png, generate_ordinary_payload, verify_ordinary_payload

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'qr-experimental.html'
TEMPLATE_IMAGE_HASH = 'ba45158d80e6b903773b41dc972ca26ad1dfd6320fbd0562670bf5298a45dc14'
TEMPLATE_PAYLOAD_HASH = 'c3c7118b6c99dd2cc424cfcf52282d4d7c2d3689b82350f4e771b4d66e64fa73'
TABLE_HASH = '78a0d3ba8de87a9d36900d88b6f56a62bc48c86d1d555573fbc25160af7484a8'
PROVENANCE = 'locally generated / signature+PNG verified / console untested'


def checked_replace(text: str, old: str, new: str, count: int = 1) -> str:
    if text.count(old) != count:
        raise GalleryBuildError(f'Shared renderer changed: expected {count} instances of {old[:80]!r}')
    return text.replace(old, new)


def load_inputs(root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str], bytes, bytes]:
    root = Path(root)
    catalog = root / 'references/qr-codes'
    manifest = json.loads((catalog / 'manifest.json').read_text())
    metadata = json.loads((catalog / 'gen7-form-types.json').read_text())
    source = metadata['source']
    if source['repository'] != 'kwsch/PKHeX' or source['commit'] != PKHEX_COMMIT or source['tableSha256'] != TABLE_HASH:
        raise GalleryBuildError('Pinned Gen VII metadata provenance changed')
    names = {row['id']: row['name'] for row in json.loads((root / 'data/pokemon.json').read_text())}
    if set(names) != set(range(1, 808)):
        raise GalleryBuildError('Canonical names must cover exactly species 1..807')
    counts, types = metadata['formCounts'], metadata['typesBySpeciesForm']
    if set(counts) != {str(i) for i in range(1, 808)}:
        raise GalleryBuildError('Missing Gen VII form-count species')
    if any(type(n) is not int or not 1 <= n <= 256 for n in counts.values()):
        raise GalleryBuildError('Invalid form count')
    expected = {f'{dex}:{form}' for dex in range(1, 808) for form in range(counts[str(dex)])}
    if set(types) != expected or len(expected) != 1116:
        raise GalleryBuildError('Pinned form/type row coverage changed')
    for values in types.values():
        if not isinstance(values, list) or not 1 <= len(values) <= 2 or any(v not in source['typeValues'] for v in values):
            raise GalleryBuildError('Invalid form type row')
    candidates = [row for row in manifest['records'] if row['source']['title'] == 'File:Caterpie VII QR.png']
    if len(candidates) != 1:
        raise GalleryBuildError('Expected the canonical Caterpie source template')
    row = candidates[0]
    if row['image']['file'] != 'images/304909.png':
        raise GalleryBuildError('Source template path changed')
    image_path = catalog / row['image']['file']
    image = image_path.read_bytes()
    if hashlib.sha256(image).hexdigest() != TEMPLATE_IMAGE_HASH or row['imageSha256'] != TEMPLATE_IMAGE_HASH:
        raise GalleryBuildError('Source template image hash mismatch')
    if len(image) != row['image']['bytes'] or hashlib.sha1(image).hexdigest() != row['source']['sourceSha1']:
        raise GalleryBuildError('Source template original evidence mismatch')
    raw = decode_png(image_path)
    if hashlib.sha256(raw).hexdigest() != TEMPLATE_PAYLOAD_HASH or raw.hex() != row['payload']['rawHex']:
        raise GalleryBuildError('Source template payload mismatch')
    decoded = verify_ordinary_payload(raw)
    if (decoded.species_id, decoded.form, decoded.gender, decoded.shiny_flag, decoded.both_genders_flag, decoded.key_index) != (10, 0, 0, 0, 1, 3):
        raise GalleryBuildError('Source template identity mismatch')
    if decoded.body.hex() != row['payload']['bodyHex']:
        raise GalleryBuildError('Source template decrypted body mismatch')
    labels = {(r['decoded']['species']['id'], r['decoded']['formId']): _form_label(r) for r in manifest['records']}
    records = []
    for dex in range(1, 808):
        for form in range(counts[str(dex)]):
            records.append({'id': dex, 'name': names[dex], 'form_id': form,
                'form_label': labels.get((dex, form), 'Standard' if form == 0 else f'Form {form} (experimental)'),
                'types': types[f'{dex}:{form}'], 'categories': [],
                'source_url': '#generation-provenance', 'source_title': 'Caterpie template / locally generated'})
    atlas = (root / 'assets/gen7-icons.png').read_bytes()
    if not atlas.startswith(b'\x89PNG\r\n\x1a\n'):
        raise GalleryBuildError('Invalid existing sprite atlas')
    return records, source['typeValues'], raw, atlas


def verified_png(raw: bytes, dex: int, form: int) -> bytes:
    code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=8, border=4)
    code.add_data(raw, optimize=0)
    code.make(fit=True)
    buffer = BytesIO()
    code.make_image(fill_color='black', back_color='white').save(buffer, format='PNG')
    png = buffer.getvalue()
    with Image.open(BytesIO(png)) as image:
        symbols = zxingcpp.read_barcodes(image, formats=zxingcpp.BarcodeFormat.QRCode)
    if len(symbols) != 1 or symbols[0].format != zxingcpp.BarcodeFormat.QRCode or bytes(symbols[0].bytes) != raw:
        raise GalleryBuildError(f'PNG raw-byte verification failed for {dex}:{form}')
    decoded = verify_ordinary_payload(bytes(symbols[0].bytes))
    if (decoded.species_id, decoded.form, decoded.gender, decoded.shiny_flag, decoded.both_genders_flag, decoded.key_index) != (dex, form, 0, 0, 0, 3):
        raise GalleryBuildError(f'Signed PNG identity verification failed for {dex}:{form}')
    return png


def render_generated(record: dict[str, Any], raw: bytes) -> str:
    record = {**record, 'source_title': 'Caterpie template · generated payload SHA-256 ' + hashlib.sha256(raw).hexdigest()}
    card = _render_card(record)
    card = checked_replace(card, 'class="qr-card"', f'class="qr-card" id="qr-{record["id"]}-{record["form_id"]}" data-payload-sha256="{hashlib.sha256(raw).hexdigest()}"')
    card = checked_replace(card, 'data-libraries=""', 'data-libraries="generated"')
    card = checked_replace(card, 'data-library-labels=""', f'data-library-labels="{_escape(PROVENANCE)}"')
    card = checked_replace(card, 'alt="Original ', 'alt="Locally generated ')
    card = checked_replace(card, 'Source library membership', 'Generation provenance')
    card = checked_replace(card, '<span class="source-list"></span>', f'<span class="source-list"><span class="source-chip">{_escape(PROVENANCE)}</span></span><span class="dex-form">Base species icon; not form art</span>')
    return card


def test_guide(root: Path) -> str:
    manifest = json.loads((root / 'references/qr-codes/manifest.json').read_text())
    def generated(dex: int, form: int, label: str) -> str:
        target = f'qr-{dex}-{form}'
        return f'<a href="#{target}" data-qr-target="{target}">{_escape(label)}</a>'
    def original(dex: int, label: str) -> str:
        row = next(r for r in manifest['records'] if r['decoded']['species']['id'] == dex and r['decoded']['formId'] == 0)
        return f'<a href="{_escape(row["source"]["originalUrl"])}" target="_blank" rel="noopener noreferrer">{_escape(label)}</a>'
    batch1 = [original(25, 'Original Pikachu control'), generated(25, 0, 'Generated Pikachu #025'),
        generated(1, 0, 'Bulbasaur #001 (non-Alola)'), generated(150, 0, 'Mewtwo #150 (non-Alola)'),
        original(181, 'Original Ampharos'), generated(181, 0, 'Generated Ampharos #181 (Ultra-added)'),
        original(427, 'Original Buneary'), generated(427, 0, 'Generated Buneary #427 (Ultra-added)'),
        generated(803, 0, 'Poipole #803 (Ultra-only)'), generated(807, 0, 'Zeraora #807 (Ultra-only)')]
    batch2 = [generated(dex, form, f'{name} #{dex:03d} form {form}') for dex, name in [(19, 'Rattata'), (479, 'Rotom'), (201, 'Unown')] for form in [0, 1]]
    return ('<section id="test-guide" class="gift-section" aria-labelledby="test-guide-heading">'
        '<h2 id="test-guide-heading">Prioritized physical-console test guide</h2>'
        '<p>All console acceptance is unknown. Repeat separately in stock Sun/Moon and Ultra Sun/Ultra Moon. '
        'Record exact game, region and update version; payload SHA-256 (shown in the generated scan viewer); exact displayed species and form; '
        'intended recognition versus Wonder QR fallback versus rejection; seen-state and points awarded. '
        'Separate camera failures, duplicate scans and exhausted charges from application rejection. '
        'The same pattern cannot repeat until Island Scan resets scanner memory. Do not change the system clock: it resets charges to zero. '
        'Species 803 and 807 probe the SM title-data boundary (802), not a proven scanner threshold.</p>'
        '<p>Scanner budget: at most 10 stored scans, one charge restored every 2 hours; stage batches of no more than 10 '
        'and wait for sufficient charges before the next batch. Do not assume all 10 refill in 2 hours. '
        '<a href="https://bulbapedia.bulbagarden.net/wiki/QR_Scanner" target="_blank" rel="noopener noreferrer">Scanner reference</a>.</p>'
        '<h3>Batch 1 · 10 scans · controls, older species, Ultra boundary</h3><ol>' +
        ''.join(f'<li>{link}</li>' for link in batch1) + '</ol>'
        '<h3>Batch 2 · 6 scans · form comparisons</h3><ol>' + ''.join(f'<li>{link}</li>' for link in batch2) + '</ol>'
        '<p>Original links open preserved source images; generated links open this page’s scan viewer. '
        'The unchanged <a href="qr.html">ordinary archive (244 originals) and separate gift collection (2)</a> remain controls, not generated rewards.</p></section>')


def compile_experimental(root: Path = ROOT) -> str:
    root = Path(root)
    records, type_names, source, atlas = load_inputs(root)
    cards = []
    for record in records:
        raw = generate_ordinary_payload(record['id'], form=record['form_id'], gender=0, shiny=False, both_genders=False, template=source)
        record['image_data'] = 'data:image/png;base64,' + base64.b64encode(verified_png(raw, record['id'], record['form_id'])).decode('ascii')
        cards.append(render_generated(record, raw))
    text = (root / 'tools/qr_gallery_template.html').read_text()
    text = checked_replace(text, 'Generation VII Pokédex QR archive', 'Experimental Gen I–VII Pokédex QR codes', 2)
    text = checked_replace(text, 'Offline source archive · 244 original codes', 'Offline experiment · 807 species · 1116 species/form rows')
    start = '<p class="lede">'
    old = text[text.index(start):text.index('      <div class="filters"')]
    text = checked_replace(text, old, '<p class="lede">One locally generated ordinary key-3 Dex code per pinned Gen VII species/form row: all 807 species and 1116 rows. Not an exhaustive set of gender or shiny combinations. Every PNG is independently decoded and its signed species/form fields verified.</p>\n'
        '<p class="compatibility"><strong>Console untested:</strong> signatures and PNG transport do not establish game acceptance. Includes cosmetic, Mega and battle-only rows; their presence is not a promise the scanner supports them. Ordinary Dex codes do not give Pokémon. All codes set shiny=False, both genders=False and fixed experimental gender=0; this is not a claim of valid species gender metadata.</p>\n')
    text = checked_replace(text, 'Filter and sort ordinary QR archive', 'Filter and sort generated experiments')
    text = checked_replace(text, '<label for="library-filter">Source library membership</label><select id="library-filter"><option value="">All source libraries</option><option value="sun-moon">Sun / Moon category</option><option value="ultra-sun-ultra-moon">Ultra Sun / Ultra Moon category</option></select>', '<label for="library-filter">Template family / provenance</label><select id="library-filter"><option value="generated">Locally generated ordinary key-3 Dex</option></select>')
    text = checked_replace(text, 'Ordinary Pokédex QR archive', 'Generated ordinary Dex experiments')
    gift_start = text.index('    <section id="promotional-gifts"')
    gift_end = text.index('    <footer', gift_start)
    text = checked_replace(text, text[gift_start:gift_end], test_guide(root) + '\n')
    text = checked_replace(text, 'The ordinary scan view preserves each original PNG; gift scans use their verified presentation images. Source links and attribution stay outside the white QR panel.',
        f'<span id="generation-provenance">{_escape(PROVENANCE)}. Source template: File:Caterpie VII QR.png, species #010 form 0, key 3. Original PNG SHA-256 <code>{TEMPLATE_IMAGE_HASH}</code>; raw payload SHA-256 <code>{TEMPLATE_PAYLOAD_HASH}</code>. The existing codec preserves all unknown template bytes; only requested identity/flags and signature change. Neutral default form 0; nonzero rows explicitly experimental. Base species icons are not form art.</span>')
    text = checked_replace(text, 'Original image archive:', 'Source template archive (generated codes are not archive members):')
    text = checked_replace(text, 'Original archive file:', 'Generation/template:')
    text = checked_replace(text, '`Listed in: ${card.dataset.libraryLabels}`', '`Generation: ${card.dataset.libraryLabels}`')
    extension = '''      function openExperimentTarget(target) {
        const card = document.getElementById(target);
        if (!card || !card.matches(".qr-card")) return;
        search.value = "";
        typeFilter.value = "";
        libraryFilter.value = "generated";
        applyFilters();
        openViewer(card);
      }
      document.querySelectorAll("[data-qr-target]").forEach(link => {
        link.addEventListener("click", event => {
          event.preventDefault();
          openExperimentTarget(link.dataset.qrTarget);
        });
      });
      if (/^#qr-\\d+-\\d+$/.test(location.hash)) openExperimentTarget(location.hash.slice(1));
'''
    text = checked_replace(text, '      applySort();\n      applyFilters();', '      applySort();\n      applyFilters();\n' + extension)
    replacements = {'__TYPE_STYLES__': (shared_type_styles(root), 1), '__CARD_COUNT__': (str(len(records)), 2),
        '__TYPE_OPTIONS__': (''.join(f'<option value="{_escape(t)}">{_escape(t)}</option>' for t in type_names), 1),
        '__CARDS__': ('\n'.join(cards), 1), '__ATLAS_DATA_URI__': ('data:image/png;base64,' + base64.b64encode(atlas).decode('ascii'), 1)}
    for marker, (replacement, count) in replacements.items():
        text = checked_replace(text, marker, replacement, count)
    if re.search(r'__[A-Z][A-Z0-9_]+__', text):
        raise GalleryBuildError('Unresolved shared-template markers')
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        data = compile_experimental().encode('utf-8')
        if args.check:
            if not args.output.exists() or args.output.read_bytes() != data:
                print(f'Experimental QR page missing or stale: {args.output}', file=sys.stderr)
                return 1
            print(f'Reproducible: {args.output} ({len(data):,} bytes; 807 species; 1116 verified PNGs)')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(data)
            print(f'Built: {args.output} ({len(data):,} bytes; 807 species; 1116 verified PNGs)')
        return 0
    except (GalleryBuildError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Experimental QR build failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
