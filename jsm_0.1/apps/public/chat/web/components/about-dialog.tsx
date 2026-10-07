"use client";

import type { RefObject } from "react";
import { modelReadout, type Model } from "@/lib/api";
import { useStrings } from "@/lib/i18n";
import { CloseIcon } from "./icons";
import { eyebrow, focusRing } from "./styles";

type Props = {
  /** The opener calls `dialogRef.current.showModal()`. */
  dialogRef: RefObject<HTMLDialogElement | null>;
  /** The model picked in the header, from the list already loaded. */
  model: Model | null;
};

/**
 * What JSM is, and the selected model's readout. A native modal
 * <dialog>: it traps focus, closes on Escape, makes the page behind
 * inert, and hands focus back to the opener when it closes.
 */
export function AboutDialog({ dialogRef, model }: Props) {
  const t = useStrings();
  const readout = model ? modelReadout(model) : [];

  return (
    <dialog
      ref={dialogRef}
      aria-label={t.aboutJsm}
      // A click on the dialog element itself is a click on the backdrop.
      onClick={(event) => {
        if (event.target === event.currentTarget) event.currentTarget.close();
      }}
      className="m-auto max-h-[calc(100dvh-2rem)] w-[min(34rem,calc(100vw-2rem))] overflow-y-auto rounded-[8px] border border-line-strong bg-surface text-paper shadow-[0_24px_60px_-20px_rgb(0_0_0/0.45)] backdrop:bg-black/45 open:motion-safe:animate-rise dark:backdrop:bg-black/65"
    >
      <div className="relative p-6 sm:p-8">
        <button
          type="button"
          onClick={() => dialogRef.current?.close()}
          aria-label={t.close}
          className={`absolute end-3 top-3 flex size-9 items-center justify-center rounded-[5px] text-muted transition-colors hover:bg-raised hover:text-paper ${focusRing}`}
        >
          <CloseIcon />
        </button>

        <p className={eyebrow}>{t.aboutKicker}</p>
        <h2
          dir="ltr"
          className="mt-3 font-mono text-[2.5rem] leading-none font-medium tracking-[0.18em] rtl:text-end"
        >
          JSM
        </h2>
        <p className="mt-4 text-[16px] leading-7 text-muted">{t.aboutBody}</p>

        <div className="mt-7 border-t border-line pt-5">
          <p className={eyebrow}>{t.selectedModel}</p>

          {model ? (
            <>
              <p className="mt-2 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[16px]">
                <span dir="ltr" className="[overflow-wrap:anywhere]">
                  {model.display_name}
                </span>
                {model.latest && (
                  <span className="rounded-[3px] border border-amber/50 px-1.5 py-px text-[11px] text-amber ltr:font-mono ltr:text-[10px] ltr:tracking-[0.12em] ltr:uppercase">
                    {t.latest}
                  </span>
                )}
              </p>

              {readout.length > 0 ? (
                <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
                  {readout.map(({ key, value }) => (
                    <div key={key} className="flex flex-col-reverse gap-1">
                      <dt className={`${eyebrow} !text-[10px] rtl:!text-[12px]`}>
                        {t.readout[key]}
                      </dt>
                      <dd
                        dir="ltr"
                        className="font-mono text-[17px] text-paper tabular-nums rtl:text-end"
                      >
                        {value}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-2 text-[14px] text-faint">{t.noMetadata}</p>
              )}
            </>
          ) : (
            <p className="mt-2 text-[14px] text-faint">{t.noModelSelected}</p>
          )}
        </div>
      </div>
    </dialog>
  );
}
