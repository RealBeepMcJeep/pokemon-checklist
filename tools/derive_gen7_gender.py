#!/usr/bin/env python3
"""Derive per-species gender ratios from the pinned PKHeX USUM personal table.

Writes references/qr-codes/gen7-gender-ratios.json. The QR Scanner validates an ordinary
Pokédex code's gender against the species' base (form 0) personal record, so one ratio per
species is enough: 0 male only, 254 female only, 255 genderless, anything else both.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'references/qr-codes/gen7-gender-ratios.json'
COMMIT = '542111fc8584ff29c9d1455553b8acd0e1f8a59a'
TABLE = 'PKHeX.Core/Resources/byte/personal/personal_uu'
TABLE_HASH = '78a0d3ba8de87a9d36900d88b6f56a62bc48c86d1d555573fbc25160af7484a8'
RECORD, GENDER_OFFSET = 0x54, 0x12


def derive(table: bytes) -> dict:
    if hashlib.sha256(table).hexdigest() != TABLE_HASH:
        raise ValueError('personal table SHA-256 does not match the pinned PKHeX table')
    ratios = {str(species): table[species * RECORD + GENDER_OFFSET] for species in range(1, 808)}
    # Forms whose own personal row has a different ratio: the scanner validates against the species
    # row, but the shown Pokémon takes its gender from the form's row (Ash-Greninja is male only).
    form_ratios = {}
    for species in range(1, 808):
        first, count = int.from_bytes(table[species * RECORD + 0x1C:species * RECORD + 0x1E], 'little'), table[species * RECORD + 0x20]
        for form in range(1, count):
            row = species if first <= 0 else first + form - 1
            ratio = table[row * RECORD + GENDER_OFFSET]
            if ratio != ratios[str(species)]:
                form_ratios[f'{species}:{form}'] = ratio
    return {'source': {'repository': 'kwsch/PKHeX', 'commit': COMMIT, 'table': TABLE, 'tableSha256': TABLE_HASH,
                       'recordSize': RECORD, 'genderOffset': GENDER_OFFSET, 'formStatsIndexOffset': 0x1C, 'formCountOffset': 0x20,
                       'attribution': 'Derived Generation VII USUM personal-table gender ratios (species row); PKHeX source by kwsch.'},
            'meaning': {'0': 'male only', '254': 'female only', '255': 'genderless', 'other': 'both genders'},
            'genderRatio': ratios, 'formGenderRatio': form_ratios}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--table', type=Path, help='local copy of the pinned personal_uu (default: download)')
    args = parser.parse_args(argv)
    if args.table:
        table = args.table.read_bytes()
    else:
        url = f'https://raw.githubusercontent.com/kwsch/PKHeX/{COMMIT}/{TABLE}'
        with urllib.request.urlopen(url, timeout=30) as response:
            table = response.read()
    try:
        data = derive(table)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    OUTPUT.write_text(json.dumps(data, indent=2) + '\n')
    print(f'Wrote {OUTPUT.relative_to(ROOT)} (807 species)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
