import { numberLabel } from "../../infra/format";
import { Button } from "../../shared/ui/Button";
import { IconButton } from "../../shared/ui/IconButton";
import { SpeakerIcon } from "../../shared/ui/icons";
import { Panel, PanelText } from "../../shared/ui/Panel";
import { InlineError, PanelTitle } from "../../shared/ui/typography";
import type { TranscriptDetail } from "./api";
import { copy } from "./copy";
import { useTranscriptAudio, playbackRates } from "./useTranscriptAudio";

type Props = { detail: TranscriptDetail; onStale: () => void };
export function CorrectionPanel({ detail, onStale }: Props) {
  const {
    state: audioState,
    url: audioUrl,
    notice: audioNotice,
    rate: playbackRate,
    setRate: setPlaybackRate,
    player: audioPlayerRef,
    prepare: prepareAudio,
    exists: audioExists,
  } = useTranscriptAudio(detail, onStale);
  const audioButtonLabel =
    audioState === "loading"
      ? copy.audioPreparing
      : audioExists
        ? copy.audioExisting
        : copy.audioPrepare;
  return detail.status === "completed" && detail.correction !== null ? (
    <>
      <Panel tone="corrected">
        <div className="flex items-start justify-between gap-4">
          <PanelTitle>{copy.corrected}</PanelTitle>
          <IconButton
            aria-busy={audioState === "loading"}
            disabled={audioState === "loading"}
            label={audioButtonLabel}
            onClick={() => void prepareAudio()}
            tone={audioState === "loading" ? "processing" : audioExists ? "existing" : "neutral"}
          >
            <SpeakerIcon />
          </IconButton>
        </div>
        <PanelText>{detail.correction.corrected_text}</PanelText>
        {audioState === "loading" && (
          <p className="mt-3 text-caption text-muted">{copy.preparingAudio}</p>
        )}
        {audioState === "error" && audioNotice !== null && (
          <InlineError className="mt-3">{audioNotice}</InlineError>
        )}
        {audioState === "ready" && audioUrl !== null && (
          <div>
            <audio
              aria-label={copy.audioLabel}
              className="mt-3.5 block w-full"
              controls
              preload="metadata"
              ref={audioPlayerRef}
              src={audioUrl}
            />
            <div
              aria-label={copy.speedGroup}
              className="mt-2 flex items-center justify-end gap-1.5"
              role="group"
            >
              <span className="mr-0.5 text-xs font-bold text-muted-strong">{copy.speed}</span>
              {playbackRates.map((rate) => (
                <Button
                  aria-label={copy.setSpeed(rate)}
                  aria-pressed={playbackRate === rate}
                  className="min-w-12"
                  key={rate}
                  onClick={() => setPlaybackRate(rate)}
                  size="xs"
                  variant="chip"
                >
                  {copy.speedLabel(rate)}
                </Button>
              ))}
            </div>
          </div>
        )}
      </Panel>
      <section className="mt-6">
        <PanelTitle className="mb-3">
          {copy.corrections}{" "}
          <span className="font-medium text-muted">
            {numberLabel(detail.correction.corrections.length)}
          </span>
        </PanelTitle>
        {detail.correction.corrections.length === 0 ? (
          <p className="mb-3 text-xs text-muted">{copy.noCorrections}</p>
        ) : (
          <dl className="mt-4 grid gap-2">
            {detail.correction.corrections.map((pair, index) => (
              <div
                className="grid grid-cols-1 overflow-hidden rounded-lg border border-line-soft bg-card sm:grid-cols-2"
                key={`${pair.wrong}-${pair.correct}-${index}`}
              >
                <dt className="p-3 text-clay-700 line-through decoration-1">{pair.wrong}</dt>
                <dd className="border-t border-line-soft p-3 text-sage-700 sm:border-t-0 sm:border-l">
                  {pair.correct}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>
      <p className="mx-0.5 mt-4.5 text-sm text-muted">{detail.correction.overall_observation}</p>
    </>
  ) : (
    <Panel>
      <PanelTitle className="mb-3">
        {detail.status === "failed" ? copy.correctionFailed : copy.correctionProgress}
      </PanelTitle>
      <PanelText>
        {detail.last_error ??
          (detail.status === "pending" ? copy.waitingWorker : copy.processingWorker)}
      </PanelText>
    </Panel>
  );
}
