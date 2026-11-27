// Copyright (c) 2026 Almoon-D. All rights reserved.
// The owner's wells (decision 0040): the private registry with each well's outcome, depth,
// flow and water levels over time; a form to log or correct a well at the point tapped on
// the map; a reading's form; the CSV import of existing records; and how the map did
// against these wells, apart from the public ones. A change asks the map to draw the
// layer "updated with your wells" again.
import { useEffect, useState } from "react";

import type { Position } from "../api.ts";
import { formatDate, formatNumber, lookup, t } from "../i18n/index.ts";
import {
  addReading,
  type Answer,
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
  readingOf,
  type Registry,
  saveWell,
  type WellForm,
  type WellRecord,
  wellFromForm,
} from "./wells.ts";

interface Props {
  /** The point last tapped on the map, offered as the well's position. */
  tapped: Position | null;
  /** Called once a change to the wells that update the map is stored. */
  onChanged: () => void;
}

type Notice = { kind: "ok"; text: string } | { kind: "error"; text: string } | null;

function failureText(answer: Extract<Answer<unknown>, { ok: false }>): string {
  const reason = lookup(`wells.error.${answer.failure}`, t("wells.error.unexpected"));
  return answer.detail ? `${reason} (${answer.detail})` : reason;
}

function Reading({ record, onSaved }: { record: WellRecord; onSaved: (notice: Notice) => void }) {
  const [when, setWhen] = useState("");
  const [depth, setDepth] = useState("");
  async function submit() {
    const reading = readingOf(record.well.id, when, depth);
    if (!reading) {
      onSaved({ kind: "error", text: t("wells.problem.reading") });
      return;
    }
    const answer = await addReading(reading);
    if (answer.ok) {
      setWhen("");
      setDepth("");
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
          value={when}
          onChange={(event) => {
            setWhen(event.target.value);
          }}
        />
      </label>
      <label>
        {t("wells.readingDepth")}
        <input
          inputMode="decimal"
          value={depth}
          onChange={(event) => {
            setDepth(event.target.value);
          }}
        />
      </label>
      <button type="submit">{t("wells.addReading")}</button>
    </form>
  );
}

function WellItem({
  record,
  onEdit,
  onChanged,
}: {
  record: WellRecord;
  onEdit: () => void;
  onChanged: (notice: Notice, mapChanged: boolean) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const { well, readings } = record;
  const last = readings.at(-1);
  return (
    <li className="well" data-well={well.id} data-outcome={well.outcome}>
      <p>
        <strong>{well.name}</strong> · {t(`wells.outcome.${well.outcome}`)}
        {well.depth_m !== null && ` · ${t("wells.depthShort", { metres: formatNumber(well.depth_m, 1) })}`}
        {well.flow_l_s !== null && ` · ${t("wells.flowShort", { flow: formatNumber(well.flow_l_s, 2) })}`}
      </p>
      {last ? (
        <p className="note">
          {t("wells.readings", {
            count: readings.length,
            depth: formatNumber(last.depth_to_water_m, 2),
            date: formatDate(last.measured_at),
          })}
        </p>
      ) : (
        <p className="note">{t("wells.noReadings")}</p>
      )}
      <Reading
        record={record}
        onSaved={(notice) => {
          onChanged(notice, false);
        }}
      />
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

export function WellsPanel({ tapped, onChanged }: Props) {
  const [registry, setRegistry] = useState<Answer<Registry> | null>(null);
  const [form, setForm] = useState<WellForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [validation, setValidation] = useState<OwnerValidation | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let live = true;
    void fetchRegistry().then((answer) => {
      if (live) {
        setRegistry(answer);
      }
    });
    return () => {
      live = false;
    };
  }, [version]);

  function changed(next: Notice, mapChanged: boolean) {
    setNotice(next);
    setVersion((v) => v + 1);
    if (mapChanged) {
      onChanged();
    }
  }

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
      {registry && !registry.ok && (
        <p className="error" role="alert">
          {failureText(registry)}
        </p>
      )}
      {registry?.ok && (
        <>
          {registry.body.wells.length === 0 ? (
            <p className="note">{t("wells.empty")}</p>
          ) : (
            <ul className="well-list">
              {registry.body.wells.map((record) => (
                <WellItem
                  key={record.well.id}
                  record={record}
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
