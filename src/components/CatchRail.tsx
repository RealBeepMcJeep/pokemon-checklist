import {useLayoutEffect, useRef, useState} from "preact/hooks";
import {CatchSprite, type Choice} from "./CatchSelector";

const step = 62;
type Drag = {id: number; x: number; y: number; offset: number; horizontal: boolean};
export function CatchRail({kind, options, value, onChange}: {kind: "species" | "ball"; options: Choice[]; value: string; onChange: (name: string) => void}) {
  const index = Math.max(0, options.findIndex(o => o.name === value));
  const [offset, setOffset] = useState(0), [settling, setSettling] = useState(true);
  const drag = useRef<Drag | null>(null);
  const frames = useRef<number[]>([]);
  const expected = useRef<string | null>(null);
  const suppressed = useRef<{id: number; time: number} | null>(null);
  const rail = useRef<HTMLDivElement>(null);
  const signature = options.map(o => o.name).join("\n");
  function clearFrames() { frames.current.forEach(cancelAnimationFrame); frames.current = []; }
  function reset() { clearFrames(); drag.current = null; setSettling(true); setOffset(0); }
  useLayoutEffect(() => {
    if (expected.current === value) expected.current = null;
    else reset();
  }, [value, signature]);
  useLayoutEffect(() => () => { clearFrames(); drag.current = null; }, []);
  function animate(from: number) {
    clearFrames();
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setOffset(0); setSettling(true); return; }
    setSettling(false); setOffset(from);
    frames.current.push(requestAnimationFrame(() => {
      frames.current.push(requestAnimationFrame(() => { setSettling(true); setOffset(0); frames.current = []; }));
    }));
  }
  function navigate(delta: number, from = 0) {
    const next = options[(index + delta + options.length) % options.length];
    expected.current = next.name;
    onChange(next.name);
    animate(from + delta * step);
  }
  function finish(cancelled: boolean) {
    const d = drag.current;
    if (!d) return;
    drag.current = null;
    if (d.horizontal) {
      suppressed.current = {id: d.id, time: performance.now()};
      if (!cancelled && Math.abs(d.offset) >= 38) navigate(d.offset < 0 ? 1 : -1, d.offset);
      else { clearFrames(); setSettling(true); setOffset(0); }
    }
    if (rail.current?.hasPointerCapture(d.id)) rail.current.releasePointerCapture(d.id);
  }
  if (!options.length) return null;
  return <div ref={rail} id={`catch-${kind}-rail`} class="catch-rail" data-dragging={!settling}
    onKeyDown={e => { if(e.key === "ArrowLeft" || e.key === "ArrowRight") {e.preventDefault(); reset(); navigate(e.key === "ArrowRight" ? 1 : -1);} }}
    onPointerDown={e => {
      if (drag.current || !e.isPrimary) { finish(true); return; }
      if (e.button !== 0) return;
      suppressed.current = null;
      clearFrames();
      drag.current = {id: e.pointerId, x: e.clientX, y: e.clientY, offset: 0, horizontal: false};
    }}
    onPointerMove={e => {
      const d = drag.current;
      if (!d || d.id !== e.pointerId) return;
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (!d.horizontal) {
        if (Math.abs(dy) > 8 && Math.abs(dy) >= Math.abs(dx)) {
          suppressed.current = {id: d.id, time: performance.now()};
          drag.current = null; setSettling(true); setOffset(0); return;
        }
        if (Math.abs(dx) < 8 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
        d.horizontal = true;
        e.currentTarget.setPointerCapture(e.pointerId);
      }
      d.offset = Math.max(-step * 1.5, Math.min(step * 1.5, dx));
      setSettling(false); setOffset(d.offset);
    }}
    onPointerUp={() => finish(false)} onPointerCancel={() => finish(true)} onLostPointerCapture={e => {if (e.target === e.currentTarget) finish(true);}}
    onTouchStart={e => {if (e.touches.length > 1) finish(true);}}
    onClickCapture={e => {
      const s = suppressed.current;
      if (s && e.detail > 0 && performance.now() - s.time < 500 && (!("pointerId" in e) || e.pointerId === s.id)) {
        e.preventDefault(); e.stopPropagation(); suppressed.current = null;
      }
    }}>
    <div class="catch-artwork" aria-hidden="true">{[-2,-1,0,1,2].map(delta => {
      const n = (index + delta + options.length) % options.length;
      const x = delta * step + offset;
      return <span class="catch-visual" data-slot={delta} style={{transform: `translateX(${x}px)`, transition: settling ? undefined : "none"}}><span style={{display: "block", transform: `scale(${Math.max(.5, 1 - Math.abs(x) / (step * 2))})`}}><CatchSprite kind={kind} item={options[n]} index={n} scale={2}/></span></span>;
    })}</div>
    {[-1,0,1].map(delta => {
      const n = (index + delta + options.length) % options.length, item = options[n];
      return <button type="button" class={delta === 0 ? "selected" : "neighbor"} aria-label={"Select " + item.name} aria-pressed={delta === 0} onClick={() => {if(delta) navigate(delta); else onChange(item.name);}}><CatchSprite kind={kind} item={item} index={n} scale={delta === 0 ? 2 : 1}/>{kind === "species" && <small>{item.form ? "Form " + item.form : "#" + item.id}</small>}</button>;
    })}
  </div>;
}
