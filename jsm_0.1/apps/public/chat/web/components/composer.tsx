"use client";

import { useLayoutEffect, type KeyboardEvent, type RefObject } from "react";
import { useStrings } from "@/lib/i18n";
import { SendIcon } from "./icons";
import { focusRing } from "./styles";

type Props = {
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  canSend: boolean;
  hasModel: boolean;
};

const MAX_HEIGHT = 220;

export function Composer({
  textareaRef,
  value,
  onChange,
  onSend,
  canSend,
  hasModel,
}: Props) {
  const t = useStrings();

  // Grow with the content, up to a limit, then scroll.
  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_HEIGHT)}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
  }, [value, textareaRef]);

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;
    // Enter that confirms an IME composition must not send.
    if (event.nativeEvent.isComposing || event.keyCode === 229) return;
    event.preventDefault();
    onSend();
  }

  return (
    <footer className="shrink-0 border-t border-line bg-ink">
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSend();
        }}
        className="mx-auto w-full max-w-[48rem] px-4 pt-3 pb-3 sm:px-6 sm:pb-4"
      >
        <div className="flex items-end gap-2 rounded-[7px] border border-line-strong bg-surface p-1.5 transition-colors focus-within:border-amber focus-within:ring-1 focus-within:ring-amber/40">
          <textarea
            ref={textareaRef}
            dir="auto"
            rows={1}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={onKeyDown}
            aria-label={t.prompt}
            placeholder={hasModel ? t.placeholder : t.noModelAvailable}
            className="min-h-10 min-w-0 flex-1 resize-none bg-transparent px-2.5 py-2 text-[16px] leading-6 text-paper outline-none placeholder:text-faint"
          />
          <button
            type="submit"
            disabled={!canSend}
            className={`flex h-10 shrink-0 items-center gap-1.5 rounded-[5px] bg-amber px-3.5 text-[13px] font-semibold text-amber-ink transition-colors hover:bg-amber-bright active:translate-y-px disabled:pointer-events-none disabled:bg-raised disabled:text-faint ${focusRing}`}
          >
            <SendIcon />
            {t.send}
          </button>
        </div>
        <p className="mt-2 hidden text-[12px] text-faint sm:block">
          <kbd dir="ltr" className="font-mono text-[11px]">Enter</kbd>{" "}
          {t.hintSend}
          <span className="mx-1.5">·</span>
          <kbd dir="ltr" className="font-mono text-[11px]">Shift+Enter</kbd>{" "}
          {t.hintNewline}
        </p>
      </form>
    </footer>
  );
}
