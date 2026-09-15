import { Fragment } from "preact";
import { useEffect } from "preact/hooks";
import { ASSETS } from "../data";
import { locationProgress, rateText, safeId } from "../domain";
import {
  activeEncounters,
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
import { AllyForms, RowForms, StatusButton } from "./StatusControls";

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
            <StatusButton
              id={ally.speciesId}
              name={ally.name}
              context="SOS ally"
            />
            <AllyForms ally={ally} />
          </Fragment>
        ))}
      </div>
    </>
  );
}

function EncounterRow({
  row,
  group,
}: {
  row: EncounterRowData;
  group: EncounterGroupData;
}) {
  return (
    <tr id={`encounter-${safeId(row.id)}`} tabIndex={-1}>
      <th scope="row" class="species-cell">
        <span class="species-name">
          {row.speciesId ? (
            <>
              <StatusButton id={row.speciesId} name={row.speciesName} />
              <RowForms row={row} />
            </>
          ) : (
            <span class="muted">All listed wild species</span>
          )}
        </span>
      </th>
      <td>{rateText(row.rates)}</td>
      <td>
        <Conditions group={group} row={row} />
      </td>
      <td>{row.note || "—"}</td>
      <td>
        <Allies row={row} />
      </td>
    </tr>
  );
}

function EncounterGroup({ group }: { group: EncounterGroupData }) {
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
          {group.category === "return-later" ? "Return later" : "Catch now"}
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
              <th scope="col">Chance</th>
              <th scope="col">When / where</th>
              <th scope="col">Notes</th>
              <th scope="col">SOS allies</th>
            </tr>
          </thead>
          <tbody>
            {group.encounters.map((row) => (
              <EncounterRow key={row.id} row={row} group={group} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LocationProgress({ location }: { location: LocationData }) {
  const progress = locationProgress(location, speciesStatus);
  const complete = progress.total > 0 && progress.caught === progress.total;
  return (
    <span
      class={`location-progress ${complete ? "complete" : ""}`}
      data-location-progress={location.id}
    >
      {progress.total
        ? `${complete ? "Complete · " : ""}${progress.caught} / ${progress.total} caught here`
        : "No Pokémon to catch now"}
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

function Location({
  location,
  open,
}: {
  location: LocationData;
  open: boolean;
}) {
  return (
    <details
      class="location"
      id={`location-${safeId(location.id)}`}
      data-location-id={location.id}
      open={open}
    >
      <summary>
        <span class="location-heading">
          <span class="location-title">{location.name}</span>
          <LocationProgress location={location} />
        </span>
      </summary>
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
        {location.groups.map((group) => (
          <EncounterGroup key={group.id} group={group} />
        ))}
      </div>
    </details>
  );
}

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

export function LocationList() {
  const encounters = activeEncounters.value;
  const openLocation = focusedLocation.value;
  const currentMode = mode.value;
  useEffect(() => {
    if (!openLocation) return;
    requestAnimationFrame(() => {
      const target = document.querySelector<HTMLElement>(
        `[data-location-id="${CSS.escape(openLocation)}"]`,
      );
      target?.scrollIntoView({ block: "start" });
      target
        ?.querySelector<HTMLElement>("summary")
        ?.focus({ preventScroll: true });
    });
  }, [currentMode, openLocation]);
  return (
    <main id="main-view" tabIndex={-1}>
      {encounters.islands.map((island) => (
        <Island key={island.id} island={island} openLocation={openLocation} />
      ))}
    </main>
  );
}
