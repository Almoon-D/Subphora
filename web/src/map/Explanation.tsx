// Copyright (c) 2026 Almoon-D. All rights reserved.
// The national map's answer at a tapped point: the index with its confidence, what forms it
// (each input's value, suitability, weight, contribution and source), the inputs missing
// there, and what the confidence depends on.
import type { CellExplanation, Confidence, ExplainResult, ParcelExplainResult, PotentialEstimate } from "../api.ts";
import { formatDate, formatNumber, lookup, t } from "../i18n/index.ts";
import { describeDetail } from "./LayerPanel.tsx";
import { percent, valueText } from "./national.ts";

const score = (value: number) => formatNumber(value, 2);

/** The only way the page shows a score: always with its confidence beside it, and named an
 * index (hard rule 1). */
export function ScoreWithConfidence({ estimate }: { estimate: Pick<PotentialEstimate, "score" | "confidence"> }) {
  const confidence: Confidence = estimate.confidence;
  return (
    <p className="score" data-score={estimate.score ?? ""} data-confidence={confidence.label}>
      <strong>{estimate.score === null ? t("explain.noIndex") : t("explain.index", { value: score(estimate.score) })}</strong>
      {" · "}
      <span className={`confidence confidence-${confidence.label}`}>
        {t("explain.confidence", { label: t(`explain.confidence.${confidence.label}`), value: score(confidence.value) })}
      </span>
    </p>
  );
}

export function Inputs({ estimate }: { estimate: PotentialEstimate }) {
  if (estimate.contributions.length === 0) {
    return null;
  }
  return (
    <table className="inputs">
      <caption>{t("explain.inputs")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("explain.column.criterion")}</th>
          <th scope="col">{t("explain.column.suitability")}</th>
          <th scope="col">{t("explain.column.share")}</th>
          <th scope="col">{t("explain.column.contribution")}</th>
        </tr>
      </thead>
      <tbody>
        {estimate.contributions.map((c) => (
          <tr key={c.criterion} data-criterion={c.criterion}>
            <th scope="row">
              {lookup(`criterion.${c.criterion}`, c.criterion)}
              <span className="value">{valueText(c.value)}</span>
            </th>
            <td>{score(c.suitability)}</td>
            <td>{percent(c.share)}</td>
            <td>{score(c.contribution)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Missing({ estimate }: { estimate: PotentialEstimate }) {
  if (estimate.missing.length === 0) {
    return null;
  }
  return (
    <>
      <h4>{t("explain.missing")}</h4>
      <ul className="missing">
        {estimate.missing.map((m) => (
          <li key={m.criterion} data-missing={m.reason}>
            {t(`explain.missing.${m.reason}`, {
              title: lookup(`criterion.${m.criterion}`, m.criterion),
              weight: percent(m.weight),
            })}
          </li>
        ))}
      </ul>
    </>
  );
}

export function ConfidenceBreakdown({ confidence }: { confidence: Confidence }) {
  return (
    <>
      <h4>{t("explain.confidenceHeading")}</h4>
      <ul className="components">
        {confidence.components.map((c) => {
          const params = { title: lookup(`component.${c.id}`, c.id), weight: percent(c.weight) };
          return (
            <li key={c.id} data-component={c.id}>
              {c.measured ? t("explain.component", { ...params, value: score(c.value) }) : t("explain.notMeasured", params)}
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function EstimateSources({ estimate }: { estimate: PotentialEstimate }) {
  if (estimate.contributions.length === 0) {
    return null;
  }
  return (
    <details className="sources">
      <summary>{t("explain.sources")}</summary>
      <ul className="note">
        {estimate.contributions.map((c) => (
          <li key={c.criterion}>
            {t("explain.source", {
              title: lookup(`criterion.${c.criterion}`, c.criterion),
              attribution: c.source.attribution,
              detail: describeDetail(c.source.detail),
              date: formatDate(c.source.retrieved_at),
            })}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Explained({ explanation }: { explanation: CellExplanation }) {
  const { estimate } = explanation;
  return (
    <>
      <ScoreWithConfidence estimate={estimate} />
      <p className="note">{t("national.kindNote")}</p>
      <Inputs estimate={estimate} />
      <Missing estimate={estimate} />
      <ConfidenceBreakdown confidence={estimate.confidence} />
      <EstimateSources estimate={estimate} />
      <p className="note">
        {t("explain.cell", {
          cell: explanation.cell_m,
          region: explanation.region_name,
          date: formatDate(explanation.built_at),
        })}
      </p>
    </>
  );
}

export function NationalExplanation({ result }: { result: ExplainResult }) {
  return (
    <li className="info-layer national-explanation">
      <h3>{t("explain.heading")}</h3>
      {result.ok ? (
        <Explained explanation={result.explanation} />
      ) : (
        <p className="error">{t(`explain.error.${result.failure}`)}</p>
      )}
    </li>
  );
}

/** The detailed map's answer at a tapped point inside its area. */
export function ParcelExplanationView({ result }: { result: ParcelExplainResult }) {
  if (!result.ok) {
    return (
      <li className="info-layer parcel-explanation">
        <h3>{t("detailed.explainHeading")}</h3>
        <p className="error">{lookup(`detailed.error.${result.failure}`, t("detailed.error.unexpected"))}</p>
      </li>
    );
  }
  const { explanation } = result;
  const { estimate } = explanation;
  return (
    <li className="info-layer parcel-explanation">
      <h3>{t("detailed.explainHeading")}</h3>
      <ScoreWithConfidence estimate={estimate} />
      <p className="note">{t("national.kindNote")}</p>
      <Inputs estimate={estimate} />
      <Missing estimate={estimate} />
      <ConfidenceBreakdown confidence={estimate.confidence} />
      <EstimateSources estimate={estimate} />
      <p className="note">{t("detailed.cell", { cell: explanation.cell_m, date: formatDate(explanation.built_at) })}</p>
    </li>
  );
}
