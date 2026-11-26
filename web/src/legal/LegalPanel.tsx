// Copyright (c) 2026 Almoon-D. All rights reserved.
// A legal status (hard rule 2): the verdict, the water authority, the groundwater body and
// its status, the rules that could not be loaded and why, every rule evaluated with its
// source and dates, the other permits a well needs, and the disclaimer. The area's legal
// panel asks it at the area's centre, before anything else is computed.
import { useEffect, useState } from "react";
import { type AreaOfInterest, fetchLegal, type LegalResult, type LegalStatus } from "../api.ts";
import { formatDate, lookup, t, translated } from "../i18n/index.ts";
import { findingNotes, findingText, sortedFindings, sourceText } from "./legal.ts";

function Body({ status }: { status: LegalStatus }) {
  const { body } = status;
  if (!body) {
    return null;
  }
  const quantitative = body.quantitative_status ?? t("legal.unknown");
  const risk =
    body.declared_at_risk === null
      ? t("legal.riskUnknown")
      : body.declared_at_risk
        ? t("legal.declared", { declaration: body.declaration ?? "" })
        : t("legal.notDeclared");
  return (
    <p data-body={body.code}>
      {t("legal.body", { name: body.name, code: body.code, status: quantitative })} {risk}
    </p>
  );
}

export function LegalStatusView({ status }: { status: LegalStatus }) {
  if (status.state === "not_evaluated") {
    return (
      <div className="legal-status" data-legal={status.state}>
        <p className="verdict">{t("legal.state.not_evaluated")}</p>
        <p className="note">{t("detailed.disclaimer")}</p>
      </div>
    );
  }
  const { authority } = status;
  const findings = sortedFindings(status.findings);
  return (
    <div className="legal-status" data-legal={status.state}>
      <p className="verdict">{lookup(`legal.state.${status.state}`, status.state)}</p>
      {authority ? (
        <p data-district={authority.district}>
          {t("legal.authority", {
            name: authority.name,
            district: authority.district_name,
            code: authority.district,
          })}
          {authority.note && <span className="note"> {translated(authority.note)}</span>}
        </p>
      ) : null}
      <Body status={status} />
      {status.not_loaded.length > 0 && (
        <ul className="not-loaded">
          {status.not_loaded.map((n) => (
            <li key={`${n.scope}-${n.area ?? ""}`} data-scope={n.scope}>
              {t(`legal.notLoaded.${n.scope}`, { area: n.area ?? "" })} {translated(n.reason)}
            </li>
          ))}
        </ul>
      )}
      <details>
        <summary>{t("legal.rules", { count: findings.length })}</summary>
        <ul className="findings">
          {findings.map((f) => (
            <li key={f.rule_id} data-outcome={f.outcome} data-rule={f.rule_id}>
              <strong>{lookup(`legal.outcome.${f.outcome}`, f.outcome)}</strong> {translated(f.title)}.{" "}
              {findingText(f)}
              {findingNotes(f).map((note) => (
                <span key={note} className="note">
                  {" "}
                  {note}
                </span>
              ))}
              <br />
              <a className="note" href={f.source.url} target="_blank" rel="noreferrer">
                {sourceText(f)}
              </a>
            </li>
          ))}
        </ul>
      </details>
      {status.permits.length > 0 && (
        <ul className="permits">
          {status.permits.map((p) => (
            <li key={translated(p)}>{translated(p)}</li>
          ))}
        </ul>
      )}
      <p className="note">
        {t("legal.assessed", { date: formatDate(status.assessed_at) })} {t("detailed.disclaimer")}
      </p>
    </div>
  );
}

/** The area's legal panel: the rules at its centre, asked when the area is selected. */
export function LegalPanel({ area }: { area: AreaOfInterest }) {
  const [lon, lat] = area.centre;
  const region = area.region_code;
  const key = `${String(lon)},${String(lat)},${region}`;
  // The last answer, with the place it answers: another place's is still loading.
  const [answer, setAnswer] = useState<{ key: string; result: LegalResult } | null>(null);
  useEffect(() => {
    let current = true;
    void fetchLegal(lon, lat, region).then((result) => {
      if (current) {
        setAnswer({ key, result });
      }
    });
    return () => {
      current = false;
    };
  }, [key, lon, lat, region]);
  const view = answer?.key === key ? answer.result : null;
  return (
    <section className="legal-panel" aria-live="polite">
      <h2>{t("legal.heading")}</h2>
      <p className="note">{t("legal.centreNote")}</p>
      {view === null ? (
        <p className="note">{t("legal.loading")}</p>
      ) : view.ok ? (
        <LegalStatusView status={view.status} />
      ) : (
        <p className="error" role="alert" data-failure={view.failure}>
          {t(`legal.error.${view.failure}`)}
        </p>
      )}
    </section>
  );
}
