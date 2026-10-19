import { occurrenceEligible, guideEncounters, guideCalls, projectEncounters, groupUnlock, isWildcardCaller, type GuideEncounter, type GuideSosNode } from "../unlocks";
import { UNLOCKS } from "../types";
import { Fragment } from "preact";
import { memo } from "preact/compat";
import { useEffect, useMemo, useRef, useState } from "preact/hooks";
import { ASSETS, byDex, detailsByDex, formDetails } from "../data";
import { encounterRegionalForm } from "../regional";
import { targetName } from "../collection";
import { CollectionFacts } from "./CollectionFacts";
import { catchNowRows, formKey, formSlug, locationProgress, rateText, safeId } from "../domain";
import {
  activeEncounters,
  activeSaveNamespace,
  activeUnlocks,
  focusedLocation,
  mode,
  speciesStatus,
} from "../state";
import type {
  EncounterGroup as EncounterGroupData,
  EncounterRow as EncounterRowData,
  Island as IslandData,
  Location as LocationData,
} from "../types";
import { consumeRowFocusIntent, openPokemon, rememberLocation } from "../ui";
import { StatusCounts } from "./StatusCounts";
import { PokemonFacts } from "./PokemonFacts";
import {
  AllyForms,
  PokemonIcon,
  RowForms,
  StatusButton,
} from "./StatusControls";

function GuidePokemon({
  id,
  name,
  context = "",
  form,
  ability,
}: {
  id: number;
  name: string;
  context?: string;
  form?: string;
  ability?: string;
}) {
  const key = form
    ? formKey(id, "form", formSlug(form))
    : ability
      ? formKey(id, "ability", formSlug(ability))
      : "";
  const details = formDetails.get(key) || detailsByDex.get(id);
  const actualForm = encounterRegionalForm(id, form ? formSlug(form) : undefined);
  const pokemon = byDex.get(id);
  const encounterName = actualForm && pokemon ? targetName(pokemon, actualForm) : name;
  return (
    <span class="guide-pokemon">
      <StatusButton id={id} form={actualForm} context={context} compact />
      <span class="guide-pokemon-identity">
        <PokemonIcon id={id} />
        <button
          class="guide-pokemon-link"
          type="button"
          onClick={() => openPokemon(id, actualForm)}
        >
          {encounterName}
        </button>
        {actualForm ? <CollectionFacts id={id} form={actualForm} />
          : details && <PokemonFacts details={details} name={name} />}
      </span>
    </span>
  );
}

function Conditions({
  group,
  row,
}: {
  group: EncounterGroupData;
  row: EncounterRowData;
}) {
  const values = [...(group.conditions || []), ...(row.conditions || [])];
  if (!values.length) return <>—</>;
  return (
    <>
      {values.map((value) => (
        <span class="condition" key={value}>
          {value}
        </span>
      ))}
    </>
  );
}

function Allies({ row }: { row: EncounterRowData }) {
  if (!row.allies?.length) return <>—</>;
  return (
    <>
      <span class="ally-label">Called into battle by this Pokémon</span>
      <div class="ally-list">
        {row.allies.map((ally, index) => (
          <Fragment key={`${ally.speciesId}:${ally.form || ""}:${index}`}>
            <GuidePokemon
              id={ally.speciesId}
              name={ally.name}
              context="SOS ally"
              form={ally.form}
            />
            <AllyForms ally={ally} />
          </Fragment>
        ))}
      </div>
    </>
  );
}

function InlineSos({ nodes, root = true }: { nodes: readonly GuideSosNode[]; root?: boolean }) {
  if (!nodes.length) return null;
  return <ul class="inline-sos">
    {root && guideCalls(nodes).some(node => node.call.kind === "sos") &&
      <li class="sos-legend">Ordinary SOS ally share not documented.</li>}
    {nodes.map((node, index) => {
      const { call } = node;
      const row = call.row;
      const conditions = [...(call.group.conditions || []), ...(call.sourceRow.conditions || [])];
      const notes = [...(call.group.notes || []), ...(call.sourceRow.note ? [call.sourceRow.note] : [])];
      return <li class="sos-entry" data-sos-kind={call.kind} data-source-row={call.sourceRow.id} key={`${call.sourceRow.id}:${row.speciesId}:${row.form || ""}:${index}`}>
        {call.kind === "weather-sos" && <span class="sos-method">{`Weather SOS · guide-reported rate: ${row.rates ? rateText(row.rates) : "not documented"} · location-wide rule`}</span>}
        <div class="sos-identity">
          <GuidePokemon id={row.speciesId!} name={row.speciesName || row.species || "Pokémon"} form={row.form} ability={row.ability} context={call.kind === "weather-sos" ? "weather SOS ally" : "SOS ally"} />
          {call.kind === "sos" && <span class="sos-kind">{isWildcardCaller(call.sourceRow) ? "Any listed wild caller" : "SOS"}</span>}
        </div>
        <AllyForms ally={{ speciesId: row.speciesId!, species: row.species || "", name: row.speciesName || "Pokémon", form: row.form }} />
        {conditions.map(condition => <span class="condition" key={condition}>{condition}</span>)}
        {notes.map(note => <span class="sos-note" key={note}>{note}</span>)}
        <InlineSos nodes={node.children} root={false} />
      </li>;
    })}
  </ul>;
}

function PrismaticEncounters({ location }: { location: LocationData }) {
  const flags = activeUnlocks.value;
  const guide = useMemo(() => guideEncounters(location, flags), [location, flags]);
  const unresolved = useMemo(() => {
    const known = new Set(projectEncounters(location, UNLOCKS, true).calls.map(call => call.sourceRow.id));
    return location.groups.flatMap(group => {
      const kind = groupUnlock(group);
      return kind === "sos" || kind === "weather-sos" ? group.encounters.filter(row => !known.has(row.id)).map(row => ({ group, row, kind })) : [];
    });
  }, [location]);
  return <>
    {location.groups.filter(group => !["sos", "weather-sos"].includes(groupUnlock(group) || "")).map(group =>
      <EncounterGroup key={group.id} group={group} location={location} guide={guide.filter(entry => entry.group.id === group.id)} />)}
    {unresolved.filter(entry => flags.includes("sos") && (entry.kind !== "weather-sos" || flags.includes("weather-sos"))).map(({ group, row }) =>
      <p class="sos-source-warning" id={`encounter-${safeId(row.id)}`} tabIndex={-1} key={row.id}>
        <strong>Caller mapping unavailable. </strong>{row.note || `The guide lists ${row.speciesName || "this encounter"}, but supplies no reachable caller mapping.`}
        {[...(group.notes || []), ...(group.conditions || []), ...(row.conditions || [])].map(note => <span key={note}> {note}</span>)}
      </p>)}
  </>;
}

function EncounterRow({
  row,
  group,
  inline,
}: {
  row: EncounterRowData;
  group: EncounterGroupData;
  inline?: GuideSosNode[];
}) {
  return (
    <tr id={`encounter-${safeId(row.id)}`} tabIndex={-1}>
      <th scope="row" class="species-cell">
        <span class="species-name">
          {row.speciesId ? (
            <>
              <GuidePokemon
                id={row.speciesId}
                name={row.speciesName || row.species || "Pokémon"}
                form={row.form}
                ability={row.ability}
              />
              <RowForms row={row} />
            </>
          ) : (
            <span class="muted">All listed wild species</span>
          )}
        </span>
        {inline !== undefined && <InlineSos nodes={inline} />}
      </th>
      <td class={inline === undefined ? undefined : "caller-rate"}>{rateText(row.rates)}</td>
      <td>
        <Conditions group={group} row={row} />
      </td>
      <td>{row.note || "—"}</td>
      {inline === undefined && <td><Allies row={row} /></td>}
    </tr>
  );
}

function EncounterGroup({ group, location, guide }: { group: EncounterGroupData; location: LocationData; guide?: GuideEncounter[] }) {
  const enabled = mode.value === "photonic-prismatic";
  const access = enabled ? guide ? guide.map(entry => entry.eligible) : group.encounters.map(row => occurrenceEligible(location,group,row,false,activeUnlocks.value)) : [];
  const available = access.some(Boolean);
  const partial = available && !access.every(Boolean);
  const levels = group.levels
    ? ` · Lv. ${group.levels.min}–${group.levels.max}`
    : "";
  const notes = [
    ...(group.notes || []),
    ...(group.conditions || []).map((condition) => `Condition: ${condition}`),
  ];
  return (
    <section class={`encounter-group ${group.category}`}>
      <div class="group-heading">
        <strong>
          {group.name}
          {levels}
        </strong>
        <span class="group-tag">
          {enabled ? (available ? (partial ? "Some available" : "Catch now") : "Return later") : (group.category === "return-later" ? "Return later" : "Catch now")}
        </span>
      </div>
      {notes.length > 0 && (
        <div class="group-notes">
          {notes.map((note) => (
            <p key={note}>{note}</p>
          ))}
        </div>
      )}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Pokémon / status</th>
              <th scope="col">{guide ? "Wild rate" : "Chance"}</th>
              <th scope="col">When / where</th>
              <th scope="col">Notes</th>
              {!guide && <th scope="col">SOS allies</th>}
            </tr>
          </thead>
          <tbody>
            {group.encounters.map((row) => (
              <EncounterRow key={row.id} row={row} group={group} inline={guide?.find(entry => entry.row.id === row.id)?.sos} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LocationProgress({ location }: { location: LocationData }) {
  const flags = activeUnlocks.value;
  const progress = locationProgress(location, speciesStatus, flags);
  const base = catchNowRows(location);
  const all = new Set(location.groups.flatMap(g => g.encounters.flatMap(r => [r.speciesId,...r.allies.map(a=>a.speciesId)])).filter((id): id is number => !!id));
  const locked = all.size - progress.total;
  const backtrack = flags.length > 0 && base.length > 0 && base.every(r=>speciesStatus(r.speciesId!) === "caught") && progress.caught < progress.total;
  const complete = progress.total > 0 && progress.caught === progress.total;
  return (
    <span
      class={`location-progress ${complete ? "complete" : ""}`}
      data-location-progress={location.id}
    >
      {progress.total ? (
        <>{complete && <span>Complete · </span>}<StatusCounts counts={progress} label={`${location.name} catch now`} /></>
      ) : "No Pokémon to catch now"}
      {mode.value === "photonic-prismatic" && <span class="location-extras">{locked > 0 && <span class="locked-count">Locked {locked}</span>}{backtrack && <strong data-backtrack="true">↩ Backtrack</strong>}</span>}
    </span>
  );
}

function AssetImage({
  path,
  alt,
  caption = alt,
}: {
  path: string;
  alt: string;
  caption?: string;
}) {
  return (
    <figure>
      <img src={ASSETS[path]} alt={alt} />
      <figcaption>{caption}</figcaption>
    </figure>
  );
}

// Memoised like Pokedex.tsx's DexRowContent: `location` and `open` only change for
// the location(s) whose focus actually moved, so every other already-open
// location's tables would otherwise be rebuilt on every focus change (finishing a
// location, switching mode) for no visible difference.
const Location = memo(function Location({
  location,
  open,
}: {
  location: LocationData;
  open: boolean;
}) {
  // Only the focused location is open on first paint, so rendering every other
  // section's tables and maps means building thousands of nodes and decoding
  // dozens of images nobody has looked at yet. Mount a section's body the first
  // time it is actually opened, then keep it so in-page search and anchor jumps
  // still find it.
  const [mounted, setMounted] = useState(open);
  const memoryMode = mode.value;
  const memoryNamespace = activeSaveNamespace.value;
  useEffect(() => {
    if (open) setMounted(true);
  }, [open]);
  // Render count exposed only for the Playwright test that guards this memoisation;
  // an integer attribute costs nothing worth measuring.
  const renders = useRef(0);
  renders.current += 1;
  return (
    <details
      class="location"
      id={`location-${safeId(location.id)}`}
      data-location-id={location.id}
      data-renders={renders.current}
      open={open}
      onToggle={(event) => {
        if (event.currentTarget.open) {
          setMounted(true);
          rememberLocation(location.id, memoryMode, memoryNamespace);
        }
      }}
    >
      <summary id={`encounter-${safeId(location.id)}`} onClick={(event) => {
        if (!(event.currentTarget.parentElement as HTMLDetailsElement).open) {
          // An old in-app jump is no longer an explicit request after manual browsing.
          history.replaceState(null, "", window.location.href.split("#")[0]);
          rememberLocation(location.id, memoryMode, memoryNamespace);
        }
      }}>
        <span class="location-heading">
          <span class="location-title">{location.name}</span>
          <LocationProgress location={location} />
        </span>
      </summary>
      {mounted && (
        <div class="location-body">
          {!!location.assets?.length && (
            <div class="map-grid">
              {location.assets.map((path) => {
                const numbered = /map/i.test(path);
                const alt = numbered
                  ? `${location.name} numbered grass map`
                  : `${location.name} location screenshot`;
                return (
                  <AssetImage
                    key={path}
                    path={path}
                    alt={alt}
                    caption={
                      numbered ? `${alt} · numbers match the grass groups` : alt
                    }
                  />
                );
              })}
            </div>
          )}
          {!!location.notes?.length && (
            <div class="notes">
              {location.notes.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </div>
          )}
          {mode.value === "photonic-prismatic" ? <PrismaticEncounters location={location} /> : location.groups.map((group) => (
            <EncounterGroup key={group.id} group={group} location={location} />
          ))}
        </div>
      )}
    </details>
  );
});

function Island({
  island,
  openLocation,
}: {
  island: IslandData;
  openLocation: string | null;
}) {
  return (
    <section class="island">
      <h2>{island.name}</h2>
      {!!island.assets?.length && (
        <div class="map-grid">
          {island.assets.map((path) => (
            <AssetImage
              key={path}
              path={path}
              alt={`${island.name} overview map`}
            />
          ))}
        </div>
      )}
      {island.locations.map((location) => (
        <Location
          key={location.id}
          location={location}
          open={location.id === openLocation}
        />
      ))}
    </section>
  );
}

export function LocationList({ inert = false }: { inert?: boolean }) {
  const encounters = activeEncounters.value;
  const openLocation = focusedLocation.value;
  const currentMode = mode.value;
  const namespace = activeSaveNamespace.value;
  useEffect(() => {
    if (!openLocation) return;
    // jumpTo() is about to scroll to and focus a specific row in this location
    // itself; focusing the summary here would win the race and steal it back.
    if (consumeRowFocusIntent(openLocation)) return;
    requestAnimationFrame(() => {
      const target = document.querySelector<HTMLElement>(
        `[data-location-id="${CSS.escape(openLocation)}"]`,
      );
      target?.scrollIntoView({ block: "start" });
      target
        ?.querySelector<HTMLElement>("summary")
        ?.focus({ preventScroll: true });
    });
  }, [currentMode, namespace, openLocation]);
  return (
    <main id="main-view" tabIndex={-1} inert={inert}>
      {encounters.islands.map((island) => (
        <Island key={`${namespace}:${currentMode}:${island.id}`} island={island} openLocation={openLocation} />
      ))}
    </main>
  );
}
