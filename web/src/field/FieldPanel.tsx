// Copyright (c) 2026 Almoon-D. All rights reserved.
// Field mode's panel (MASTER_PLAN §4.7): large, high-contrast controls for use outdoors
// and with gloves. The position with its accuracy and heading; the spot being walked to,
// its distance and direction, and "at the spot" by the configured rule; notes, photos,
// voice memos and the track, each confirmed only once kept on the device; and the outbox,
// with its unsent count, a sync on demand and the export of everything unsent.
import { useEffect, useRef, useState } from "react";

import type { AreaAnalysis, FieldConfig } from "../api.ts";
import { formatNumber, t } from "../i18n/index.ts";
import { isBlocked } from "../legal/legal.ts";
import type { FieldDb } from "./db.ts";
import { download, unsyncedExport } from "./export.ts";
import { atSpot, compassPoint, leg } from "./geodesy.ts";
import type { Located } from "./hooks.ts";
import type { OutboxView } from "./hooks.ts";
import {
  type Fix,
  fixPosition,
  mediaProblem,
  nextTrackPoint,
  note,
  type Observation,
  type Target,
  trackPoint,
  uuidv7,
  withMedia,
} from "./records.ts";

type Notice = { kind: "saved"; key: "note" | "photo" | "voice" } | { kind: "error"; message: string } | null;

function Position({ located }: { located: Located }) {
  const { fix, problem } = located;
  return (
    <section className="field-block" aria-labelledby="field-position">
      <h2 id="field-position">{t("field.position")}</h2>
      {fix ? (
        <>
          <p className="field-big" data-accuracy={fix.accuracy_m}>
            {t("field.accuracy", { metres: formatNumber(fix.accuracy_m) })}
          </p>
          <p>
            {fix.heading_deg === null
              ? t("field.noHeading")
              : t("field.heading", {
                  degrees: formatNumber(fix.heading_deg),
                  point: t(`compass.${compassPoint(fix.heading_deg)}`),
                })}
          </p>
        </>
      ) : (
        !problem && <p className="field-big">{t("field.waiting")}</p>
      )}
      {problem && (
        <p className={fix ? "note" : "error"} role="alert">
          {t(`field.problem.${problem}`)}
        </p>
      )}
    </section>
  );
}

function Guidance({ fix, target, atSpotM }: { fix: Fix | null; target: Target; atSpotM: number }) {
  if (!fix) {
    return <p className="note">{t("field.guidanceWaiting")}</p>;
  }
  const { distance_m, bearing_deg } = leg(fixPosition(fix), [target.longitude, target.latitude]);
  const there = atSpot(distance_m, fix.accuracy_m, atSpotM);
  return (
    <div className="guidance" data-at-spot={there} data-distance={Math.round(distance_m)}>
      {there ? (
        <p className="at-spot" role="status">
          {t("field.atSpot")}
        </p>
      ) : (
        <>
          <p className="field-big">
            <span className="arrow" aria-hidden="true" style={{ transform: `rotate(${String(bearing_deg)}deg)` }}>
              ↑
            </span>{" "}
            {t("field.distance", { metres: formatNumber(distance_m) })}
          </p>
          <p>
            {t("field.bearing", {
              degrees: formatNumber(bearing_deg),
              point: t(`compass.${compassPoint(bearing_deg)}`),
            })}
          </p>
        </>
      )}
      {fix.accuracy_m > atSpotM && (
        <p className="note">{t("field.accuracyTooLow", { accuracy: formatNumber(fix.accuracy_m), needed: formatNumber(atSpotM) })}</p>
      )}
    </div>
  );
}

function TargetBlock({
  analysis,
  target,
  fix,
  atSpotM,
  onTarget,
}: {
  analysis: AreaAnalysis | null;
  target: Target | null;
  fix: Fix | null;
  atSpotM: number;
  onTarget: (target: Target | null) => void;
}) {
  const candidates = analysis?.candidates ?? [];
  return (
    <section className="field-block" aria-labelledby="field-target">
      <h2 id="field-target">{target ? t("field.targetHeading", { rank: target.rank }) : t("field.noTarget")}</h2>
      {target && <Guidance fix={fix} target={target} atSpotM={atSpotM} />}
      {analysis && candidates.length > 0 ? (
        <div className="field-row" role="group" aria-label={t("field.choose")}>
          {candidates.map((candidate) => (
            <button
              key={candidate.rank}
              type="button"
              className="field-button secondary"
              aria-pressed={target?.area_id === analysis.id && target.rank === candidate.rank}
              onClick={() => {
                onTarget({
                  area_id: analysis.id,
                  rank: candidate.rank,
                  longitude: candidate.longitude,
                  latitude: candidate.latitude,
                });
              }}
            >
              {t("field.goTo", { rank: candidate.rank })}
              {isBlocked(candidate.legal) && ` · ${t("detailed.blocked")}`}
            </button>
          ))}
        </div>
      ) : (
        !target && <p className="note">{t("field.noCandidates")}</p>
      )}
      {target && (
        <button
          type="button"
          className="field-button secondary"
          onClick={() => {
            onTarget(null);
          }}
        >
          {t("field.clearTarget")}
        </button>
      )}
    </section>
  );
}

/** A voice memo with the microphone where the browser records; otherwise the device's own
 * recorder through a file input. */
function useVoice(onRecorded: (bytes: ArrayBuffer, type: string) => void, onFailed: () => void) {
  const recorder = useRef<MediaRecorder | null>(null);
  const [recording, setRecording] = useState(false);
  // The microphone is offered only on a secure origin (HTTPS or localhost).
  const canRecord = typeof MediaRecorder !== "undefined" && "mediaDevices" in navigator && "getUserMedia" in navigator.mediaDevices;
  async function start() {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onFailed();
      return;
    }
    const chunks: Blob[] = [];
    const media = new MediaRecorder(stream);
    media.ondataavailable = (event) => {
      chunks.push(event.data);
    };
    media.onstop = () => {
      for (const track of stream.getTracks()) {
        track.stop();
      }
      const blob = new Blob(chunks, { type: media.mimeType });
      void blob.arrayBuffer().then((bytes) => {
        onRecorded(bytes, media.mimeType);
      });
    };
    recorder.current = media;
    media.start();
    setRecording(true);
  }
  function stop() {
    recorder.current?.stop();
    recorder.current = null;
    setRecording(false);
  }
  return { canRecord, recording, start, stop };
}

function Outbox({ outbox, onExport }: { outbox: OutboxView; onExport: () => void }) {
  const { unsynced, refused, syncing, last } = outbox;
  let state: string;
  if (syncing) {
    state = t("field.syncing");
  } else if (unsynced === 0) {
    state = t("field.allSynced");
  } else if (last === "offline") {
    state = t("field.offline");
  } else if (last === "server_error") {
    state = t("field.serverError");
  } else {
    state = t("field.waitingToSync");
  }
  return (
    <section className="field-block outbox" aria-labelledby="field-outbox" data-unsynced={unsynced} data-refused={refused}>
      <h2 id="field-outbox">{t("field.unsynced", { count: unsynced })}</h2>
      <p aria-live="polite">{state}</p>
      {refused > 0 && <p className="error">{t("field.refused", { count: refused })}</p>}
      <div className="field-row">
        <button type="button" className="field-button" disabled={syncing || unsynced === refused} onClick={outbox.sync}>
          {t("field.syncNow")}
        </button>
        <button type="button" className="field-button secondary" disabled={unsynced === 0} onClick={onExport}>
          {t("field.export")}
        </button>
      </div>
    </section>
  );
}

export function FieldPanel({
  config,
  db,
  outbox,
  located,
  analysis,
  target,
  follow,
  onTarget,
  onFollow,
  onExit,
}: {
  config: FieldConfig;
  /** Null: the device's store could not be opened; nothing can be recorded. */
  db: FieldDb | null;
  outbox: OutboxView;
  located: Located;
  analysis: AreaAnalysis | null;
  target: Target | null;
  follow: boolean;
  onTarget: (target: Target | null) => void;
  onFollow: (follow: boolean) => void;
  onExit: () => void;
}) {
  const [writing, setWriting] = useState<string | null>(null);
  const [caption, setCaption] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [track, setTrack] = useState<{ id: string; points: number } | null>(null);
  const fix = located.fix;

  async function keep(observation: Observation, media: { type: string; bytes: ArrayBuffer } | null, key: "note" | "photo" | "voice" | null) {
    if (!db) {
      return false;
    }
    try {
      await db.record(observation, media);
    } catch {
      setNotice({ kind: "error", message: t("field.notSaved") });
      return false;
    }
    if (key) {
      setNotice({ kind: "saved", key });
    }
    outbox.refresh();
    outbox.sync();
    return true;
  }

  async function keepFile(kind: "photo" | "voice", bytes: ArrayBuffer, type: string) {
    const problem = mediaProblem(type, bytes.byteLength, config.media_types, config.media_max_bytes);
    if (problem) {
      setNotice({
        kind: "error",
        message: t(`field.mediaProblem.${problem}`, { max: formatNumber(config.media_max_bytes / 1_048_576) }),
      });
      return;
    }
    const text = caption.trim() || null;
    const observation = await withMedia(kind, bytes, type, text, { position: fix, target });
    if (await keep(observation, { type: observation.media?.content_type ?? type, bytes }, kind)) {
      setCaption("");
    }
  }

  const voice = useVoice(
    (bytes, type) => {
      void keepFile("voice", bytes, type);
    },
    () => {
      setNotice({ kind: "error", message: t("field.noMicrophone") });
    },
  );

  // Each fix that moves the track on becomes its next point, kept before it is counted.
  // The refs hold the fix last looked at and the track's last point, so that a render
  // in between never records a fix twice.
  const seen = useRef<Fix | null>(null);
  const lastPoint = useRef<Fix | null>(null);
  const trackId = track?.id ?? null;
  const refresh = outbox.refresh;
  useEffect(() => {
    if (!trackId || !fix || !db || fix === seen.current) {
      return;
    }
    seen.current = fix;
    if (!nextTrackPoint(lastPoint.current, fix, config.track_min_interval_s, config.track_min_distance_m)) {
      return;
    }
    const previous = lastPoint.current;
    lastPoint.current = fix;
    void db.record(trackPoint(trackId, fix, { target })).then(
      () => {
        setTrack((current) => (current?.id === trackId ? { ...current, points: current.points + 1 } : current));
        refresh();
      },
      () => {
        lastPoint.current = previous;
        setNotice({ kind: "error", message: t("field.notSaved") });
      },
    );
  }, [trackId, fix, db, target, config.track_min_interval_s, config.track_min_distance_m, refresh]);

  async function onExport() {
    if (db) {
      download(await unsyncedExport(db));
    }
  }

  const disabled = db === null;
  return (
    <div className="field-mode">
      <div className="field-row field-header">
        <h1>{t("field.title")}</h1>
        <button type="button" className="field-button secondary" onClick={onExit}>
          {t("field.exit")}
        </button>
      </div>
      {disabled && (
        <p className="error" role="alert">
          {t("field.noStore")}
        </p>
      )}
      <Position located={located} />
      <button
        type="button"
        className="field-button secondary"
        aria-pressed={follow}
        onClick={() => {
          onFollow(!follow);
        }}
      >
        {t("field.follow")}
      </button>
      <TargetBlock analysis={analysis} target={target} fix={fix} atSpotM={config.at_spot_m} onTarget={onTarget} />
      <section className="field-block" aria-labelledby="field-record">
        <h2 id="field-record">{t("field.record")}</h2>
        {notice && (
          <p className={notice.kind === "error" ? "error" : "saved"} role={notice.kind === "error" ? "alert" : "status"}>
            {notice.kind === "saved" ? t(`field.saved.${notice.key}`) : notice.message}
          </p>
        )}
        {writing === null ? (
          <div className="field-grid">
            <button
              type="button"
              className="field-button"
              disabled={disabled}
              onClick={() => {
                setNotice(null);
                setWriting("");
              }}
            >
              {t("field.note")}
            </button>
            <label className={disabled ? "field-button disabled" : "field-button"}>
              {t("field.photo")}
              <input
                type="file"
                accept={config.media_types.filter((type) => type.startsWith("image/")).join(",")}
                capture="environment"
                disabled={disabled}
                className="visually-hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) {
                    void file.arrayBuffer().then((bytes) => keepFile("photo", bytes, file.type));
                  }
                }}
              />
            </label>
            {voice.canRecord ? (
              <button
                type="button"
                className={voice.recording ? "field-button recording" : "field-button"}
                disabled={disabled}
                aria-pressed={voice.recording}
                onClick={() => {
                  setNotice(null);
                  if (voice.recording) {
                    voice.stop();
                  } else {
                    void voice.start();
                  }
                }}
              >
                {voice.recording ? t("field.voiceStop") : t("field.voice")}
              </button>
            ) : (
              <label className={disabled ? "field-button disabled" : "field-button"}>
                {t("field.voice")}
                <input
                  type="file"
                  accept="audio/*"
                  capture
                  disabled={disabled}
                  className="visually-hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.target.value = "";
                    if (file) {
                      void file.arrayBuffer().then((bytes) => keepFile("voice", bytes, file.type));
                    }
                  }}
                />
              </label>
            )}
            <button
              type="button"
              className={track ? "field-button recording" : "field-button"}
              disabled={disabled}
              aria-pressed={track !== null}
              onClick={() => {
                seen.current = null;
                lastPoint.current = null;
                setTrack(track ? null : { id: uuidv7(), points: 0 });
              }}
            >
              {track ? t("field.trackStop", { points: track.points }) : t("field.track")}
            </button>
          </div>
        ) : (
          <form
            className="field-note"
            onSubmit={(event) => {
              event.preventDefault();
              const text = writing.trim();
              if (!text) {
                return;
              }
              void keep(note(text, { position: fix, target }), null, "note").then((saved) => {
                if (saved) {
                  setWriting(null);
                }
              });
            }}
          >
            <label htmlFor="field-note-text">{t("field.noteLabel")}</label>
            <textarea
              id="field-note-text"
              rows={5}
              maxLength={config.note_max_chars}
              value={writing}
              onChange={(event) => {
                setWriting(event.target.value);
              }}
            />
            <div className="field-row">
              <button type="submit" className="field-button" disabled={!writing.trim()}>
                {t("field.saveNote")}
              </button>
              <button
                type="button"
                className="field-button secondary"
                onClick={() => {
                  setWriting(null);
                }}
              >
                {t("field.cancel")}
              </button>
            </div>
          </form>
        )}
        {writing === null && (
          <>
            <label htmlFor="field-caption">{t("field.caption")}</label>
            <input
              id="field-caption"
              className="field-input"
              maxLength={config.note_max_chars}
              value={caption}
              onChange={(event) => {
                setCaption(event.target.value);
              }}
            />
          </>
        )}
        {!fix && <p className="note">{t("field.noPosition")}</p>}
      </section>
      <Outbox
        outbox={outbox}
        onExport={() => {
          void onExport();
        }}
      />
    </div>
  );
}
