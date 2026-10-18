"""Insertion-only layout A: full Gen VII effects and access, without losing card pixels."""
from functools import lru_cache
from PIL import Image, ImageChops, ImageDraw
import story_team_cards as art


def compose(original, rows, equipment):
    if original.size != art.SIZE or len(rows) != 6 or len(equipment.get('members', [])) != 6:
        raise ValueError('combined equipment needs one full six-member source card')
    face = lru_cache(maxsize=20)(art.font)
    probe = ImageDraw.Draw(Image.new('RGB', (1260, 1)))
    def text(value, size, maximum, bold=False):
        if not isinstance(value, str) or not value.strip():
            raise ValueError('missing essential item name/effect/access text')
        return art.wrapped_lines(probe, value, face(size, bold), 545, maximum)
    layouts = []
    used = set()
    for index, member in enumerate(rows):
        identity = (member['owned'], member['final'], member['dex'])
        matches = [entry for entry in equipment['members'] if (entry['owned'], entry['final'], entry['dex']) == identity]
        if len(matches) != 1 or identity in used:
            raise ValueError('equipment member identity mismatch or duplicate')
        entry = matches[0]; used.add(identity)
        if entry.get('moves') != member.get('moves') or (index and entry.get('evolution') != member.get('evolution')):
            raise ValueError('equipment path/move targets mismatch')
        choices = []
        for stage in ['current', 'later']:
            choice = entry['story'][stage]
            blocks = [('EASY ACCESS / IF COLLECTED' if stage == 'current' else 'LATER STORY UPGRADE', 16, True, 1),
                      (choice['item'].get('name'), 25, True, 2),
                      (choice['item'].get('effect'), 18, False, 4),
                      (choice['access'].get('location'), 17, False, 3)]
            tag = ('Stock USUM fallback / Standard access unverified' if choice['access'].get('status') == 'stock-USUM-fallback'
                   else 'Conditional access / inventory unconfirmed')
            blocks.append((tag, 14, False, 1))
            prepared = []; y = 12
            for value, size, bold, maximum in blocks:
                lines = text(value, size, maximum, bold)
                prepared.append({'text': value, 'lines': lines, 'size': size, 'bold': bold, 'top': y})
                y += len(lines) * (size + 4) + 5
            choices.append({'stage': stage, 'blocks': prepared, 'height': y + 5})
        layouts.append({'owned': member['owned'], 'final': member['final'], 'dex': member['dex'], 'choices': choices})
    band = max(choice['height'] for row in layouts for choice in row['choices']) + 8
    horizon = equipment.get('horizon', 'Report horizon not recorded; item ownership unknown.')
    horizon_lines = art.wrapped_lines(probe, horizon, face(16), 1160, 3)
    header, footer = 84, 56 + 24 * len(horizon_lines)
    canvas = Image.new('RGB', (1260, original.height + header + 6 * band + footer), art.BG)
    draw = ImageDraw.Draw(canvas)
    draw.text((48, 8), 'TEAM EQUIPMENT / WHAT IT DOES', font=face(27, True), fill='#c19ce8')
    draw.text((48, 47), 'Easy-access option if collected + later story upgrade. Original card details retained.', font=face(18), fill=art.DIM)
    previous = 0; slices = []
    for index, row in enumerate(layouts):
        cut = art.ROW_TOP + index * art.ROW_STEP + art.ROW_HEIGHT + 4
        destination = previous + header + index * band
        canvas.paste(original.crop((0, previous, original.width, cut)), (0, destination))
        slices.append([previous, cut, destination])
        y = cut + header + index * band
        for choice in row['choices']:
            current = choice['stage'] == 'current'
            x, right = (50, 621) if current else (633, 1210)
            draw.rounded_rectangle((x, y + 4, right, y + band - 4), radius=10,
                fill='#152e39' if current else '#332d34', outline='#427e89' if current else '#927151', width=2)
            for block in choice['blocks']:
                top = y + block['top']
                color = art.WHITE if block['bold'] else art.DIM
                for line in block['lines']:
                    draw.text((x + 13, top), line, font=face(block['size'], block['bold']), fill=color)
                    top += block['size'] + 4
                if top > y + band - 4: raise ValueError('equipment block overlaps its boundary')
        previous = cut
    destination = previous + header + 6 * band
    canvas.paste(original.crop((0, previous, original.width, original.height)), (0, destination))
    slices.append([previous, original.height, destination])
    y = original.height + header + 6 * band
    notes = [*horizon_lines,
             'Berries are consumed. Only one free school Wise Glasses per alternative party; later vendor prices unverified.',
             'Gen VII effects from verified item data; choices are conditional story advice, not a global optimal-build claim.']
    for index, line in enumerate(notes):
        art.fit(draw, line, face(16), 1160, strict=True)
        draw.text((50, y + 6 + 24 * index), line, font=face(16), fill=art.DIM)
    recovered = Image.new('RGB', original.size)
    for top, bottom, destination in slices:
        recovered.paste(canvas.crop((0, destination, original.width, destination + bottom - top)), (0, top))
    if ImageChops.difference(recovered, original).getbbox() is not None:
        raise ValueError('combined equipment changed original pixels')
    return canvas, {'original_pixels_preserved': True, 'preserved_slices': slices, 'size': list(canvas.size), 'rows': layouts}
