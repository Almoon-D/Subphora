// Copyright (c) 2026 Almoon-D. All rights reserved.
// What the switched-on layers hold at the tapped point, each with its source and date.
import type { FeatureInfo, InfoResult } from "../api.ts";
import { formatDate, lookup, t } from "../i18n/index.ts";
import { describeDetail } from "./LayerPanel.tsx";

/** Idle: no tap yet (the panel is not shown); nothing: a tap with no layer to ask. */
export type Tap =
  | { state: "idle" }
  | { state: "nothing" }
  | { state: "loading" }
  | { state: "done"; results: InfoResult[] };

function Value({ value }: { value: string }) {
  if (value.startsWith("https://")) {
    return (
      <a href={value} target="_blank" rel="noopener noreferrer">
        {value}
      </a>
    );
  }
  return <>{value}</>;
}

/** Which layer answered, at what scale and of what date, and the regional ones that did not. */
function AnsweredBy({ info }: { info: FeatureInfo }) {
  const answer = info.answered_by;
  const who =
    answer.level === "regional"
      ? t("info.answeredRegional", {
          publisher: answer.publisher,
          area: lookup(`area.${answer.area_id ?? ""}`, answer.area_id ?? ""),
          detail: describeDetail(answer.detail),
        })
      : t("info.answeredNational", { publisher: answer.publisher, detail: describeDetail(answer.detail) });
  return (
    <>
      <p className="note answered" data-answered={answer.layer_id}>
        {who}
      </p>
      {info.fallbacks.map((fallback) => (
        <p key={fallback.layer_id} className="note" data-fallback={fallback.reason}>
          {t(`info.fallback.${fallback.reason}`, { title: lookup(`layer.${fallback.layer_id}`, fallback.layer_id) })}
        </p>
      ))}
    </>
  );
}

function Result({ result }: { result: InfoResult }) {
  const title = lookup(`layer.${result.layerId}`, result.layerId);
  if (!result.ok) {
    return (
      <li className="info-layer">
        <h3>{title}</h3>
        <p className="error">{t(`info.error.${result.failure}`)}</p>
      </li>
    );
  }
  const { info } = result;
  return (
    <li className="info-layer">
      <h3>{title}</h3>
      {info.features.length === 0 && <p className="note">{t("info.empty")}</p>}
      {info.features.map((feature, index) => (
        <dl key={index}>
          {feature.fields.map((field) => (
            <div key={field.name}>
              <dt>{lookup(`field.${field.name}`, field.name)}</dt>
              <dd>
                <Value value={field.value} />
              </dd>
            </div>
          ))}
        </dl>
      ))}
      <AnsweredBy info={info} />
      <p className="note">
        {t("info.source", { attribution: info.source.attribution, date: formatDate(info.source.retrieved_at) })}
      </p>
    </li>
  );
}

export function InfoPanel({ tap }: { tap: Tap }) {
  if (tap.state === "idle") {
    return null;
  }
  return (
    <section className="info" aria-labelledby="info-heading" aria-live="polite">
      <h2 id="info-heading">{t("info.heading")}</h2>
      {tap.state === "nothing" && <p className="note">{t("info.none")}</p>}
      {tap.state === "loading" && <p>{t("info.loading")}</p>}
      {tap.state === "done" && (
        <ul>
          {tap.results.map((result) => (
            <Result key={result.layerId} result={result} />
          ))}
        </ul>
      )}
    </section>
  );
}
