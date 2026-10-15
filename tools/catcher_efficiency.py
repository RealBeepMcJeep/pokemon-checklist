"""Separate, bounded Gen VII False Swipe damage lens; never capture probability.

Neutral field/no items/no boosts/no critical hits; ordinary offensive ability
scenarios and declared attacker status. Defender ability/retaliation excluded.
Q12 rounding is checked against pinned @smogon/calc 0.10.0, generation 7.
"""
from __future__ import annotations

TYPES=frozenset("Normal Fire Water Electric Grass Ice Fighting Poison Ground Flying Psychic Bug Rock Ghost Dragon Dark Steel Fairy".split())
PASSIVE=frozenset({"",None,"Own Tempo","Dry Skin","Effect Spore","Swarm","Mold Breaker","Rock Head","Lightning Rod","Overgrow","Leaf Guard","Emergency Exit","Limber","Unburden","No Guard","Compound Eyes","Chlorophyll","Early Bird","Inner Focus","Keen Eye"})
ACTIVE=frozenset({"Technician","Huge Power","Pure Power","Hustle","Tough Claws","Adaptability","Guts","Toxic Boost","Rivalry"})

def poke_round(numerator: int, denominator: int=4096) -> int:
    """Round nearest, exact halves DOWN, using integer arithmetic."""
    whole,remainder=divmod(numerator,denominator)
    return whole+(2*remainder>denominator)

def damage_rolls(*,level: int,attack: int,defense: int,attacker_types: list[str],
                 defender_types: list[str],ability: str|None=None,status: str="",
                 rivalry: str="neutral") -> list[int]:
    if not 1<=level<=100 or min(attack,defense)<1:
        raise ValueError("level must be 1..100; attack/defense must be positive")
    if not attacker_types or not defender_types or not set(attacker_types+defender_types)<=TYPES:
        raise ValueError("Unknown/empty Gen VII typing")
    if ability not in PASSIVE|ACTIVE:
        raise ValueError(f"Unsupported offensive ability scenario: {ability}")
    if status not in {"","brn","psn","tox","par","slp","frz"} or rivalry not in {"neutral","same","opposite"}:
        raise ValueError("Unknown status or Rivalry scenario")
    if "Ghost" in defender_types:
        return [0]*16
    bp=40
    if ability=="Technician" or (ability=="Toxic Boost" and status in {"psn","tox"}):
        bp=poke_round(bp*6144)
    elif ability=="Tough Claws":
        bp=poke_round(bp*5325)
    elif ability=="Rivalry" and rivalry!="neutral":
        bp=poke_round(bp*(5120 if rivalry=="same" else 3072))
    if ability in {"Huge Power","Pure Power"}:
        attack*=2
    elif ability=="Hustle" or (ability=="Guts" and status):
        attack=poke_round(attack*6144)
    base=(((2*level//5+2)*bp*attack//defense)//50)+2
    stab=8192 if ability=="Adaptability" and "Normal" in attacker_types else (6144 if "Normal" in attacker_types else 4096)
    resistance=2**sum(t in {"Rock","Steel"} for t in defender_types)
    values=[]
    for random in range(85,101):
        result=poke_round((base*random//100)*stab)//resistance
        if status=="brn" and ability!="Guts":result//=2
        values.append(max(1,result))
    return values


def expected_actions(hp: int, rolls: list[int], accuracy: float=1.0) -> float|None:
    """Expected False Swipe attempts to HP=1; misses and zero damage self-loop.

    Damage rolls are equiprobable and independent, noncritical, with no opponent
    actions. False Swipe never KOs. None means impossible, not zero actions.
    """
    if not isinstance(hp,int) or not 1<=hp<=10000 or not rolls:
        raise ValueError("hp must be 1..10000 and rolls nonempty")
    if not 0<=accuracy<=1 or any(not isinstance(d,int) or d<0 for d in rolls):
        raise ValueError("Invalid accuracy/damage distribution")
    if hp==1:return 0.0
    positive=[d for d in rolls if d>0]
    progress=accuracy*len(positive)/len(rolls)
    if not progress:return None
    expected=[0.0]*(hp+1)
    for current in range(2,hp+1):
        future=accuracy*sum(expected[max(1,current-d)] for d in positive)/len(rolls)
        expected[current]=(1+future)/progress
    return expected[hp]


def stat(base: int,level: int,*,iv: int=31,ev: int=0,nature: int=10,hp: bool=False) -> int:
    if not 1<=base<=255 or not 1<=level<=100 or not 0<=iv<=31 or not 0<=ev<=252 or nature not in {9,10,11}:
        raise ValueError("Invalid Gen VII stat assumptions")
    value=(2*base+iv+ev//4)*level//100
    return value+level+10 if hp else (value+5)*nature//10


def expected_with_fang(hp: int,rolls: list[int],accuracy: float=1.0,fang_accuracy: float=0.9) -> float|None:
    """Optimal FS/Fang damage-action policy, NEVER permitting Fang at 1 HP.

    Fixed Normal immunity applies to both; no status, retaliation, balls, switch
    costs, PP exhaustion or opponent recovery is included.
    """
    expected_actions(hp,rolls,accuracy)  # shared validation
    if not 0<fang_accuracy<=1:raise ValueError("Invalid Fang accuracy")
    if hp==1:return 0.0
    if not any(rolls):return None
    positive=[d for d in rolls if d>0]
    progress=accuracy*len(positive)/len(rolls)
    expected=[0.0]*(hp+1)
    for current in range(2,hp+1):
        swipe=(1+accuracy*sum(expected[max(1,current-d)] for d in positive)/len(rolls))/progress if progress else float("inf")
        fang=1/fang_accuracy+expected[current-max(1,current//2)]
        expected[current]=min(swipe,fang)
    return expected[hp]


def compare(utility: dict,cache,*,target_level: int=20) -> dict:
    """Attach an independent, explicitly hypothetical lens; never mutate utility."""
    import re
    from pathlib import Path
    import catcher_score as cs
    import story_moves as sm
    from showdown_text import object_after,list_field
    sources=sm.MoveSources(Path(cache))
    data=cs.load_rank_data(Path(cache))
    def profile(slug):
        body=data["dex"][slug]
        stats={k:int(v) for k,v in re.findall(r"(\w+):\s*(\d+)",object_after(body,"baseStats") or "")}
        return body,stats,list_field(body,"types")
    targets=[]
    for slug in ["pikachu","roggenrola","magnemite","gastly","hoppip"]:
        _,stats,types=profile(slug)
        targets.append({"name":sources.data.nice[slug],"types":types,"hp":stat(stats["hp"],target_level,hp=True),"defense":stat(stats["def"],target_level),"level":target_level})
    candidates=[(r,False) for r in utility["rows"] if r["false_swipe"]]
    paras=next((r for r in utility["rows"] if r["name"]=="Paras"),None)
    if paras and utility["level"]>=24:
        evolved=cs.ml.normalize("Parasect")
        from copy import deepcopy
        row=deepcopy(paras)
        row.update(name="Parasect",slug=evolved,dex=sources.data.id_of[evolved],path=paras["path"]+["Parasect"])
        candidates.append((row,True))
    rows=[]
    for parent,optional in candidates:
        body,stats,types=profile(parent["slug"])
        for slot,ability in cs.ability_slots(body).items():
            if slot=="H":continue
            scenarios=["neutral","same","opposite"] if ability=="Rivalry" else ["neutral"]
            for rivalry in scenarios:
                targets_for_row=[]
                attack=stat(stats["atk"],utility["level"])
                hit=0.8 if ability=="Hustle" else 1.0
                has_fang=any(p["move_id"]=="superfang" for p in parent["parts"])
                for target in targets:
                    rolls=damage_rolls(level=utility["level"],attack=attack,defense=target["defense"],attacker_types=types,defender_types=target["types"],ability=ability,rivalry=rivalry)
                    sensitivity=[]
                    for iv,ev,nature in [(0,0,9),(31,252,11)]:
                        variation=damage_rolls(level=utility["level"],attack=stat(stats["atk"],utility["level"],iv=iv,ev=ev,nature=nature),defense=target["defense"],attacker_types=types,defender_types=target["types"],ability=ability,rivalry=rivalry)
                        sensitivity.append(expected_actions(target["hp"],variation,hit))
                    targets_for_row.append(dict(target,damage_rolls=rolls,swipe_attempts=expected_actions(target["hp"],rolls,hit),swipe_attempts_attacker_stat_extremes=sensitivity,
                        fang_then_swipe_policy=expected_with_fang(target["hp"],rolls,hit) if has_fang else None,
                        blocked="Normal/Ghost immunity; requires a separately sourced bypass" if "Ghost" in target["types"] else None))
                rows.append({"name":parent["name"],"dex":parent["dex"],"owned":parent["owned"],"owned_dex":parent["owned_dex"],"path":parent["path"],"ability":ability,"ability_slot":slot,"ability_unconfirmed":True,"rivalry":rivalry,"optional_evolution":optional,"utility_score":parent["score"],"attack":attack,"base_attack":stats["atk"],"types":types,"accuracy":hit,"has_super_fang_in_selected_kit":has_fang,"setup_required":parent.get("setup_required",False),"unsafe_contact_ability":ability=="Effect Spore","targets":targets_for_row})
    return {"schema":1,"level":utility["level"],"source_caught_ids":utility["source_caught_ids"],"utility_source":utility["source"],"rows":rows,
        "no_false_swipe":[{"name":r["name"],"owned":r["owned"],"utility_score":r["score"]} for r in utility["rows"] if not r["false_swipe"]],
        "targets":targets,"assumptions":{"iv":31,"ev":0,"nature":"neutral","target_level":target_level,"ordinary_ability_scenarios_only":True,"actual_ability_unknown":True,"base_form_assumed":True,"attacker_full_hp":True,"no_items_boosts_criticals_field_or_target_abilities":True,"random_damage":"16 equiprobable Gen VII rolls, 85..100","stat_sensitivity":"attacker IV0/EV0/Attack-down vs IV31/EV252/Attack-up; target fixed","metric":"Expected damage-action attempts to reach 1 HP; excludes status, switching, PP limits, retaliation/recovery and ball throws","super_fang":"Optional optimal Fang/False Swipe policy only for a selected obtainable Fang kit; Fang NEVER used at 1 HP","engine_limit":"Stock Gen VII model/reference agreement; Prismatic battle-engine equivalence unverified"},
        "reference":{"package":"@smogon/calc","version":"0.10.0","gitHead":"3c539689dd2185696f7c95ba6e26407b2e4889c4","generation":7,"url":"https://github.com/smogon/damage-calc/tree/3c539689dd2185696f7c95ba6e26407b2e4889c4"}}


def card_rows(report: dict) -> list[dict]:
    chosen=[r for r in report["rows"] if r["name"] in {"Paras","Parasect","Smeargle","Kricketune"} and not r["unsafe_contact_ability"] and r["rivalry"]=="neutral"]
    others=sorted((r for r in report["rows"] if r["name"] not in {c["name"] for c in chosen} and r["rivalry"]=="neutral" and not r["unsafe_contact_ability"]),key=lambda r:sum(t["swipe_attempts"] or 0 for t in r["targets"]))
    for row in others:
        if row["name"] not in {c["name"] for c in chosen}:
            chosen.append(row)
            if len(chosen)>=7:break
    return chosen[:8]


def render(report: dict,output) -> None:
    from PIL import Image,ImageDraw
    import story_team_cards as art
    rows=card_rows(report)
    if not rows:raise ValueError("No owned, horizon-ready False Swipe carrier")
    height=370+len(rows)*300+500
    canvas=Image.new("RGB",(1260,height),art.BG);draw=ImageDraw.Draw(canvas)
    atlas=Image.open(art.ATLAS).convert("RGBA");accent="#80d398"
    def text(x,y,value,size=22,color=art.DIM,bold=False,width=1130,max_lines=4):
        lines=art.wrapped_lines(draw,str(value),art.font(size,bold),width,max_lines=max_lines)
        for i,line in enumerate(lines):draw.text((x,y+i*(size+6)),line,font=art.font(size,bold),fill=color)
        return len(lines)*(size+6)
    text(54,30,"SEPARATE LENS / NOT CATCH PROBABILITY",24,accent,True)
    text(54,80,"FALSE SWIPE: HOW MANY ACTIONS?",40,art.WHITE,True)
    text(54,145,f"Attackers L{report['level']} / benchmarks L{report['assumptions']['target_level']} / lower is faster",27)
    text(54,190,"IV31, EV0, neutral nature; ordinary ability SCENARIOS, not your known slot.",22)
    text(54,232,"Noncritical; no items, boosts, field, defender abilities or opponent actions.",22)
    text(54,274,"Counts damage attempts to 1 HP, including misses. Sleep/switches/throws excluded.",22)
    text(54,316,"Utility POINTS below are unchanged and do not rank damage throughput.",21,accent)
    for index,row in enumerate(rows):
        top=370+index*300
        draw.rounded_rectangle((35,top,1225,top+283),radius=22,fill=art.PANEL,outline=art.LINE,width=2)
        icon=art.sprite(atlas,row["dex"],3);canvas.paste(icon,(52,top+12),icon)
        text(193,top+14,f"{row['name']} / {row['ability']}",29,art.WHITE,True,width=990)
        label="OPTIONAL L24 EVOLUTION after Spore L22" if row["optional_evolution"] else ("SKETCH SETUP; retained copies unconfirmed" if row["setup_required"] else "Owned path: "+" -> ".join(row["path"]))
        text(193,top+57,label,20,width=975)
        text(193,top+89,f"Utility {row['utility_score']:.2f} pts / model Atk {row['attack']} / ability unconfirmed",20,width=975)
        for j,target in enumerate(row["targets"]):
            x=64+j*233
            text(x,top+137,target["name"],21,art.WHITE,True,width=220)
            value="BLOCKED" if target["swipe_attempts"] is None else f"{target['swipe_attempts']:.2f}"
            text(x,top+171,value,31,accent,True,width=220)
            damage=target["damage_rolls"]
            text(x,top+212,f"{min(damage)}-{max(damage)} HP/hit",18,width=220)
        if row["has_super_fang_in_selected_kit"]:
            t=row["targets"][0]
            text(64,top+248,f"With selected Super Fang: optimal damage-only policy vs Pikachu = {t['fang_then_swipe_policy']:.2f} actions",18,accent,width=1120)
        elif row["utility_score"]<=25:
            text(64,top+248,"HP-control partner only: this comparison does not give it sleep or make it the best solo catcher.",18,accent,width=1120)
    y=390+len(rows)*300
    notes=[
      "Pikachu neutral / Roggenrola Rock / Magnemite Steel / Gastly Ghost / Hoppip Grass benchmark.",
      "Parasect is optional only after Paras learns Spore at L22; evolve at L24. Same utility, stronger Attack.",
      "Technician helps Smeargle's False Swipe; it does NOT improve the throw's odds once HP/status match.",
      "Ghosts need a separately sourced Foresight/Odor Sleuth/Soak plan; the selected 3-slot Sketch kit may need changing.",
      "Spore and Sleep Powder fail on Grass/Overcoat/Goggles; sleep immunity still applies. Effect Spore can poison.",
      "Butterfree has NO False Swipe. Use it with a verified HP-control partner if keeping it as sleeper.",
      "Full JSON includes IV/EV/nature sensitivity and all carriers. These are scenarios, not measured individual stats.",
      "Pinned Gen VII reference-model agreement; Prismatic damage-engine equivalence unverified."]
    for note in notes:y+=text(54,y,note,20,width=1140)+10
    if y>height-12:raise ValueError("Efficiency footer overflow")
    canvas.save(output,optimize=True)


def main() -> int:
    import argparse,json,os,zipfile,math
    from pathlib import Path
    import catcher_now as now
    import catcher_score as cs
    from showdown_data import configured_cache_dir
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--uid");group.add_argument("--species")
    parser.add_argument("--cache",type=Path,default=configured_cache_dir())
    parser.add_argument("--level",type=int,default=30)
    parser.add_argument("--target-level",type=int,default=20)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    if not 2<=args.level<=100 or not 1<=args.target_level<=100:parser.error("Invalid benchmark levels")
    records=cs.read_account_records(args.uid,now.ROOT) if args.uid else {}
    utility=now.build_report(records,args.cache,args.level,species=args.species)
    utility["source_seen_ids"]=sorted(int(k.split(":")[1]) for k,v in records.items() if k.startswith("species:") and v.get("s")=="seen")
    for row in utility["rows"]:
        if not math.isclose(row["score"],sum(p["contribution"] for p in row["parts"]),abs_tol=1e-10):raise ValueError("Utility arithmetic mismatch")
    efficiency=compare(utility,args.cache,target_level=args.target_level)
    efficiency["source_seen_ids"]=utility["source_seen_ids"]
    args.output_dir.mkdir(parents=True,exist_ok=True);args.output_dir.chmod(0o700)
    (args.output_dir/"utility.json").write_text(json.dumps(utility,indent=2,allow_nan=False))
    (args.output_dir/"efficiency.json").write_text(json.dumps(efficiency,indent=2,allow_nan=False))
    now.render(utility,args.output_dir/"catchers.png");render(efficiency,args.output_dir/"false-swipe-efficiency.png")
    with zipfile.ZipFile(args.output_dir/"catcher-comparison.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for name in ["utility.json","efficiency.json","catchers.png","false-swipe-efficiency.png"]:archive.write(args.output_dir/name,name)
    if args.uid:
        fresh=cs.read_account_records(args.uid,now.ROOT)
        for kind,key in [("caught","source_caught_ids"),("seen","source_seen_ids")]:
            ids=sorted(int(k.split(":")[1]) for k,v in fresh.items() if k.startswith("species:") and v.get("s")==kind)
            if ids!=utility[key]:raise RuntimeError(f"{kind} state changed; regenerate this snapshot before delivery")
    for path in args.output_dir.iterdir():
        if path.is_file():path.chmod(0o600)
    print(json.dumps({"output_dir":str(args.output_dir),"caught":len(utility["source_caught_ids"]),"rows":len(efficiency["rows"]),"utility_unchanged":True,"live_readback_verified":bool(args.uid),"files":[p.name for p in args.output_dir.iterdir()]}))
    return 0

if __name__=="__main__":raise SystemExit(main())
