import { ATLAS, byDex } from "../data";
import { STATUS_LABEL, formSlug } from "../domain";
import {
        cycleForm,
        formDefinitions,
        formSignal,
        formsTracked,
        savedNotice,
        speciesSignal,
} from "../state";
import { changeSpecies } from "../ui";
import type { Ally, EncounterRow, Status } from "../types";

const STATUS_SYMBOL = {
        none: "❌",
        caught: "✅",
        seen: "👁️",
} satisfies Record<Status, string>;

export function PokemonIcon({ id }: { id: number }) {
        return (
                <span
                        class="icon"
                        aria-hidden="true"
                        style={{
                                backgroundPosition: `-${((id - 1) % ATLAS.columns) * ATLAS.frameWidth}px -${Math.floor((id - 1) / ATLAS.columns) * ATLAS.frameHeight}px`,
                        }}
                />
        );
}

export function StatusButton({
        id,
        context = "",
        compact = false,
}: {
        id: number;
        context?: string;
        compact?: boolean;
}) {
        const status = speciesSignal(id).value;
        const displayName = byDex.get(id)?.name || "Pokémon";
        const label = `${displayName}${context ? ` ${context}` : ""} status: ${STATUS_LABEL[status]}. Activate to cycle status.`;
        return (
                <button
                        type="button"
                        class={`status-button status-${status} ${compact ? "compact-status" : ""}`}
                        data-action="species"
                        data-species={id}
                        aria-label={label}
                        onClick={() => changeSpecies(id)}
                >
                        {compact ? (
                                <>
                                        <span
                                                class="status-symbol"
                                                aria-hidden="true"
                                        >
                                                {STATUS_SYMBOL[status]}
                                        </span>
                                        <span class="status-text visually-hidden">
                                                {STATUS_LABEL[status]}
                                        </span>
                                </>
                        ) : (
                                <span class="status-text">
                                        {STATUS_LABEL[status]}
                                </span>
                        )}
                </button>
        );
}

export function FormStatusButton({
        formKey,
        prefix = "",
}: {
        formKey: string;
        prefix?: string;
}) {
        const form = formDefinitions.get(formKey);
        if (!form) return null;
        const status = formSignal(formKey).value;
        const label = `${prefix || byDex.get(form.speciesId)?.name || "Pokémon"} ${form.label} form status: ${STATUS_LABEL[status]}. Activate to cycle status.`;
        return (
                <button
                        type="button"
                        class={`status-button form-status status-${status}`}
                        data-action="form"
                        data-form={formKey}
                        aria-label={label}
                        onClick={() => {
                                cycleForm(formKey);
                                savedNotice("Form status");
                        }}
                >
                        <span>{form.label}</span>
                        <span class="status-text">{STATUS_LABEL[status]}</span>
                </button>
        );
}

export function RowForms({ row }: { row: EncounterRow }) {
        if (!formsTracked.value || !row.speciesId) return null;
        const keys = [
                ...(row.form ? [`${row.speciesId}:${formSlug(row.form)}`] : []),
                ...(row.forms || []).map(
                        (form) => `${row.speciesId}:${formSlug(form)}`,
                ),
                ...(row.ability
                        ? [`${row.speciesId}:ability-${formSlug(row.ability)}`]
                        : []),
        ];
        return (
                <div class="form-list">
                        {[...new Set(keys)]
                                .filter((key) => formDefinitions.has(key))
                                .map((key) => (
                                        <FormStatusButton
                                                key={key}
                                                formKey={key}
                                        />
                                ))}
                </div>
        );
}

export function AllyForms({ ally }: { ally: Ally }) {
        if (!formsTracked.value || !ally.form) return null;
        return (
                <FormStatusButton
                        formKey={`${ally.speciesId}:${formSlug(ally.form)}`}
                />
        );
}
