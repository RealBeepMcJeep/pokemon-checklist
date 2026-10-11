"""Deterministically extract stock Gen VII capture fields from pinned PKHeX resources."""
import argparse, hashlib, json, struct
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
COMMIT = '542111fc8584ff29c9d1455553b8acd0e1f8a59a'
HASHES = {'personal_uu':'78a0d3ba8de87a9d36900d88b6f56a62bc48c86d1d555573fbc25160af7484a8', 'personal_sm':'954c322b1d38b9d3feb9d39a4cbf212aa77d4a9ba32df349abd7b9f24ef058ec', 'PersonalInfo7.cs':'b58a126d806a0ece09f3bc405b5f0a832ed34a2b0dfacb50ac6e0b2354cb6cb6'}
ALOLA = {19,20,26,27,28,37,38,50,51,52,53,74,75,76,88,89,103,105}
# Personal-table indices; other forms have explicit numeric labels rather than guessed identities.
LABELS = {386:['Attack','Defense','Speed'], 487:['Origin'], 492:['Sky'], 646:['White','Black'], 678:['Female'], 681:['Blade'], 720:['Unbound'], 745:['Midnight','Dusk'], 746:['School'], 800:['Dusk Mane','Dawn Wings','Ultra']}
def generate():
    raw = {}
    for name, expected in HASHES.items():
        content = (ROOT/'data/reference/capture'/name).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f'{name}: pinned SHA256 mismatch')
        raw[name] = content
    def record(game, sid, form):
        if game == 'personal_sm' and sid > 802: return None
        blob = raw[game]; base = blob[sid*84:(sid+1)*84]
        start = struct.unpack_from('<H',base,0x1c)[0]
        if form and (not start or form >= base[0x20]): return None
        index = start + form - 1 if form else sid
        b = blob[index*84:(index+1)*84]
        return {'catchRate': b[8], 'speed':b[3], 'types':list(dict.fromkeys(b[6:8])), 'gender':b[0x12], 'weight':struct.unpack_from('<H',b,0x26)[0]}
    rows = []
    for species in json.loads((ROOT/'data/pokemon.json').read_text()):
        sid = species['id']; b = raw['personal_uu'][sid*84:(sid+1)*84]
        count = b[0x20] if struct.unpack_from('<H',b,0x1c)[0] else 1
        for form in range(max(1,count)):
            name = species['name']
            if form:
                label = 'Alolan' if sid in ALOLA and form == 1 else (LABELS.get(sid,[])[form-1] if form <= len(LABELS.get(sid,[])) else f'Form {form}')
                name += ' — ' + label
            rows.append({'id':sid, 'form':form, 'name':name, 'sm':record('personal_sm',sid,form), 'usum':record('personal_uu',sid,form)})
    return {'schemaVersion':1,'source':{'repository':'https://github.com/kwsch/PKHeX','commit':COMMIT,'sha256':HASHES,'recordSize':84,'weightUnit':'0.1 kg','types':'Normal Fighting Flying Poison Ground Rock Bug Ghost Steel Fire Water Grass Electric Psychic Ice Dragon Dark Fairy','formMapping':'FormStatsIndex + form - 1; base species 1..802 SM, 1..807 USUM'},'pokemon':rows}
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check',action='store_true'); args=parser.parse_args()
    target=ROOT/'data/capture.json'; text=json.dumps(generate(),ensure_ascii=False,separators=(',',':'))+'\n'
    if args.check:
        if not target.exists() or target.read_text() != text: raise SystemExit('capture.json stale; run tools/build_capture_data.py')
        print('capture.json: pinned hashes and deterministic output verified')
    else: target.write_text(text)
if __name__ == '__main__': main()
