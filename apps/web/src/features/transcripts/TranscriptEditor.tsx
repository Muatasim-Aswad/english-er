import { useEffect, useState } from "react";
import { Button } from "../../shared/ui/Button";
import { IconButton } from "../../shared/ui/IconButton";
import { EditIcon, HistoryIcon } from "../../shared/ui/icons";
import { Panel, PanelText } from "../../shared/ui/Panel";
import { PanelTitle } from "../../shared/ui/typography";
import type { TranscriptDetail } from "./api";
import { copy } from "./copy";

type Props = {
  detail: TranscriptDetail;
  busy: boolean;
  onSave: (text: string) => Promise<boolean | undefined>;
};
export function TranscriptEditor({ detail, busy, onSave }: Props) {
  const [editingTranscript, setEditingTranscript] = useState(false);
  const [transcriptDraft, setTranscriptDraft] = useState(detail.transcript_text);
  const [showCapturedText, setShowCapturedText] = useState(false);
  useEffect(() => {
    if (!editingTranscript) setTranscriptDraft(detail.transcript_text);
  }, [detail.transcript_text, editingTranscript]);
  const saveTranscript = async () => {
    if (transcriptDraft === detail.transcript_text || (await onSave(transcriptDraft))) {
      setEditingTranscript(false);
      setShowCapturedText(false);
    }
  };
  return (
    <Panel>
      <div className="flex items-start justify-between gap-4">
        <PanelTitle>{showCapturedText ? copy.capturedTranscript : copy.transcript}</PanelTitle>
        <div className="flex gap-1.5">
          {!editingTranscript && detail.transcript_text !== detail.original_text && (
            <IconButton
              aria-pressed={showCapturedText}
              disabled={busy}
              label={showCapturedText ? copy.showCurrent : copy.showCaptured}
              onClick={() => setShowCapturedText((current) => !current)}
            >
              <HistoryIcon />
            </IconButton>
          )}
          {!editingTranscript && (
            <IconButton
              disabled={busy}
              label={copy.edit}
              onClick={() => {
                setShowCapturedText(false);
                setEditingTranscript(true);
              }}
            >
              <EditIcon />
            </IconButton>
          )}
        </div>
      </div>
      {editingTranscript ? (
        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault();
            void saveTranscript();
          }}
        >
          <label className="mb-2 block text-xs font-bold" htmlFor="transcript-text">
            {copy.textLabel}
          </label>
          <textarea
            autoFocus
            className="w-full resize-y rounded-lg border border-control bg-card p-3 leading-normal focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-accent"
            disabled={busy}
            id="transcript-text"
            onChange={(event) => setTranscriptDraft(event.target.value)}
            rows={8}
            value={transcriptDraft}
          />
          <div className="mt-3 flex items-center gap-4">
            <Button disabled={busy || transcriptDraft.trim().length === 0} type="submit">
              {busy ? copy.saving : copy.save}
            </Button>
            <Button
              disabled={busy}
              onClick={() => {
                setTranscriptDraft(detail.transcript_text);
                setEditingTranscript(false);
              }}
            >
              {copy.cancel}
            </Button>
          </div>
        </form>
      ) : (
        <PanelText>{showCapturedText ? detail.original_text : detail.transcript_text}</PanelText>
      )}
    </Panel>
  );
}
