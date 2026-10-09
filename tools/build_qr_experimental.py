#!/usr/bin/env python3
"""Build the generated Pokédex QR page: every species/form the Gen VII QR Scanner accepts.

Each card carries precomputed, signed payloads for its gender and shiny variants; the page draws
the QR code in the browser (vendored qrcode-generator). Every payload is verified here: signature,
identity fields, unchanged template bytes, and the scanner's acceptance rule below.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.build_qr_gallery import GalleryBuildError, PKHEX_COMMIT, _escape, shared_type_styles
from tools.qr_codec import decode_png, generate_ordinary_payload, verify_ordinary_payload

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'qr-experimental.html'
TEMPLATE = ROOT / 'tools/qr_experimental_template.html'
QR_LIBRARY = ROOT / 'tools/vendor/qrcode-generator-2.0.4.js'
QR_LIBRARY_HASH = '79ec86f82856005b1c887905cfccfcfbec3821ca61c7fd5a952faa5f778f791c'
TEMPLATE_IMAGE_HASH = 'ba45158d80e6b903773b41dc972ca26ad1dfd6320fbd0562670bf5298a45dc14'
TEMPLATE_PAYLOAD_HASH = 'c3c7118b6c99dd2cc424cfcf52282d4d7c2d3689b82350f4e771b4d66e64fa73'
TABLE_HASH = '78a0d3ba8de87a9d36900d88b6f56a62bc48c86d1d555573fbc25160af7484a8'

# Scanner rules, reverse-engineered from Ultra Moon v1.2's QR Scanner
# (NetApp::QR::QRUtility::AnalyzeQRBinaryForApp) and checked by running its own code.
SCANNER_EXCLUDED = range(785, 808)  # in-code exclusion table: always a Wonder QR
PIKACHU = 25                        # form reset to 0 after validation
GENDER_CODE = {'m': 0, 'f': 1, 'u': 2}
GENDER_WORD = {'m': 'male', 'f': 'female', 'u': 'genderless'}
# Species/forms whose acceptance was seen on a real Ultra Moon (Prismatic Moon Standard), 2026-10.
CONSOLE_TESTED = {(1, 0), (3, 1), (25, 0), (130, 0), (150, 0), (151, 0), (592, 0), (658, 2), (666, 19), (745, 2), (772, 0)}
# Friendlier display names for PKHeX's Gen 7 form strings; the raw strings stay searchable.
FORM_NAMES = {'': 'Standard', 'Normal': 'Standard', 'Large': 'Totem', '*Busted': 'Totem (Busted)', 'Alola': 'Alolan'}
SPECIES_FORM_NAMES = {658: {'Ash': 'Battle Bond', 'Active': 'Ash-Greninja'}, 678: {'M': 'Male', 'F': 'Female'},
                      718: {'10%-C': '10% (Power Construct)', '50%-C': '50% (Power Construct)'},
                      800: {'Dusk': 'Dusk Mane', 'Dawn': 'Dawn Wings'}, 801: {'Original': 'Original Color'}}
TESTED_LABEL = 'Tested on 3DS'
PROVENANCE = 'Generated from the official Caterpie code (key 3); signature, identity fields and scanner rule verified at build time.'


def friendly_form(species: int, form: int, raw: str) -> str:
    if species == PIKACHU and form:
        return f'{raw} Cap'
    if species == 774:  # Minior: M-<color> meteor shells, C-<color> cores
        return 'Meteor' if raw.startswith('M-') and form == 0 else f'Meteor ({raw[2:]})' if raw.startswith('M-') else f'{raw[2:]} Core'
    return SPECIES_FORM_NAMES.get(species, {}).get(raw) or FORM_NAMES.get(raw, raw)


def gender_options(ratio: int) -> list[str]:
    """Gender variants the scanner accepts, from the species' base personal gender ratio."""
    return {0: ['m'], 254: ['f'], 255: ['u']}.get(ratio, ['m', 'f'])


def card_genders(record: dict[str, Any]) -> list[str]:
    """Variants worth offering: accepted for the species, and shown as that gender for this form."""
    options = gender_options(record['gender_ratio'])
    shown = gender_options(record.get('form_gender_ratio', record['gender_ratio']))
    return [g for g in options if g in shown] or options


def registration_masks(gender: str, shiny: bool, form: int) -> tuple[int, int, int, int]:
    """One Pokédex registration lane: normal ♂/genderless, normal ♀, shiny ♂/genderless, shiny ♀."""
    masks = [0, 0, 0, 0]
    masks[(1 if gender == 'f' else 0) + (2 if shiny else 0)] = 1 << form
    return masks[0], masks[1], masks[2], masks[3]


def scanner_outcome(species: int, form: int, gender: int, shiny: int, both: int,
                    masks: tuple[int, int, int, int], form_count: int, ratio: int) -> str:
    """'accepted', 'base-form' (shown as form 0) or 'wonder' for an ordinary key-3 record."""
    if not 1 <= species <= 807 or species in SCANNER_EXCLUDED or form >= form_count:
        return 'wonder'
    if (masks[0] | masks[1] | masks[2] | masks[3]).bit_length() > form_count:
        return 'wonder'
    lanes = {0: (0, 1, 3), 254: (1, 0, 2), 255: (2, 1, 3)}.get(ratio)
    if lanes:
        required, a, b = lanes
        if gender != required or (masks[a] + masks[b]) % (1 << 32) or both == 1:
            return 'wonder'
    elif gender not in (0, 1):
        return 'wonder'
    if shiny not in (0, 1) or both not in (0, 1):
        return 'wonder'
    return 'base-form' if species == PIKACHU and form else 'accepted'


def load_inputs(root: Path = ROOT) -> tuple[list[dict[str, Any]], list[str], bytes, bytes]:
    root = Path(root)
    catalog = root / 'references/qr-codes'
    manifest = json.loads((catalog / 'manifest.json').read_text())
    metadata = json.loads((catalog / 'gen7-form-types.json').read_text())
    genders = json.loads((catalog / 'gen7-gender-ratios.json').read_text())
    form_names = json.loads((catalog / 'gen7-form-names.json').read_text())
    if form_names['source']['repository'] != 'kwsch/PKHeX' or form_names['source']['commit'] != PKHEX_COMMIT:
        raise GalleryBuildError('Pinned form-name provenance changed')
    source = metadata['source']
    if source['repository'] != 'kwsch/PKHeX' or source['commit'] != PKHEX_COMMIT or source['tableSha256'] != TABLE_HASH:
        raise GalleryBuildError('Pinned Gen VII metadata provenance changed')
    gsource = genders['source']
    if gsource['repository'] != 'kwsch/PKHeX' or gsource['commit'] != PKHEX_COMMIT or gsource['tableSha256'] != TABLE_HASH:
        raise GalleryBuildError('Pinned gender-ratio provenance changed')
    ratios, form_ratios = genders['genderRatio'], genders.get('formGenderRatio', {})
    if set(ratios) != {str(i) for i in range(1, 808)} or any(type(v) is not int or not 0 <= v <= 255 for v in ratios.values()):
        raise GalleryBuildError('Gender ratios must cover species 1..807 with byte values')
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
    raw_names = form_names['formNames']
    if set(raw_names) != set(counts) or any(len(raw_names[k]) != counts[k] for k in counts):
        raise GalleryBuildError('Form names must cover every pinned form row')
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
    records = []
    for dex in range(1, 808):
        for form in range(counts[str(dex)]):
            records.append({'id': dex, 'name': names[dex], 'form_id': form, 'form_count': counts[str(dex)],
                'form_label': friendly_form(dex, form, raw_names[str(dex)][form]), 'form_raw': raw_names[str(dex)][form],
                'types': types[f'{dex}:{form}'], 'gender_ratio': ratios[str(dex)],
                'form_gender_ratio': form_ratios.get(f'{dex}:{form}', ratios[str(dex)])})
    atlas = (root / 'assets/gen7-icons.png').read_bytes()
    if not atlas.startswith(b'\x89PNG\r\n\x1a\n'):
        raise GalleryBuildError('Invalid existing sprite atlas')
    return records, source['typeValues'], raw, atlas


def load_qr_library(root: Path = ROOT) -> str:
    data = (Path(root) / 'tools/vendor/qrcode-generator-2.0.4.js').read_bytes()
    if hashlib.sha256(data).hexdigest() != QR_LIBRARY_HASH:
        raise GalleryBuildError('Vendored qrcode-generator changed')
    text = data.decode('utf-8')
    if '</script' in text.lower():
        raise GalleryBuildError('Vendored library cannot be inlined safely')
    return text


def signed_variant(record: dict[str, Any], gender: str, shiny: bool, template: bytes) -> bytes:
    """Sign one variant and verify it: identity, unchanged template bytes, and the scanner rule."""
    dex, form = record['id'], record['form_id']
    masks = registration_masks(gender, shiny, form)
    raw = generate_ordinary_payload(dex, form=form, gender=GENDER_CODE[gender], shiny=shiny, both_genders=False,
                                    masks=masks, template=template)
    decoded = verify_ordinary_payload(raw)
    source = verify_ordinary_payload(template).body
    if (decoded.species_id, decoded.form, decoded.gender, decoded.shiny_flag, decoded.both_genders_flag, decoded.key_index) != (dex, form, GENDER_CODE[gender], int(shiny), 0, 3):
        raise GalleryBuildError(f'Signed identity verification failed for {dex}:{form} {gender}{"s" if shiny else ""}')
    if decoded.body[0x08:0x18] != b''.join(m.to_bytes(4, 'little') for m in masks):
        raise GalleryBuildError(f'Registration masks not written for {dex}:{form}')
    if decoded.body[:0x08] != source[:0x08] or decoded.body[0x18:0x28] != source[0x18:0x28] or decoded.body[0x2e:-8] != source[0x2e:-8]:
        raise GalleryBuildError(f'Unknown template bytes changed for {dex}:{form}')
    outcome = scanner_outcome(dex, form, decoded.gender, decoded.shiny_flag, decoded.both_genders_flag, masks,
                              record['form_count'], record['gender_ratio'])
    if outcome != 'accepted':
        raise GalleryBuildError(f'Scanner rule rejects {dex}:{form} {gender}: {outcome}')
    return raw


def blocked_reason(record: dict[str, Any]) -> str | None:
    """Why no code can register this species/form, or None if it is scannable."""
    gender = gender_options(record['gender_ratio'])[0]
    masks = registration_masks(gender, False, record['form_id'])
    outcome = scanner_outcome(record['id'], record['form_id'], GENDER_CODE[gender], 0, 0, masks,
                              record['form_count'], record['gender_ratio'])
    if outcome == 'accepted':
        return None
    if outcome == 'base-form':
        return 'Scans as plain Pikachu'
    return 'The scanner swaps it for a random Pokémon'


def dex_line(dex: int, label: str, prefix: str = 'National Pokédex ') -> str:
    return f'{prefix}#{dex:03d}' + ('' if label == 'Standard' else f' · {label}')


def search_terms(record: dict[str, Any]) -> str:
    dex = record['id']
    return ' '.join(dict.fromkeys((record['name'], str(dex), f'{dex:03d}', f'#{dex:03d}', record['form_label'], record['form_raw'])))


def render_card(record: dict[str, Any], template: bytes) -> str:
    dex, form, name, label = record['id'], record['form_id'], record['name'], record['form_label']
    genders = card_genders(record)
    payloads = {}
    for gender in genders:
        for shiny in (False, True):
            payloads[gender + ('s' if shiny else '')] = base64.b64encode(signed_variant(record, gender, shiny, template)).decode('ascii')
    data_qr = ''.join(f' data-qr-{key}="{value}"' for key, value in payloads.items())
    types = record['types']
    type_tags = ''.join(f'<span class="type-chip type-mark type-{_escape(t.lower())}" title="{_escape(t)} type" aria-hidden="true">{_escape(t)}</span>' for t in types)
    tested = ('<span class="tested" title="Scanned successfully on a real Ultra Moon"><svg class="icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M6.2 11.6 2.6 8l-1.4 1.4 5 5L15 5.6l-1.4-1.4Z"/></svg>' + TESTED_LABEL + '</span>'
              if (dex, form) in CONSOLE_TESTED else '')
    if len(genders) == 2:
        gender_control = (f'<button class="switch gender-switch" type="button" data-on="false" aria-label="Male. Switch to female" aria-describedby="name-{dex}-{form}" data-card-action="gender">'
                          '<span class="switch-track" aria-hidden="true"><span class="switch-knob">♂</span></span><span class="switch-label">Male</span></button>')
    else:
        symbol, css, text, short = {'m': ('♂', 'male', 'Male only', 'only'), 'f': ('♀', 'female', 'Female only', 'only'),
                                    'u': ('–', 'none', 'Genderless', '')}[genders[0]]
        gender_control = (f'<span class="gender-fixed" title="{text}"><span class="symbol {css}" aria-hidden="true">{symbol}</span>'
                          f'<span class="fixed-label"><span class="long">{text}</span><span class="short" aria-hidden="true">{short}</span></span></span>')
    shiny_control = (f'<button class="switch shiny-switch" type="button" role="switch" aria-checked="false" aria-label="Shiny" aria-describedby="name-{dex}-{form}" data-card-action="shiny">'
                     '<span class="switch-label">Shiny</span><span class="switch-track" aria-hidden="true"><span class="switch-knob"><svg class="icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 0.8 9.7 6.3 15.2 8 9.7 9.7 8 15.2 6.3 9.7 0.8 8 6.3 6.3Z"/></svg></span></span></button>')
    return (
        f'<article class="qr-card" id="qr-{dex}-{form}" data-dex="{dex}" data-name="{_escape(name)}" data-form="{form}" '
        f'data-form-label="{_escape(label)}" data-types="{_escape(" ".join(types))}" data-search="{_escape(search_terms(record))}" '
        f'data-genders="{"".join(genders)}" data-gender="{genders[0]}" data-shiny="0"{' data-tested="1"' if (dex, form) in CONSOLE_TESTED else ''}{data_qr}>'
        f'<button class="card-open" type="button" aria-label="Open scan view for #{dex:03d} {_escape(name)}' + ('' if label == 'Standard' else f', {_escape(label)}') + '">'
        f'<span class="qr-frame"><img class="qr-original" alt="" draggable="false"></span>'
        f'<span class="card-meta"><span class="identity"><span class="sprite-crop" aria-hidden="true"><img class="sprite-atlas" data-dex="{dex}" alt=""></span>'
        f'<span class="names"><strong class="species-name" id="name-{dex}-{form}">{_escape(name)}</strong>'
        f'<span class="dex-form">{_escape(dex_line(dex, label))}</span></span></span>'
        f'<span class="type-list type-marks type-labels" aria-label="Types: {_escape(" and ".join(types))}">{type_tags}{tested}</span></span></button>'
        f'<div class="card-controls">{gender_control}{shiny_control}</div></article>'
    )


def render_blocked(records: list[dict[str, Any]], reason: str) -> str:
    first = records[0]
    dex, name = first['id'], first['name']
    label = first['form_label'] if len(records) == 1 else f'{len(records)} Cap forms'
    forms = ' '.join(str(r['form_id']) for r in records)
    terms = ' '.join(dict.fromkeys(term for r in records for term in search_terms(r).split()))
    return (f'<li class="blocked-row" id="qr-{dex}-{first["form_id"]}" data-dex="{dex}" data-name="{_escape(name)}" data-form="{first["form_id"]}" '
            f'data-forms="{forms}" data-types="{_escape(" ".join(first["types"]))}" data-search="{_escape(terms)}">'
            f'<span class="sprite-crop" aria-hidden="true"><img class="sprite-atlas" data-dex="{dex}" alt=""></span>'
            f'<span class="names"><strong class="species-name">{_escape(name)}</strong>'
            f'<span class="dex-form">{_escape(dex_line(dex, label, ""))}</span>'
            f'<span class="blocked-reason">{_escape(reason)}</span></span></li>')


def compile_experimental(root: Path = ROOT) -> str:
    root = Path(root)
    records, type_names, template, atlas = load_inputs(root)
    cards, blocked, caps = [], [], []
    for record in records:
        reason = blocked_reason(record)
        if reason and record['id'] == PIKACHU:
            caps.append(record)
            if len(caps) == 1:
                blocked.append(None)  # placeholder keeps dex order
        elif reason:
            blocked.append(render_blocked([record], reason))
        else:
            cards.append(render_card(record, template))
    blocked = [render_blocked(caps, blocked_reason(caps[0]) or '') if row is None else row for row in blocked]
    species = len({r['id'] for r in records if not blocked_reason(r)})
    intro = (
        '<p class="lede">A working QR code for every Pokémon and form the Gen VII QR Scanner accepts. '
        'Pick a Pokémon, flip ♂/♀ and Shiny, then tap the code to show it big for your 3DS camera.</p>\n'
        '      <details id="how-it-works" class="compatibility"><summary>How these codes work</summary><ul>'
        '<li>Scanning registers the Pokémon as <em>seen</em> in the Pokédex; it doesn’t give you the Pokémon. Each gender and shiny version registers separately, so scan each one you want.</li>'
        '<li>The scanner holds 10 scans and recharges one every 2 hours, and won’t accept the same code twice until your next Island Scan.</li>'
        '<li>Pokémon #785–807 and Pikachu’s Cap forms can’t be added with any QR code: <a href="#not-scannable">see the list at the bottom</a>.</li>'
        f'<li>The rules come from reverse-engineering the Ultra Moon v1.2 QR Scanner and running its own code. Cards marked “{TESTED_LABEL}” were also tried on a real Ultra Moon; Sun, Moon and Ultra Sun are untested.</li>'
        '</ul></details>\n'
        '      <script>if (!matchMedia("(max-width: 700px)").matches) document.getElementById("how-it-works").open = true;</script>')
    blocked_intro = ('<p>No QR code can register these. The scanner swaps species #785–807 for a random Wonder QR Pokémon, and always resets Pikachu to its normal form. '
                     'They aren’t in the Wonder QR table either.</p>')
    credits = (
        '<p>QR codes are drawn in your browser from payloads signed and verified when the page is built.</p><ul>'
        '<li>Pages: <a href="index.html">Checklist</a> · <a href="qr.html">Original QR archive and event gifts</a> · <a href="qr-experimental.html">Generated codes</a>.</li>'
        f'<li id="generation-provenance">Template: the official Caterpie code (File:Caterpie VII QR.png, key 3), original PNG SHA-256 <code>{TEMPLATE_IMAGE_HASH}</code>, raw payload SHA-256 <code>{TEMPLATE_PAYLOAD_HASH}</code>. Only the species, form, gender, shiny flag, registration lanes and signature change.</li>'
        f'<li>Types, form rows and gender ratios: <a href="https://github.com/kwsch/PKHeX/tree/{PKHEX_COMMIT}" target="_blank" rel="noopener noreferrer">PKHeX</a>, pinned commit <code>{PKHEX_COMMIT}</code>, personal table SHA-256 <code>{TABLE_HASH}</code>.</li>'
        '<li>Sprite atlas: <a href="https://github.com/PokeAPI/sprites/tree/6e3e7c43e86db0e1b2277795cfee41b11e8df2a4" target="_blank" rel="noopener noreferrer">PokeAPI/sprites</a>, pinned commit <code>6e3e7c43e86db0e1b2277795cfee41b11e8df2a4</code>; base species icons, not form art.</li>'
        '<li>QR drawing: <a href="https://github.com/kazuhikoarase/qrcode-generator" target="_blank" rel="noopener noreferrer">qrcode-generator</a> 2.0.4 by Kazuhiko Arase, MIT license.</li>'
        '<li>Protocol background: <a href="https://gbatemp.net/threads/pokemon-sun-and-moon-hacking-qr-codes.448369/" target="_blank" rel="noopener noreferrer">published Gen VII QR reverse-engineering discussion</a>.</li>'
        '</ul>')
    replacements = {
        '__TYPE_STYLES__': (shared_type_styles(root), 1),
        '__EYEBROW__': (f'Generated Pokédex codes · {species} species · {len(cards)} cards', 1),
        '__INTRO__': (intro, 1), '__CARD_COUNT__': (str(len(cards)), 2),
        '__TYPE_OPTIONS__': (''.join(f'<option value="{_escape(t)}">{_escape(t)}</option>' for t in type_names), 1),
        '__CARDS__': ('\n'.join(cards), 1), '__BLOCKED_COUNT__': (str(len(blocked)), 1),
        '__BLOCKED_INTRO__': (blocked_intro, 1), '__BLOCKED__': ('\n'.join(blocked), 1), '__CREDITS__': (credits, 1),
        '__PROVENANCE__': (_escape(PROVENANCE), 1), '__QR_LIBRARY__': (load_qr_library(root), 1),
        '__ATLAS_DATA_URI__': ('data:image/png;base64,' + base64.b64encode(atlas).decode('ascii'), 1)}
    text = (root / 'tools/qr_experimental_template.html').read_text()
    for marker, (replacement, count) in replacements.items():
        if text.count(marker) != count:
            raise GalleryBuildError(f'Template marker {marker} expected {count} times')
        text = text.replace(marker, replacement)
    if re.search(r'__[A-Z][A-Z0-9_]+__', text.replace(load_qr_library(root), '')):
        raise GalleryBuildError('Unresolved template markers')
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
            print(f'Reproducible: {args.output} ({len(data):,} bytes)')
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(data)
            print(f'Built: {args.output} ({len(data):,} bytes)')
        return 0
    except (GalleryBuildError, OSError, ValueError, KeyError, TypeError) as error:
        print(f'Experimental QR build failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
