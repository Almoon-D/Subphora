// Copyright (c) 2026 Almoon-D. All rights reserved.
// The selected area's detailed map: the button that asks for it, its job while it runs or
// why it failed, then its mean index and confidence, its layers with their legends, and its
// ranked candidate spots, each with its explanation and legal status.
import type { AreaAnalysis, Candidate, ParcelFailure, ParcelLayer } from "../api.ts";
import { formatArea, formatDate, formatNumber, lookup, t } from "../i18n/index.ts";
import { ConfidenceBreakdown, EstimateSources, Inputs, Missing, ScoreWithConfidence } from "../map/Explanation.tsx";
import { legendText, percent } from "../map/national.ts";
import type { ParcelView } from "./parcel.ts";

interface Props {
  view: ParcelView | undefined;
  layer: string | null;
  onStart: () => void;
  onLayer: (id: string | null) => void;
}

/** The area's mean index with its mean confidence, or why it has none. */
export function MeanScore({ analysis }: { analysis: AreaAnalysis }) {
  const { summary } = analysis;
  if (summary.mean_index === null || summary.mean_confidence === null) {
    return <p className="note">{t("detailed.noScore")}</p>;
  }
  return <ScoreWithConfidence estimate={{ score: summary.mean_index, confidence: summary.mean_confidence }} />;
}

function Summary({ analysis }: { analysis: AreaAnalysis }) {
  const { summary } = analysis;
  const partial = summary.contributions.filter((c) => c.present_share < 1);
  const attribution = [...new Set(Object.values(analysis.sources).map((s) => s.attribution))].join("; ");
  return (
    <>
      <h3>{t("detailed.summaryHeading")}</h3>
      <MeanScore analysis={analysis} />
      <p className="note">{t("national.kindNote")}</p>
      <p className="note">
        {t("detailed.cells", {
          cells: formatNumber(summary.cells),
          cell: analysis.cell_m,
          area: formatArea(analysis.area_m2),
        })}
      </p>
      {summary.missing.length > 0 && (
        <ul className="missing">
          {summary.missing.map((m) => (
            <li key={m.criterion} data-missing={m.reason}>
              {t(`explain.missing.${m.reason}`, {
                title: lookup(`criterion.${m.criterion}`, m.criterion),
                weight: percent(m.weight),
              })}
            </li>
          ))}
        </ul>
      )}
      {partial.length > 0 && (
        <ul className="missing">
          {partial.map((c) => (
            <li key={c.criterion} data-partial={c.criterion}>
              {t("detailed.partial", {
                title: lookup(`criterion.${c.criterion}`, c.criterion),
                share: percent(c.present_share),
              })}
            </li>
          ))}
        </ul>
      )}
      <p className="note">{lookup(`detailed.terrain.${analysis.terrain_model}`, analysis.terrain_model)}</p>
      <p className="note source">{t("national.source", { attribution })}</p>
    </>
  );
}

function Layers({
  layers,
  layer,
  onLayer,
}: {
  layers: ParcelLayer[];
  layer: string | null;
  onLayer: (id: string | null) => void;
}) {
  const shown = layers.find((l) => l.id === layer);
  return (
    <fieldset className="parcel-layers">
      <legend>{t("detailed.layersHeading")}</legend>
      {[...layers.map((l) => l.id), null].map((id) => (
        <label key={id ?? "none"} className="toggle" data-parcel-layer={id ?? "none"}>
          <input
            type="radio"
            name="parcel-layer"
            checked={layer === id}
            onChange={() => {
              onLayer(id);
            }}
          />
          {id === null ? t("detailed.noLayer") : lookup(`layer.${id}`, id)}
        </label>
      ))}
      {shown && (
        <div className="national-legend" data-legend={`parcel-${shown.id}`}>
          <p className="note">{lookup(`national.unit.${shown.unit}`, shown.unit)}</p>
          <ul>
            {shown.legend.map((item) => (
              <li key={item.colour}>
                <span className="swatch" style={{ background: item.colour }} aria-hidden="true" />
                {legendText(item, shown.unit)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </fieldset>
  );
}

function CandidateItem({ candidate }: { candidate: Candidate }) {
  const { local, estimate, legal } = candidate;
  return (
    <li className="candidate" data-rank={candidate.rank}>
      <h4>{t("detailed.candidate", { rank: candidate.rank })}</h4>
      <ScoreWithConfidence estimate={estimate} />
      <p className="note">
        {t("detailed.candidatePosition", {
          crs: local.crs,
          x: formatNumber(local.x),
          y: formatNumber(local.y),
          lat: formatNumber(candidate.latitude, 5),
          lon: formatNumber(candidate.longitude, 5),
        })}
      </p>
      <p className="legal" data-legal={legal.state}>
        {lookup(`detailed.legal.${legal.state}`, legal.state)} {t("detailed.disclaimer")}
      </p>
      <p className="note" data-depth={candidate.depth}>
        {t("detailed.depthNotEstimated")}
      </p>
      <details>
        <summary>{t("detailed.why")}</summary>
        <Inputs estimate={estimate} />
        <Missing estimate={estimate} />
        <ConfidenceBreakdown confidence={estimate.confidence} />
        <EstimateSources estimate={estimate} />
      </details>
    </li>
  );
}

function Candidates({ analysis }: { analysis: AreaAnalysis }) {
  return (
    <>
      <h3>{t("detailed.candidatesHeading")}</h3>
      {analysis.no_candidates ? (
        <p className="note" data-no-candidates={analysis.no_candidates}>
          {t(`detailed.noCandidates.${analysis.no_candidates}`)}
        </p>
      ) : (
        <>
          <p className="note">{t("detailed.candidatesHint")}</p>
          <ol className="candidates">
            {analysis.candidates.map((c) => (
              <CandidateItem key={c.rank} candidate={c} />
            ))}
          </ol>
        </>
      )}
    </>
  );
}

function Failure({ failure, onStart }: { failure: ParcelFailure; onStart: () => void }) {
  return (
    <>
      <p className="error" role="alert" data-failure={failure}>
        {lookup(`detailed.error.${failure}`, t("detailed.error.unexpected"))}
      </p>
      <button type="button" onClick={onStart}>
        {t("detailed.start")}
      </button>
    </>
  );
}

function Body({ view, layer, onStart, onLayer }: Props) {
  if (!view) {
    return (
      <>
        <p className="note">{t("detailed.intro")}</p>
        <button type="button" onClick={onStart}>
          {t("detailed.start")}
        </button>
      </>
    );
  }
  if (view.state === "asking") {
    return <p>{t("detailed.asking")}</p>;
  }
  if (view.state === "failed") {
    return <Failure failure={view.failure} onStart={onStart} />;
  }
  const { job, layers } = view.answer;
  if (job.state === "failed") {
    return <Failure failure={job.failure ?? "unexpected"} onStart={onStart} />;
  }
  if (job.analysis === null) {
    return <p aria-busy="true">{t(job.state === "queued" ? "detailed.job.queued" : "detailed.job.running")}</p>;
  }
  return (
    <>
      <Summary analysis={job.analysis} />
      <Layers layers={layers} layer={layer} onLayer={onLayer} />
      <Candidates analysis={job.analysis} />
      <p className="note">{t("detailed.built", { date: formatDate(job.analysis.built_at) })}</p>
    </>
  );
}

export function ParcelPanel(props: Props) {
  const { view } = props;
  const state = view?.state === "answered" ? view.answer.job.state : (view?.state ?? "idle");
  return (
    <section className="parcel" aria-labelledby="parcel-heading" aria-live="polite" data-state={state}>
      <h2 id="parcel-heading">{t("detailed.heading")}</h2>
      <Body {...props} />
    </section>
  );
}
