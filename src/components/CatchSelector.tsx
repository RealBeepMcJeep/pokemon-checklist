import { useLayoutEffect, useRef, useState } from "preact/hooks";
import pokemonAtlas from "../../assets/gen7-icons.png?url";
import ballAtlas from "../../assets/catch-balls.png?url";
export type Choice = { name: string; id?: number; form?: number };
export function CatchSprite({kind, item, index, scale = 1}: {kind: string; item: Choice; index: number; scale?: number}) {
  const species = kind === "species", frame = species ? 40 : 30, cols = species ? 32 : 8;
  const slot = species ? item.id! - 1 : index;
  return <span class="catch-sprite" aria-hidden="true" style={{width: frame * scale, height: 30 * scale}}><img alt="" draggable={false} src={species ? pokemonAtlas : ballAtlas} style={{width: cols * frame * scale, height: (species ? 780 : 90) * scale, transform: `translate(-${slot % cols * frame * scale}px, -${Math.floor(slot / cols) * 30 * scale}px)`}} /></span>;
}
export function CatchSelector({kind, options, value, onChange, detail}: {kind: "species" | "ball"; options: Choice[]; value: string; onChange: (name: string) => void; detail?: string}) {
  const id = "catch-" + kind, index = options.findIndex(o => o.name === value);
  const [editing, setEditing] = useState(false), [draft, setDraft] = useState(""), [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const gesture = useRef<{x: number; y: number} | null>(null), swiped = useRef(false);
  const navigate = (delta: number) => choose(options[(index + delta + options.length) % options.length].name);
  const normalize = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const filtered = options.map((item, index) => ({item, index})).filter(o => normalize(o.item.name).includes(normalize(draft))).slice(0, 60);
  useLayoutEffect(() => { if(editing) input.current?.focus(); }, [editing]);
  useLayoutEffect(() => { if(active >= 0) document.getElementById(id + "-option-" + active)?.scrollIntoView({block: "nearest"}); }, [active, id]);
  const choose = (name: string) => { onChange(name); setEditing(false); setDraft(""); setActive(-1); };
  return <section class="catch-selector" data-kind={kind} aria-label={kind === "species" ? "Pokémon selector" : "Ball selector"}>
    <div id={id + "-rail"} class="catch-rail" onKeyDown={e => {if(e.key === "ArrowLeft" || e.key === "ArrowRight") {e.preventDefault(); navigate(e.key === "ArrowRight" ? 1 : -1);}}}
      onTouchStart={e => {if(e.touches.length !== 1) {gesture.current=null;return;} const t = e.touches[0]; gesture.current = {x:t.clientX,y:t.clientY}; swiped.current=false;}}
      onTouchEnd={e => {const t = e.changedTouches[0], start = gesture.current; gesture.current=null; if(start && Math.abs(t.clientX-start.x) > 45 && Math.abs(t.clientX-start.x) > Math.abs(t.clientY-start.y)*1.5) {swiped.current=true; navigate(t.clientX < start.x ? 1 : -1);}}} onTouchCancel={() => {gesture.current=null;}}>
      {[-1,0,1].map(delta => {const n = (index + delta + options.length) % options.length, item = options[n]; return <button type="button" class={delta === 0 ? "selected" : "neighbor"} aria-label={"Select " + item.name} aria-pressed={delta === 0} onClick={() => {if(!swiped.current) choose(item.name); swiped.current=false;}}><CatchSprite kind={kind} item={item} index={n} scale={delta === 0 ? 2 : 1}/>{kind === "species" && <small>{item.form ? "Form " + item.form : "#" + item.id}</small>}</button>;})}
    </div>
    <div class="catch-combobox" onBlur={e => {if(!e.currentTarget.contains(e.relatedTarget as Node | null)) setEditing(false);}}>
      <button hidden={editing} id={id + "-name"} class="catch-name" type="button" onClick={() => {setDraft(""); setActive(-1); if(input.current) {input.current.hidden = false; input.current.focus();} setEditing(true);}}>{value}</button>
      <input hidden={!editing} ref={input} id={id} aria-label={kind === "species" ? "Pokémon / form" : "Ball"} placeholder={kind === "species" ? "Pokémon Name" : "Ball Name"} role="combobox" aria-expanded={true} aria-autocomplete="list" aria-controls={id + "-list"} aria-activedescendant={active >= 0 ? id + "-option-" + active : undefined} autoComplete="off" value={draft} onInput={e => {setDraft(e.currentTarget.value); setActive(-1);}} onKeyDown={e => {if(e.key === "Escape") {e.preventDefault(); e.stopPropagation(); setEditing(false); document.getElementById(id + "-rail")?.querySelector<HTMLButtonElement>(".selected")?.focus();} else if(e.key === "ArrowDown" || e.key === "ArrowUp") {e.preventDefault(); setActive(a => filtered.length ? a < 0 ? (e.key === "ArrowDown" ? 0 : filtered.length - 1) : (a + (e.key === "ArrowDown" ? 1 : -1) + filtered.length) % filtered.length : -1);} else if(e.key === "Enter" && active >= 0) {e.preventDefault(); choose(filtered[active].item.name);}}}/>
      {editing && <ul id={id + "-list"} role="listbox" aria-label={kind + " suggestions"}>{filtered.map(({item,index},n) => <li id={id + "-option-" + n} role="option" aria-selected={active === n} tabIndex={-1} onPointerDown={e => {if(e.pointerType === "mouse") e.preventDefault();}} onClick={() => choose(item.name)}><CatchSprite kind={kind} item={item} index={index}/><span>{item.name}</span></li>)}{!filtered.length && <li>No matching selection</li>}</ul>}
    </div>
    {<p class={"catch-selector-note muted " + (kind === "species" ? "catch-form-note" : "catch-ball-note")}>{kind === "species" ? options[index].form ? "Form " + options[index].form + " · base-species icon" : "#" + options[index].id + " · National Dex order" : detail}</p>}
  </section>;
}
