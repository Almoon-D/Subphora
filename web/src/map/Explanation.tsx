// Copyright (c) 2026 Almoon-D. All rights reserved.
// The national map's answer at a tapped point: the index with its confidence, what forms it
// (each input's value, suitability, weight, contribution and source), the inputs missing
// there, what the confidence depends on, and how well the model did against known wells in
// that hydrogeological domain.
import type {
  CellExplanation,
  Confidence,
  DomainValidation,
  ExplainResult,
  ParcelExplainResult,
  PotentialEstimate,
  WellUpdate,
} from "../api.ts";
import { formatDate, formatNumber, lookup, t } from "../i18n/index.ts";
import { DepthHere } from "../parcel/Depth.tsx";
import { describeDetail } from "./LayerPanel.tsx";
import { percent, valueText } from "./national.ts";

const score = (value: number) => formatNumber(value, 2);

/** The only way the page shows a score: always with its confidence beside it, and named an
 * index (hard rule 1); a probability only where the domain is calibrated, with its interval. */
export function ScoreWithConfidence({
  estimate,
}: {
  estimate: Pick<PotentialEstimate, "score" | "confidence"> & Partial<Pick<PotentialEstimate, "probability">>;
}) {
  const confidence: Confidence = estimate.confidence;
  const { probability } = estimate;
  return (
    <p className="score" data-score={estimate.score ?? ""} data-confidence={confidence.label}>
      <strong>{estimate.score === null ? t("explain.noIndex") : t("explain.index", { value: score(estimate.score) })}</strong>
      {" · "}
      <span className={`confidence confidence-${confidence.label}`}>
        {t("explain.confidence", { label: t(`explain.confidence.${confidence.label}`), value: score(confidence.value) })}
      </span>
      {probability && (
        <>
          {" · "}
          <span className="probability" data-probability={probability.value}>
            {t("explain.probability", {
              value: percent(probability.value),
              low: percent(probability.low),
              high: percent(probability.high),
            })}
          </span>
        </>
      )}
    </p>
  );
}

/** How well the model discriminates known wells in a domain: measured, "no better than
 * chance here", too few wells, or not validated, always said. */
export function ValidationNote({ validation }: { validation: DomainValidation }) {
  const { auc } = validation;
  const params = {
    label: validation.label,
    productive: validation.productive,
    value: auc ? score(auc.value) : "",
    low: auc ? score(auc.low) : "",
    high: auc ? score(auc.high) : "",
    reason: validation.labels_source,
  };
  const measured = validation.state === "validated" || validation.state === "no_better_than_chance";
  return (
    <div className={`validation validation-${validation.state}`} data-validation={validation.state} data-domain={validation.domain}>
      <p>{t(`validation.${validation.state}`, params)}</p>
      {measured && (
        <p className="note">
          {t("validation.counts", { productive: validation.productive, blocks: validation.blocks })}{" "}
          {validation.design &&
            t(`validation.design.${validation.design}`, {
              productive: validation.productive,
              dry: validation.dry,
              background: validation.background,
            })}{" "}
          {validation.calibration && t("validation.calibrated")}
        </p>
      )}
      {validation.trials.map((trial) => (
        <p className="note" key={trial.criterion} data-trial={trial.criterion} data-outcome={trial.outcome}>
          {t(`validation.trial.${trial.outcome}`, {
            title: lookup(`criterion.${trial.criterion}`, trial.criterion),
            without: trial.auc_without ? score(trial.auc_without.value) : "",
            with: trial.auc_with ? score(trial.auc_with.value) : "",
            low: trial.gain_low === null ? "" : score(trial.gain_low),
            high: trial.gain_high === null ? "" : score(trial.gain_high),
          })}
        </p>
      ))}
    </div>
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
      <ValidationNote validation={estimate.validation} />
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
/** The value updated with the owner's wells beside the map's own, with the estimate's
 * confidence next to it, and the wells that moved it (decision 0040). */
export function UpdatedWithWells({ update, confidence }: { update: WellUpdate; confidence: Confidence }) {
  const values = {
    value: score(update.value),
    low: score(update.low),
    high: score(update.high),
    prior: score(update.prior),
  };
  return (
    <div className="updated-with-wells" data-updated={update.value} data-wells={update.evidence.length}>
      <p>
        <strong>
          {update.kind === "probability"
            ? t("explain.updated.probability", {
                ...values,
                value: percent(update.value),
                low: percent(update.low),
                high: percent(update.high),
                prior: percent(update.prior),
              })
            : t("explain.updated.index", values)}
        </strong>
        {" · "}
        <span className={`confidence confidence-${confidence.label}`}>
          {t("explain.confidence", { label: t(`explain.confidence.${confidence.label}`), value: score(confidence.value) })}
        </span>
      </p>
      <p className="note">
        {update.evidence.length === 0
          ? t("explain.updated.none", { range: formatNumber(update.range_m) })
          : t("explain.updated.wells", {
              count: update.evidence.length,
              list: update.evidence
                .map((e) =>
                  t("explain.updated.well", {
                    outcome: t(`wells.outcome.${e.outcome}`),
                    distance: formatNumber(e.distance_m),
                    weight: score(e.weight),
                  }),
                )
                .join("; "),
            })}
      </p>
      <p className="note">
        {t("explain.updated.note", {
          half: formatNumber(update.half_weight_m),
          range: formatNumber(update.range_m),
          strength: formatNumber(update.prior_strength, 1),
        })}
      </p>
    </div>
  );
}

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
      {explanation.updated && <UpdatedWithWells update={explanation.updated} confidence={estimate.confidence} />}
      {explanation.depth && <DepthHere depth={explanation.depth} />}
      <p className="note">{t("national.kindNote")}</p>
      <Inputs estimate={estimate} />
      <Missing estimate={estimate} />
      <ConfidenceBreakdown confidence={estimate.confidence} />
      <ValidationNote validation={estimate.validation} />
      <EstimateSources estimate={estimate} />
      <p className="note">{t("detailed.cell", { cell: explanation.cell_m, date: formatDate(explanation.built_at) })}</p>
    </li>
  );
}
