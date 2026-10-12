import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { CatchRail } from "./CatchRail";
import pokemonAtlas from "../../assets/gen7-icons.png?url";
import ballAtlas from "../../assets/catch-balls.png?url";
export type Choice = { name: string; id?: number; form?: number };
export function CatchSprite({kind, item, index, scale = 1}: {kind: string; item: Choice; index: number; scale?: number}) {
  const species = kind === "species", frame = species ? 40 : 30, cols = species ? 32 : 8;
  const slot = species ? item.id! - 1 : index;
  return <span class="catch-sprite" aria-hidden="true" style={{width: frame * scale, height: 30 * scale}}><img alt="" draggable={false} src={species ? pokemonAtlas : ballAtlas} style={{width: cols * frame * scale, height: (species ? 780 : 90) * scale, transform: `translate(-${slot % cols * frame * scale}px, -${Math.floor(slot / cols) * 30 * scale}px)`}} /></span>;
}
export function CatchSelector({kind, options, value, onChange, detail, rateBadge}: {kind: "species" | "ball"; options: Choice[]; value: string; onChange: (name: string) => void; detail?: string; rateBadge?: {label: string; explanation: string}}) {
  const id = "catch-" + kind, index = Math.max(0, options.findIndex(o => o.name === value));
  const [editing, setEditing] = useState(false), [draft, setDraft] = useState(""), [active, setActive] = useState(-1);
  const input = useRef<HTMLInputElement>(null);

  const normalize = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
  const filtered = options.map((item, index) => ({item, index})).filter(o => normalize(o.item.name).includes(normalize(draft))).slice(0, 60);
  useLayoutEffect(() => { if(editing) input.current?.focus(); }, [editing]);
  useLayoutEffect(() => { if(active >= 0) document.getElementById(id + "-option-" + active)?.scrollIntoView({block: "nearest"}); }, [active, id]);
  const choose = (name: string) => { onChange(name); setEditing(false); setDraft(""); setActive(-1); };
  return <section class="catch-selector" data-kind={kind} aria-label={kind === "species" ? "Pokémon selector" : "Ball selector"}>
    <CatchRail kind={kind} options={options} value={value} onChange={choose}/>
    <div class="catch-combobox" onBlur={e => {if(!e.currentTarget.contains(e.relatedTarget as Node | null)) setEditing(false);}}>
      <button hidden={editing} id={id + "-name"} class="catch-name" type="button" onClick={() => {setDraft(""); setActive(-1); if(input.current) {input.current.hidden = false; input.current.focus();} setEditing(true);}}>{value}</button>
      <input hidden={!editing} ref={input} id={id} aria-label={kind === "species" ? "Pokémon / form" : "Ball"} placeholder={kind === "species" ? "Pokémon Name" : "Ball Name"} role="combobox" aria-expanded={true} aria-autocomplete="list" aria-controls={id + "-list"} aria-activedescendant={active >= 0 ? id + "-option-" + active : undefined} autoComplete="off" value={draft} onInput={e => {setDraft(e.currentTarget.value); setActive(-1);}} onKeyDown={e => {if(e.key === "Escape") {e.preventDefault(); e.stopPropagation(); setEditing(false); document.getElementById(id + "-rail")?.querySelector<HTMLButtonElement>(".selected")?.focus();} else if(e.key === "ArrowDown" || e.key === "ArrowUp") {e.preventDefault(); setActive(a => filtered.length ? a < 0 ? (e.key === "ArrowDown" ? 0 : filtered.length - 1) : (a + (e.key === "ArrowDown" ? 1 : -1) + filtered.length) % filtered.length : -1);} else if(e.key === "Enter" && active >= 0) {e.preventDefault(); choose(filtered[active].item.name);}}}/>
      {editing && <ul id={id + "-list"} role="listbox" aria-label={kind + " suggestions"}>{filtered.map(({item,index},n) => <li id={id + "-option-" + n} role="option" aria-selected={active === n} tabIndex={-1} onPointerDown={e => {if(e.pointerType === "mouse") e.preventDefault();}} onClick={() => choose(item.name)}><CatchSprite kind={kind} item={item} index={index}/><span>{item.name}</span></li>)}{!filtered.length && <li>No matching selection</li>}</ul>}
    </div>
    {<p class={"catch-selector-note muted " + (kind === "species" ? "catch-form-note" : "catch-ball-note")}>{kind === "species" ? options[index].form ? "Form " + options[index].form + " · base-species icon" : "#" + options[index].id : detail}{rateBadge && <> · <span class="catch-rate" title={rateBadge.explanation} aria-label={rateBadge.explanation}>{rateBadge.label}</span></>}</p>}
  </section>;
}
