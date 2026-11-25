// Copyright (c) 2026 Almoon-D. All rights reserved.
// The areas of the session side by side, once at least two have their detailed map: size,
// mean index and confidence, and the best candidate spots, every score with its confidence.
import type { AreaAnalysis, AreaOfInterest } from "../api.ts";
import { formatArea, t } from "../i18n/index.ts";
import { ScoreWithConfidence } from "../map/Explanation.tsx";
import { areaHeading, areaKey } from "../search/areas.ts";
import { MeanScore } from "./ParcelPanel.tsx";

// Candidates per row: enough to compare areas; the area's own panel lists them all.
const BEST_SHOWN = 3;

interface Props {
  rows: { area: AreaOfInterest; analysis: AreaAnalysis }[];
}

export function Comparison({ rows }: Props) {
  if (rows.length < 2) {
    return null;
  }
  return (
    <section className="comparison" aria-labelledby="comparison-heading">
      <h2 id="comparison-heading">{t("compare.heading")}</h2>
      <table>
        <thead>
          <tr>
            <th scope="col">{t("compare.area")}</th>
            <th scope="col">{t("compare.mean")}</th>
            <th scope="col">{t("compare.best")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ area, analysis }) => (
            <tr key={areaKey(area)} data-compare={analysis.id}>
              <th scope="row">
                {areaHeading(area)}
                <span className="value">{formatArea(analysis.area_m2)}</span>
              </th>
              <td>
                <MeanScore analysis={analysis} />
              </td>
              <td>
                {analysis.candidates.length === 0 ? (
                  <p className="note">{t(`detailed.noCandidates.${analysis.no_candidates ?? "no_score"}`)}</p>
                ) : (
                  analysis.candidates
                    .slice(0, BEST_SHOWN)
                    .map((c) => <ScoreWithConfidence key={c.rank} estimate={c.estimate} />)
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">{t("national.kindNote")}</p>
    </section>
  );
}
