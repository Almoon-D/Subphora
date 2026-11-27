// Copyright (c) 2026 Almoon-D. All rights reserved.
// The owner's wells (decision 0040): the private registry with each well's outcome, depth,
// flow and water levels over time; a form to log or correct a well at the point tapped on
// the map; a reading's form; the CSV import of existing records; and how the map did
// against these wells, apart from the public ones. A change asks the map to draw the
// layer "updated with your wells" again. A reading is typed at the well head, often with
// no coverage (session 17): it is kept on the device first and sent by the outbox, and the
// list of wells is read from the device's copy while the server is out of reach.
import { useEffect, useRef, useState } from "react";

import type { Position } from "../api.ts";
import type { FieldDb, PendingReading, RegistryCopy } from "../field/db.ts";
import type { OutboxView } from "../field/hooks.ts";
import { uuidv7 } from "../field/records.ts";
import { formatDate, formatNumber, lookup, t } from "../i18n/index.ts";
import {
  addReading,
  type Answer,
  belowGround,
  EMPTY_READING,
  deleteWell,
  EMPTY_FORM,
  fetchOwnerValidation,
  fetchRegistry,
  type FormProblem,
  formOf,
  type ImportReport,
  importWells,
  newId,
  OUTCOMES,
  type OwnerValidation,
  PUMP_STATES,
  READERS,
  type ReadingForm,
  readingOf,
  REFERENCES,
  type Registry,
  saveWell,
  type WellForm,
  type WellReading,
  type WellRecord,
  wellFromForm,
} from "./wells.ts";

interface Props {
  /** The point last tapped on the map, offered as the well's position. */
  tapped: Position | null;
  /** Called once a change to the wells that update the map is stored. */
  onChanged: () => void;
  /** The device's store (null while it opens or where IndexedDB is missing) and its
   * outbox, which sends the readings kept there. */
  db: FieldDb | null;
  outbox: Pick<OutboxView, "sync" | "refresh" | "syncing">;
}

type Notice = { kind: "ok"; text: string } | { kind: "error"; text: string } | null;

function failureText(answer: Extract<Answer<unknown>, { ok: false }>): string {
  const reason = lookup(`wells.error.${answer.failure}`, t("wells.error.unexpected"));
  return answer.detail ? `${reason} (${answer.detail})` : reason;
}

function Reading({
  record,
  db,
  onKept,
  onSaved,
}: {
  record: WellRecord;
  db: FieldDb | null;
  /** A reading kept on the device, for the outbox to send. */
  onKept: () => void;
  onSaved: (notice: Notice) => void;
}) {
  const [form, setForm] = useState<ReadingForm>(EMPTY_READING);
  const set = (change: Partial<ReadingForm>) => {
    setForm((current) => ({ ...current, ...change }));
  };
  async function submit() {
    const made = readingOf(record.well.id, form, uuidv7());
    if (!made.ok) {
      onSaved({ kind: "error", text: t(`wells.problem.${made.problem}`) });
      return;
    }
    if (db) {
      // On the device first (hard rule 5): confirmed once it is on disk, then sent.
      try {
        await db.recordReading(made.reading);
      } catch {
        onSaved({ kind: "error", text: t("wells.readingNotKept") });
        return;
      }
      setForm(EMPTY_READING);
      onSaved({ kind: "ok", text: t("wells.readingKept") });
      onKept();
      return;
    }
    // No store on this device: straight to the server, confirmed only once it has it.
    const answer = await addReading(made.reading);
    if (answer.ok) {
      setForm(EMPTY_READING);
    }
    onSaved(answer.ok ? { kind: "ok", text: t("wells.readingSaved") } : { kind: "error", text: failureText(answer) });
  }
  return (
    <form
      className="well-reading"
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      <label>
        {t("wells.readingWhen")}
        <input
          type="datetime-local"
          value={form.when}
          onChange={(event) => {
            set({ when: event.target.value });
          }}
        />
      </label>
      <label>
        {t("wells.readingDepth")}
        <input
          inputMode="decimal"
          value={form.depth}
          onChange={(event) => {
            set({ depth: event.target.value });
          }}
        />
      </label>
      <label>
        {t("wells.readingReference")}
        <select
          value={form.reference}
          onChange={(event) => {
            set({ reference: event.target.value as ReadingForm["reference"] });
          }}
        >
          {REFERENCES.map((reference) => (
            <option key={reference} value={reference}>
              {t(`wells.reference.${reference}`)}
            </option>
          ))}
        </select>
      </label>
      {form.reference === "casing_top" && (
        <label>
          {t("wells.readingHeight")}
          <input
            inputMode="decimal"
            value={form.height}
            onChange={(event) => {
              set({ height: event.target.value });
            }}
          />
        </label>
      )}
      <label>
        {t("wells.readingBy")}
        <select
          value={form.measured_by}
          onChange={(event) => {
            set({
              measured_by: event.target.value as ReadingForm["measured_by"],
            });
          }}
        >
          {READERS.map((reader) => (
            <option key={reader} value={reader}>
              {t(`wells.measuredBy.${reader}`)}
            </option>
          ))}
        </select>
      </label>
      <label>
        {t("wells.readingPump")}
        <select
          value={form.pump}
          onChange={(event) => {
            set({ pump: event.target.value as ReadingForm["pump"] });
          }}
        >
          {PUMP_STATES.map((pump) => (
            <option key={pump} value={pump}>
              {t(`wells.pump.${pump}`)}
            </option>
          ))}
        </select>
      </label>
      {form.pump !== "unknown" && (
        <label>
          {t(`wells.readingMinutes.${form.pump}`)}
          <input
            inputMode="numeric"
            value={form.minutes}
            onChange={(event) => {
              set({ minutes: event.target.value });
            }}
          />
        </label>
      )}
      <p className="note">{t("wells.pumpHint")}</p>
      <button type="submit">{t("wells.addReading")}</button>
    </form>
  );
}

/** A reading as the list shows it: the water below the ground, and the pump if it ran. */
function readingText(reading: WellReading): string {
  const pump = reading.pump === "running" ? ` ${t("wells.whilePumping")}` : "";
  return `${t("wells.readingShort", { depth: formatNumber(belowGround(reading), 2), date: formatDate(reading.measured_at) })}${pump}`;
}

function WellItem({
  record,
  pending,
  offline,
  db,
  onKept,
  onEdit,
  onChanged,
}: {
  record: WellRecord;
  /** The readings of this well still on the device, waiting for the outbox. */
  pending: PendingReading[];
  /** The list is the device's copy: a well cannot be changed now, only read. */
  offline: boolean;
  db: FieldDb | null;
  onKept: () => void;
  onEdit: () => void;
  onChanged: (notice: Notice, mapChanged: boolean) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const { well, readings } = record;
  const last = readings.at(-1);
  const waiting = pending.filter((p) => p.entry.refused === null);
  const refused = pending.filter((p) => p.entry.refused !== null);
  return (
    <li className="well" data-well={well.id} data-outcome={well.outcome}>
      <p>
        <strong>{well.name}</strong> · {t(`wells.outcome.${well.outcome}`)}
        {well.depth_m !== null && ` · ${t("wells.depthShort", { metres: formatNumber(well.depth_m, 1) })}`}
        {well.flow_l_s !== null && ` · ${t("wells.flowShort", { flow: formatNumber(well.flow_l_s, 2) })}`}
      </p>
      {last ? (
        <p className="note">{t("wells.readings", { count: readings.length, last: readingText(last) })}</p>
      ) : (
        <p className="note">{t("wells.noReadings")}</p>
      )}
      {waiting.length > 0 && (
        <p className="note" data-pending-readings={waiting.length}>
          {t("wells.pendingReadings", { count: waiting.length, list: waiting.map((p) => readingText(p.reading)).join("; ") })}
        </p>
      )}
      {refused.map((p) => (
        <p key={p.entry.id} className="error" data-refused-reading={p.entry.refused}>
          {t("wells.refusedReading", {
            reading: readingText(p.reading),
            reason: lookup(`wells.error.${p.entry.refused ?? ""}`, p.entry.refused ?? ""),
          })}
        </p>
      ))}
      <Reading
        record={record}
        db={db}
        onKept={onKept}
        onSaved={(notice) => {
          onChanged(notice, false);
        }}
      />
      {!offline && (
        <p>
          <button type="button" className="secondary" onClick={onEdit}>
            {t("wells.edit")}
          </button>{" "}
          <button
            type="button"
            className="secondary"
            data-delete={confirming ? "confirm" : "ask"}
            onClick={() => {
              if (!confirming) {
                setConfirming(true);
                return;
              }
              void deleteWell(well.id).then((answer) => {
                setConfirming(false);
                onChanged(answer.ok ? { kind: "ok", text: t("wells.deleted") } : { kind: "error", text: failureText(answer) }, answer.ok);
              });
            }}
          >
            {confirming ? t("wells.deleteConfirm") : t("wells.delete")}
          </button>
        </p>
      )}
    </li>
  );
}

function WellFormView({
  form,
  editing,
  tapped,
  onForm,
  onSubmit,
  onCancel,
}: {
  form: WellForm;
  editing: boolean;
  tapped: Position | null;
  onForm: (form: WellForm) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  const field = (key: keyof WellForm, label: string, decimal = false) => (
    <label>
      {label}
      <input
        name={key}
        inputMode={decimal ? "decimal" : undefined}
        value={form[key]}
        onChange={(event) => {
          onForm({ ...form, [key]: event.target.value });
        }}
      />
    </label>
  );
  return (
    <form
      className="well-form"
      aria-label={editing ? t("wells.editHeading") : t("wells.addHeading")}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <h3>{editing ? t("wells.editHeading") : t("wells.addHeading")}</h3>
      {field("name", t("wells.name"))}
      {field("longitude", t("wells.longitude"), true)}
      {field("latitude", t("wells.latitude"), true)}
      {tapped && (
        <button
          type="button"
          className="secondary"
          onClick={() => {
            onForm({ ...form, longitude: tapped[0].toFixed(6), latitude: tapped[1].toFixed(6) });
          }}
        >
          {t("wells.useTapped")}
        </button>
      )}
      <label>
        {t("wells.outcomeLabel")}
        <select
          name="outcome"
          value={form.outcome}
          onChange={(event) => {
            onForm({ ...form, outcome: event.target.value as WellForm["outcome"] });
          }}
        >
          {OUTCOMES.map((outcome) => (
            <option key={outcome} value={outcome}>
              {t(`wells.outcome.${outcome}`)}
            </option>
          ))}
        </select>
      </label>
      {field("depth_m", t("wells.depth"), true)}
      {field("flow_l_s", t("wells.flow"), true)}
      <label>
        {t("wells.drilledOn")}
        <input
          type="date"
          name="drilled_on"
          value={form.drilled_on}
          onChange={(event) => {
            onForm({ ...form, drilled_on: event.target.value });
          }}
        />
      </label>
      {field("note", t("wells.note"))}
      <p>
        <button type="submit">{t("wells.save")}</button>{" "}
        {editing && (
          <button type="button" className="secondary" onClick={onCancel}>
            {t("wells.cancel")}
          </button>
        )}
      </p>
    </form>
  );
}

function ImportResult({ report }: { report: ImportReport }) {
  return (
    <p className="note" data-import-rows={report.rows}>
      {t("wells.imported", {
        rows: report.rows,
        created: report.wells.created,
        unchanged: report.wells.unchanged,
        readings: report.readings.created,
      })}
      {report.conflict_rows.length > 0 && ` ${t("wells.importConflicts", { rows: report.conflict_rows.join(", ") })}`}
    </p>
  );
}

function ValidationView({ result }: { result: OwnerValidation }) {
  return (
    <div className="wells-validation">
      {result.validations.length === 0 && <p className="note">{t("wells.validation.none")}</p>}
      <ul>
        {result.validations.map((v) => (
          <li key={v.domain} data-validation={v.state} data-domain={v.domain}>
            {t(`wells.validation.${v.state}`, {
              label: v.label,
              productive: v.productive,
              dry: v.dry,
              value: v.auc ? formatNumber(v.auc.value, 2) : "",
              low: v.auc ? formatNumber(v.auc.low, 2) : "",
              high: v.auc ? formatNumber(v.auc.high, 2) : "",
            })}
          </li>
        ))}
      </ul>
      {(result.off_map > 0 || result.unknown_outcome > 0) && (
        <p className="note">{t("wells.validation.left", { offMap: result.off_map, unknown: result.unknown_outcome })}</p>
      )}
    </div>
  );
}

export function WellsPanel({ tapped, onChanged, db, outbox }: Props) {
  const [registry, setRegistry] = useState<Answer<Registry> | null>(null);
  // The device's copy, shown while the server is out of reach; and the readings waiting.
  const [copy, setCopy] = useState<RegistryCopy | null>(null);
  const [pending, setPending] = useState<PendingReading[]>([]);
  const [form, setForm] = useState<WellForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [validation, setValidation] = useState<OwnerValidation | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const run = { live: true };
    void fetchRegistry().then(async (answer) => {
      // The list last read stays on screen while the server is out of reach: the
      // device's copy (this page's own reading of it, or an earlier one kept on disk).
      let stored: RegistryCopy | undefined;
      try {
        if (!answer.ok && answer.failure === "network") {
          stored = await db?.registryCopy();
        }
      } catch {
        // The device's copy is a convenience: the list from the server stands without it.
      }
      if (!run.live) {
        return;
      }
      setRegistry(answer);
      if (answer.ok) {
        setCopy({ key: "registry", registry: answer.body, read_at: new Date().toISOString() });
      } else if (stored) {
        setCopy(stored);
      } else if (answer.failure !== "network") {
        setCopy(null);
      }
    });
    if (db) {
      void db.pendingReadings().then(
        (found) => {
          if (run.live) {
            setPending(found);
          }
        },
        () => undefined,
      );
    }
    return () => {
      run.live = false;
    };
  }, [version, db]);

  // The list read from the server is kept on the device, once the device's store is open.
  useEffect(() => {
    if (db && registry?.ok) {
      db.keepRegistry(registry.body).catch(() => undefined);
    }
  }, [db, registry]);

  // Once a round of the outbox ends, what it sent is in the registry: read it again.
  const wasSyncing = useRef(false);
  useEffect(() => {
    if (wasSyncing.current && !outbox.syncing) {
      setVersion((v) => v + 1);
    }
    wasSyncing.current = outbox.syncing;
  }, [outbox.syncing]);

  function kept() {
    setVersion((v) => v + 1);
    outbox.refresh();
    outbox.sync();
  }
  function changed(next: Notice, mapChanged: boolean) {
    setNotice(next);
    setVersion((v) => v + 1);
    if (mapChanged) {
      onChanged();
    }
  }

  const shown = registry?.ok ? registry.body : (copy?.registry ?? null);

  async function submit() {
    const made = wellFromForm(form, editing ?? newId());
    if (!made.ok) {
      setNotice({ kind: "error", text: t(`wells.problem.${made.problem satisfies FormProblem}`) });
      return;
    }
    const answer = await saveWell(made.well);
    if (!answer.ok) {
      // The form keeps what was typed, to send again.
      setNotice({ kind: "error", text: failureText(answer) });
      return;
    }
    setForm(EMPTY_FORM);
    setEditing(null);
    changed({ kind: "ok", text: t("wells.saved") }, true);
  }

  async function upload(file: File) {
    const answer = await importWells(file);
    if (!answer.ok) {
      setNotice({ kind: "error", text: failureText(answer) });
      return;
    }
    setReport(answer.body);
    changed(null, true);
  }

  return (
    <section className="wells" aria-labelledby="wells-heading">
      <h2 id="wells-heading">{t("wells.heading")}</h2>
      <p className="note">{t("wells.privacy")}</p>
      {registry === null && <p className="note">{t("wells.loading")}</p>}
      {registry && !registry.ok && !copy && (
        // Read on opening, not asked for: no alert (the page's alerts answer what was done).
        <p className="error" data-wells-failure={registry.failure}>
          {failureText(registry)}
        </p>
      )}
      {registry && !registry.ok && copy && (
        <p className="note" data-wells-copy={copy.read_at}>
          {t("wells.deviceCopy", { date: formatDate(copy.read_at) })}
        </p>
      )}
      {shown && (
        <>
          {shown.wells.length === 0 ? (
            <p className="note">{t("wells.empty")}</p>
          ) : (
            <ul className="well-list">
              {shown.wells.map((record) => (
                <WellItem
                  key={record.well.id}
                  record={record}
                  pending={pending.filter((p) => p.reading.well_id === record.well.id)}
                  offline={!registry?.ok}
                  db={db}
                  onKept={kept}
                  onEdit={() => {
                    setEditing(record.well.id);
                    setForm(formOf(record.well));
                  }}
                  onChanged={changed}
                />
              ))}
            </ul>
          )}
          <p className="note">{t("wells.layerHint")}</p>
        </>
      )}
      {notice && (
        <p className={notice.kind === "ok" ? "note" : "error"} role={notice.kind === "ok" ? "status" : "alert"}>
          {notice.text}
        </p>
      )}
      <WellFormView
        form={form}
        editing={editing !== null}
        tapped={tapped}
        onForm={setForm}
        onSubmit={() => {
          void submit();
        }}
        onCancel={() => {
          setEditing(null);
          setForm(EMPTY_FORM);
        }}
      />
      <h3>{t("wells.importHeading")}</h3>
      <p className="note">{t("wells.importHint")}</p>
      <label>
        {t("wells.importFile")}
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) {
              void upload(file);
            }
          }}
        />
      </label>
      {report && <ImportResult report={report} />}
      <h3>{t("wells.validationHeading")}</h3>
      <p className="note">{t("wells.validationHint")}</p>
      <button
        type="button"
        className="secondary"
        onClick={() => {
          void fetchOwnerValidation().then((answer) => {
            if (answer.ok) {
              setValidation(answer.body);
            } else {
              setNotice({ kind: "error", text: failureText(answer) });
            }
          });
        }}
      >
        {t("wells.validate")}
      </button>
      {validation && <ValidationView result={validation} />}
    </section>
  );
}
