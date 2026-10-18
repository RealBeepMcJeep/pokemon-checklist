"""Combined cards retain original pixels and expose real equipment effects."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import story_team_cards as cards
import team_options

def fixture():
    moves=[{"name":"Tackle","type":"Normal","gate":"Level 1"} for _ in range(4)]
    members=[{"owned":name,"final":name,"dex":dex,"owned_dex":dex,"types":[typ],"tier":"RU","favorite":False,"evolution":name,"moves":copy.deepcopy(moves)} for name,dex,typ in [("Gengar",94,"Ghost"),("Arcanine",59,"Fire"),("Raichu",26,"Electric"),("Pidgeot",18,"Flying"),("Slowbro",80,"Water")]]
    report={"utility":"Butterfree","utility_dex":12,"caught_records":6,"utility_moves":moves}
    option={"category":"OG","anchor":"Gengar","members":members,"evolving":0,"level_evolving":0,"new_entries":0,"core_synergy":6.8,"six_synergy":6.6}
    equipment=[]
    for member in [{"owned":"Butterfree","final":"Butterfree","dex":12,"moves":moves,"evolution":"Fixed catching utility"},*members]:
        choice={"item":{"name":"Sitrus Berry","effect":"Restores 1/4 max HP when at 1/2 max HP or less. Single use."},"access":{"location":"Route 2 berry tree north of Pokemon Center","status":"stock-USUM-fallback","gate":"Daily pile; collection is conditional."}}
        equipment.append({**copy.deepcopy(member),"story":{"current":copy.deepcopy(choice),"later":copy.deepcopy(choice)}})
    return report,option,{"category":"OG","members":equipment}

class EquipmentTests(unittest.TestCase):
    def test_combined_card_adds_effects_without_losing_any_original_pixels(self):
        report,option,equipment=fixture();atlas=Image.open(cards.ATLAS).convert("RGBA")
        texts=[];original=ImageDraw.ImageDraw.text
        def observe(self,xy,text,*args,**kwargs):
            texts.append(str(text));return original(self,xy,text,*args,**kwargs)
        with tempfile.TemporaryDirectory() as folder:
            plain=Path(folder)/"plain.png";combined=Path(folder)/"combined.png"
            cards.render_card(report,option,1,atlas,plain,generated="test")
            with patch.object(ImageDraw.ImageDraw,"text",observe):cards.render_card(report,{**option,"equipment":equipment},1,atlas,combined,generated="test")
            with Image.open(combined) as image:self.assertGreater(image.height,cards.SIZE[1],"equipment must expand the card, not disappear")
            self.assertIn("Restores 1/4 max HP when at 1/2 max HP or less. Single use."," ".join(texts))
            layout=json.loads(combined.with_suffix('.layout.json').read_text());self.assertEqual(len(layout['rows']),6)
            with Image.open(plain) as source,Image.open(combined) as target:
                for top,bottom,destination in layout['preserved_slices']:
                    self.assertEqual(source.crop((0,top,source.width,bottom)).tobytes(),target.crop((0,destination,target.width,destination+bottom-top)).tobytes())

    def test_report_retains_all_initial_favorites_not_just_selected_members(self):
        roster={"caught_count":1,"canonical_count":1,"records":{"species:1":{"s":"caught"},"species:2":{"s":"seen"},"star:777":{"s":"on"},"star:25":{"s":"off"}}}
        report=team_options.story_report(roster,[],{"final":"Butterfree","endpoint_id":12})
        self.assertEqual(report.get('source_starred_ids'),[777])

    def test_missing_effect_mismatched_member_and_overlong_text_fail_closed(self):
        report,option,equipment=fixture();atlas=Image.open(cards.ATLAS).convert('RGBA')
        with tempfile.TemporaryDirectory() as folder:
            for kind in ['missing','member','long']:
                bad=copy.deepcopy(equipment)
                if kind=='missing':bad['members'][0]['story']['current']['item']['effect']=''
                elif kind=='member':bad['members'][0]['final']='Wrong Pokemon'
                else:bad['members'][0]['story']['current']['item']['effect']='Essential words must not be silently discarded. '*100
                with self.subTest(kind=kind),self.assertRaises(ValueError):cards.render_card(report,{**option,'equipment':bad},1,atlas,Path(folder)/'bad.png',generated='test')

    def test_offline_redraw_binds_hash_and_never_changes_the_story_snapshot(self):
        import hashlib
        report,option,equipment=fixture();report['options']=[];held: dict={'teams':[]}
        for category in ['OG','Non-OG','Mixed','Pokedex','Best']:
            report['options'].append({**copy.deepcopy(option),'category':category})
            held['teams'].append({**copy.deepcopy(equipment),'category':category})
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);source=folder/'story.json';items=folder/'items.json'
            source.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
            held['source_team_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();items.write_text(json.dumps(held))
            with patch('team_builder.read_records',side_effect=AssertionError('offline redraw must not read account')):
                self.assertEqual(cards.main(['--report-json',str(source),'--held-items-json',str(items),'--output-dir',str(folder/'out')]),0)
            self.assertEqual(source.read_bytes(),(folder/'out/story-options.json').read_bytes())
            held['source_team_sha256']='0'*64;items.write_text(json.dumps(held))
            with self.assertRaisesRegex(ValueError,'exact saved team'):cards.main(['--report-json',str(source),'--held-items-json',str(items),'--output-dir',str(folder/'wrong')])

    def test_new_report_favorites_must_match_the_observed_initial_snapshot(self):
        import held_item_cards
        team={'source_caught_ids':[],'source_seen_ids':[],'source_starred_ids':[777]}
        expected={'caught':[],'seen':[],'starred':[25]}
        with self.assertRaises(ValueError):held_item_cards.validate_sources(team,expected,{'star:25':{'s':'on'}})

if __name__=='__main__':unittest.main()
