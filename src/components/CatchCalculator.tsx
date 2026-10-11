import { useEffect, useState } from "preact/hooks";
import capture from "../../data/capture.json";
import {
  BALLS,
  ballModifiers,
  probability,
  dexBonus,
  type Status,
  type CaptureStats,
} from "../capture";
import { mode } from "../state";
function Combobox({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false),
    [active, setActive] = useState(-1);
  const filtered = options
    .filter((o) => o.toLocaleLowerCase().includes(value.toLocaleLowerCase()))
    .slice(0, 60);
  useEffect(() => {
    if (open && active >= 0)
      document
        .getElementById(id + "-option-" + active)
        ?.scrollIntoView({ block: "nearest" });
  }, [active, open, id]);
  const choose = (v: string) => {
    onChange(v);
    setOpen(false);
    setActive(-1);
  };
  return (
    <div
      class="catch-combobox"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null))
          setOpen(false);
      }}
    >
      <label for={id}>{label}</label>
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={id + "-list"}
        aria-activedescendant={
          open && active >= 0 ? id + "-option-" + active : undefined
        }
        value={value}
        autoComplete="off"
        onFocus={() => setOpen(true)}
        onInput={(e) => {
          onChange(e.currentTarget.value);
          setOpen(true);
          setActive(-1);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape" && open) {
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
          } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            setActive((a) =>
              filtered.length
                ? a < 0
                  ? e.key === "ArrowDown"
                    ? 0
                    : filtered.length - 1
                  : (a + (e.key === "ArrowDown" ? 1 : -1) + filtered.length) %
                    filtered.length
                : -1,
            );
          } else if (e.key === "Enter" && open && active >= 0) {
            e.preventDefault();
            choose(filtered[active]);
          }
        }}
      />
      {open && (
        <ul
          id={id + "-list"}
          role="listbox"
          aria-label={label + " suggestions"}
        >
          {filtered.map((o, n) => (
            <li
              id={id + "-option-" + n}
              role="option"
              aria-selected={active === n}
              tabIndex={-1}
              onPointerDown={(e) => {
                if (e.pointerType === "mouse") e.preventDefault();
              }}
              onClick={() => {
                choose(o);
                document.getElementById(id)?.focus();
                setOpen(false);
              }}
            >
              {o}
            </li>
          ))}
          {!filtered.length && <li>No matching selection</li>}
        </ul>
      )}
    </div>
  );
}
const context = {
  turn: 1,
  level: 10,
  yourLevel: 10,
  night: false,
  cave: false,
  fishing: false,
  surfing: false,
  registered: false,
  sameSpecies: false,
  oppositeGender: false,
};
export function CatchCalculator() {
  const [species, setSpecies] = useState("Pikachu"),
    [ball, setBall] = useState("Poké Ball");
  const [status, setStatus] = useState<Status>("none"),
    [percent, setPercent] = useState(100),
    [exact, setExact] = useState(false),
    [current, setCurrent] = useState(100),
    [max, setMax] = useState(100);
  const [caught, setCaught] = useState(0),
    [roto, setRoto] = useState(false),
    [override, setOverride] = useState(false),
    [rate, setRate] = useState(45);
  const [conditions, setConditions] = useState(context);
  const conditionNumber = (
    key: "turn" | "level" | "yourLevel",
    label: string,
    max = 100,
  ) => (
    <label>
      {label}
      <input
        type="number"
        min="1"
        max={max}
        step="1"
        value={conditions[key]}
        onInput={(e) =>
          setConditions({ ...conditions, [key]: e.currentTarget.valueAsNumber })
        }
      />
    </label>
  );
  const conditionCheck = (
    key:
      | "night"
      | "cave"
      | "surfing"
      | "fishing"
      | "registered"
      | "sameSpecies"
      | "oppositeGender",
    label: string,
  ) => (
    <label class="catch-check">
      <input
        type="checkbox"
        checked={conditions[key]}
        onChange={(e) =>
          setConditions({ ...conditions, [key]: e.currentTarget.checked })
        }
      />
      {label}
    </label>
  );
  const game = mode.value === "sun" || mode.value === "moon" ? "sm" : "usum";
  const pokemon = capture.pokemon.find((p) => p.name === species);
  const stats = pokemon?.[game] as CaptureStats | undefined | null;
  const maxInvalid =
    exact && (!Number.isInteger(max) || max < 1 || max > 65535);
  const currentInvalid =
    exact &&
    (!Number.isInteger(current) ||
      current < 1 ||
      (!maxInvalid && current > max));
  let error = "",
    result: ReturnType<typeof probability> | undefined,
    modifiers: ReturnType<typeof ballModifiers> | undefined;
  try {
    if (maxInvalid)
      throw new Error("Maximum HP must be a whole number from 1 to 65535.");
    if (currentInvalid)
      throw new Error(
        "Current HP must be a whole number from 1 to Maximum HP.",
      );
    if (!pokemon || !BALLS.includes(ball))
      throw new Error(
        "Select a valid Pokémon / form and ball from the suggestions.",
      );
    if (!stats)
      throw new Error(
        "This species / form is unavailable in stock Sun / Moon. Choose an Ultra game mode.",
      );
    modifiers = ballModifiers(
      ball,
      {
        ...stats,
        catchRate: override ? rate : stats.catchRate,
        id: pokemon.id,
      },
      conditions,
      game,
    );
    result = probability({
      catchRate: modifiers.rate,
      ballBonus: modifiers.bonus,
      currentHP: exact ? current : percent,
      maxHP: exact ? max : 100,
      status,
      roto: roto && game === "usum",
      caught,
      master: modifiers.master,
    });
  } catch (e) {
    error = (e as Error).message;
  }
  return (
    <section id="catch-calculator" aria-labelledby="catch-title">
      <h3 id="catch-title">Catch calculator</h3>
      <p class="muted">
        Documented Gen VII model ·{" "}
        {game === "sm" ? "Sun / Moon" : "Ultra Sun / Ultra Moon"} stock data.
        Inputs are temporary and never change your checklist.
      </p>
      <div class="catch-grid">
        <Combobox
          id="catch-species"
          label="Pokémon / form"
          value={species}
          onChange={setSpecies}
          options={capture.pokemon.map((p) => p.name)}
        />
        <Combobox
          id="catch-ball"
          label="Ball"
          value={ball}
          onChange={setBall}
          options={BALLS}
        />
      </div>
      <div class="catch-feedback">
        {error && (
          <p id="catch-error" role="status">
            {error}
          </p>
        )}
        {result && (
          <p id="catch-result" role="status">
            <strong>{(result.probability * 100).toFixed(2)}%</strong> per throw
          </p>
        )}
      </div>
      {[
        "Quick Ball",
        "Timer Ball",
        "Nest Ball",
        "Level Ball",
        "Dusk Ball",
        "Dive Ball",
        "Lure Ball",
        "Repeat Ball",
        "Love Ball",
      ].includes(ball) && (
        <fieldset>
          <legend>{ball} conditions</legend>
          {(ball === "Quick Ball" || ball === "Timer Ball") && (
            <>
              {conditionNumber("turn", "Turn number", 9999)}
              <p class="muted">
                Turn 1 means no turns have elapsed. Quick: ×5 only on turn 1.
                Timer: min(4, 1 + (turn − 1) × 1229/4096).
              </p>
            </>
          )}
          {(ball === "Nest Ball" || ball === "Level Ball") &&
            conditionNumber("level", "Target level")}
          {ball === "Level Ball" &&
            conditionNumber("yourLevel", "Your active Pokémon level")}
          {ball === "Dusk Ball" && (
            <>
              {conditionCheck("night", "Nighttime")}
              {conditionCheck("cave", "Inside a cave")}
            </>
          )}
          {(ball === "Dive Ball" || ball === "Lure Ball") && (
            <>
              {conditionCheck("fishing", "Fishing encounter")}
              {ball === "Dive Ball" &&
                conditionCheck("surfing", "Surfing encounter")}
            </>
          )}
          {ball === "Repeat Ball" && (
            <>
              {conditionCheck(
                "registered",
                "This species was registered caught in this game's Pokédex",
              )}
              <p class="muted">
                Historical registration, including trades and evolutions; not
                your current checklist inventory.
              </p>
            </>
          )}
          {ball === "Love Ball" && (
            <>
              {conditionCheck(
                "sameSpecies",
                "Same species as your active Pokémon",
              )}
              {conditionCheck(
                "oppositeGender",
                "Opposite male / female genders",
              )}
              <p class="muted">
                Genderless and single-gender species cannot meet both
                conditions.
              </p>
            </>
          )}
        </fieldset>
      )}
      <fieldset>
        <legend>Health</legend>
        <label class="catch-check">
          <input
            type="checkbox"
            checked={exact}
            onChange={(e) => {
              if (
                e.currentTarget.checked &&
                Number.isInteger(max) &&
                max >= 1 &&
                max <= 65535
              )
                setCurrent(Math.max(1, Math.round((percent * max) / 100)));
              setExact(e.currentTarget.checked);
            }}
          />{" "}
          Exact HP inputs
        </label>
        {exact ? (
          <div class="catch-grid">
            <label>
              Current HP
              <input
                type="number"
                min="1"
                max={max}
                step="1"
                aria-invalid={currentInvalid}
                aria-describedby={currentInvalid ? "catch-error" : undefined}
                value={current}
                onInput={(e) => setCurrent(e.currentTarget.valueAsNumber)}
              />
            </label>
            <label>
              Maximum HP
              <input
                type="number"
                min="1"
                max="65535"
                step="1"
                aria-invalid={maxInvalid}
                aria-describedby={maxInvalid ? "catch-error" : undefined}
                value={max}
                onInput={(e) => setMax(e.currentTarget.valueAsNumber)}
              />
            </label>
          </div>
        ) : (
          <label>
            HP remaining (approximate %)
            <input
              type="range"
              min="1"
              max="100"
              step="1"
              value={percent}
              onInput={(e) => setPercent(e.currentTarget.valueAsNumber)}
            />
            <output>{percent}%</output>
          </label>
        )}
        <button
          type="button"
          class="action-button"
          onClick={() => {
            setExact(true);
            setCurrent(1);
          }}
        >
          Set 1 HP
        </button>
        {!exact && (
          <p class="muted">
            Percent mode estimates HP using a 100-HP target; rounding can differ
            from your actual HP. A fainted Pokémon cannot be caught.
          </p>
        )}
      </fieldset>
      <fieldset>
        <legend>Major status · one at a time</legend>
        <div class="catch-status">
          {(
            [
              ["none", "None"],
              ["slp", "Asleep"],
              ["frz", "Frozen"],
              ["par", "Paralyzed"],
              ["psn", "Poisoned"],
              ["brn", "Burned"],
            ] as [Status, string][]
          ).map(([key, label]) => (
            <label class="catch-check">
              <input
                type="checkbox"
                checked={status === key}
                onChange={(e) =>
                  setStatus(e.currentTarget.checked ? key : "none")
                }
              />
              {label}
            </label>
          ))}
        </div>
      </fieldset>
      <details class="catch-advanced">
        <summary>Optional modifiers &amp; hack override</summary>
        <label>
          Historical registered-caught species
          <input
            type="number"
            min="0"
            max="807"
            step="1"
            value={caught}
            onInput={(e) => setCaught(e.currentTarget.valueAsNumber)}
          />
        </label>
        <p class="muted">
          Default 0: no critical-capture bonus. Use this game's historical
          Pokédex registrations, including trades and evolutions, not the
          checklist's currently-owned total.
        </p>
        <label class="catch-check">
          <input
            type="checkbox"
            disabled={game === "sm"}
            checked={game === "usum" && roto}
            onChange={(e) => setRoto(e.currentTarget.checked)}
          />
          Roto Catch ×2.5
        </label>
        <p class="muted">
          USUM only; default off. The Cave of Dragonflies' firsthand USUM report
          identifies it with max Capture O-Power (250%). Not a verified
          hack-engine constant.
        </p>
        <label class="catch-check">
          <input
            type="checkbox"
            checked={override}
            onChange={(e) => setOverride(e.currentTarget.checked)}
          />
          Override stock catch rate
        </label>
        {override && (
          <label>
            Catch rate override (0–255)
            <input
              type="number"
              min="0"
              max="255"
              step="1"
              value={rate}
              onInput={(e) => setRate(e.currentTarget.valueAsNumber)}
            />
          </label>
        )}
      </details>
      {result && modifiers && (
        <>
          <p id="catch-breakdown">
            Catch rate {modifiers.rate}
            {override ? " (OVERRIDE)" : " (stock)"} · Ball ×{modifiers.bonus} ·
            Status ×{result.statusBonus} · Roto ×
            {game === "usum" && roto ? 2.5 : 1} · Dex ×{dexBonus(caught)}
            <br />
            HP {exact ? current : percent}/{exact ? max : 100}
            {modifiers.master ? (
              " · Master Ball bypasses shake / critical checks for a legal capturable wild encounter."
            ) : (
              <>
                {" "}
                · X {result.x.toFixed(4)} · Ordinary{" "}
                {(result.ordinary * 100).toFixed(2)}% · Critical event{" "}
                {(result.critical * 100).toFixed(2)}% · Critical success{" "}
                {(result.q * 100).toFixed(2)}%
              </>
            )}
          </p>
        </>
      )}
      <details id="catch-notes">
        <summary>Equation, data &amp; assumptions</summary>
        <p>
          This is the documented Gen VII calculator model, not bit-exact engine
          emulation. Exact HP means exact inputs, not verified executable
          arithmetic. Only legal capturable wild encounters are modeled: no
          trainer battles or fainted targets. Selecting a species does not mean
          it has a wild location.
        </p>
        <p>
          Stock SM / USUM personal-table catch rate, speed, type, gender and
          form weight are used. Prismatic / Photonic engine behavior and altered
          stats are unverified assumptions; the override changes only catch
          rate, not speed, weight or type. Some alternate forms use explicit
          personal-table form numbers rather than names.
        </p>
        <pre>{`down(v) = floor(v × 4096) / 4096
round(v) = floor(v × 4096 + 0.5) / 4096
x0 = round(3M − 2H)  [ordinary terrain G = 1]
x1 = round(x0 × C × B)
x2 = down(x1 / (3M))
x3 = round(x2 × S)
X = min(255, down(x3 × R))
b = floor(round(65536 / round(round(255/X)^(3/16))))
q = b / 65536
k = floor(round(round(X × D) / 6))
c = k / 256
P = c × q + (1 − c) × q⁴`}</pre>
        <p>
          X=0 gives zero; X≥255 guarantees a legal catch. Master Ball bypasses
          the routine. D: 0 for 0–30 registered species, 0.5 for 31–150, 1 for
          151–300, 1.5 for 301–450, 2 for 451–600, 2.5 for 601+. S: 2.5
          asleep/frozen; 1.5 paralyzed/poisoned/burned; otherwise 1.
        </p>
        <p>
          Heavy uses form weight: below 100 kg −20; 100–199.9 kg +0; 200–299.9
          kg +20; ≥300 kg +30, capped at 255. SM allows rate 0 (its Heavy bug);
          USUM clamps Heavy to at least 1. Ordinary non-Beast / non-Master balls
          against Ultra Beasts use 410/4096. Beast is ×5 against Ultra Beasts,
          otherwise 410/4096. Net ×3.5 Water/Bug; Moon ×4 for Moon Stone
          evolution targets (Nidorina, Nidorino, Clefairy, Jigglypuff, Skitty,
          Munna), not other members of their families. Unboosted balls ×1.
          Safari, Sport, Dream and Park are not normally usable Gen VII balls
          and are omitted.
        </p>
        <ul>
          <li>
            <a
              href="https://www.dragonflycave.com/mechanics/gen-vi-vii-capturing"
              target="_blank"
              rel="noreferrer"
            >
              The Cave of Dragonflies: documented mechanics
            </a>{" "}
            and{" "}
            <a
              href="https://www.dragonflycave.com/gen6capture-worker.js?v=2"
              target="_blank"
              rel="noreferrer"
            >
              reference worker
            </a>{" "}
            (retained offline in tests).
          </li>
          <li>
            <a
              href="https://www.dragonflycave.com/update-archive/2018"
              target="_blank"
              rel="noreferrer"
            >
              Firsthand USUM Roto / Nest correction report
            </a>
            .
          </li>
          <li>
            <a
              href="https://github.com/kwsch/PKHeX/tree/542111fc8584ff29c9d1455553b8acd0e1f8a59a"
              target="_blank"
              rel="noreferrer"
            >
              Pinned PKHeX stock data, 542111fc
            </a>
            ; generated offline with SHA256 verification.
          </li>
        </ul>
      </details>
    </section>
  );
}
