"use client";

import { useEffect, useId, useRef, useState } from "react";
import { LANGUAGE_NAMES, useStrings } from "@/lib/i18n";
import {
  MAX_NEW_TOKENS,
  TEMPERATURE,
  formatTemperature,
  resolveMaxNewTokens,
  resolveTemperature,
  type SettingsDraft,
} from "@/lib/settings";
import {
  LANGUAGES,
  THEMES,
  usePreferences,
} from "../../../../shared/preferences";
import { SlidersIcon } from "./icons";
import { Segmented } from "./segmented";
import { eyebrow, focusRing } from "./styles";

type Props = {
  /** Generation settings; left out where nothing is generated (About). */
  generation?: {
    settings: SettingsDraft;
    onChange: (settings: SettingsDraft) => void;
  };
};

const fieldClass = `h-9 w-24 rounded-[4px] border border-line bg-ink px-2.5 text-end font-mono text-[13px] text-paper tabular-nums transition-colors hover:border-line-strong ${focusRing}`;

export function SettingsPopover({ generation }: Props) {
  const t = useStrings();
  const { language, setLanguage, theme, setTheme } = usePreferences();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const temperatureId = useId();
  const maxTokensId = useId();

  // Close on outside click and on Escape.
  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    }

    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    // On narrow screens the panel anchors to the header row so it always fits.
    <div ref={rootRef} className="shrink-0 sm:relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label={t.settings}
        aria-expanded={open}
        aria-controls={panelId}
        className={`flex h-9 items-center gap-2 rounded-[5px] border px-2.5 text-[13px] transition-colors ${open ? "border-amber/60 text-paper" : "border-line text-muted hover:border-line-strong hover:text-paper"} ${focusRing}`}
      >
        <SlidersIcon />
        <span className="hidden sm:inline">{t.settings}</span>
      </button>

      {open && (
        <div
          id={panelId}
          role="group"
          aria-label={t.settings}
          className="absolute end-4 top-full z-20 mt-1.5 flex w-[min(20rem,calc(100vw-2rem))] flex-col gap-3 rounded-[6px] border border-line-strong bg-raised p-4 shadow-[0_18px_40px_-16px_rgb(0_0_0/0.3)] motion-safe:animate-rise sm:end-0 dark:shadow-[0_18px_40px_-12px_rgb(0_0_0/0.7)]"
        >
          <Segmented
            label={t.language}
            value={language}
            onChange={setLanguage}
            options={LANGUAGES.map((value) => ({
              value,
              label: LANGUAGE_NAMES[value],
            }))}
          />
          <Segmented
            label={t.theme}
            value={theme}
            onChange={setTheme}
            options={THEMES.map((value) => ({
              value,
              label: t.themes[value],
            }))}
          />

          {generation && (
            <>
              <p className={`${eyebrow} border-t border-line pt-3`}>
                {t.generation}
              </p>

              <div className="flex items-center justify-between gap-4">
                <label htmlFor={temperatureId} className="text-[13px]">
                  {t.temperature}
                  <span className="block text-[12px] text-faint">
                    {t.temperatureHint}
                  </span>
                </label>
                <input
                  id={temperatureId}
                  dir="ltr"
                  type="number"
                  inputMode="decimal"
                  min={TEMPERATURE.min}
                  max={TEMPERATURE.max}
                  step={TEMPERATURE.step}
                  title={`${TEMPERATURE.min}–${TEMPERATURE.max}`}
                  value={generation.settings.temperature}
                  onChange={(event) =>
                    generation.onChange({
                      ...generation.settings,
                      temperature: event.target.value,
                    })
                  }
                  onBlur={() =>
                    generation.onChange({
                      ...generation.settings,
                      temperature: formatTemperature(
                        resolveTemperature(generation.settings.temperature),
                      ),
                    })
                  }
                  className={fieldClass}
                />
              </div>

              <div className="flex items-center justify-between gap-4">
                <label htmlFor={maxTokensId} className="text-[13px]">
                  {t.maxNewTokens}
                  <span
                    dir="ltr"
                    className="block font-mono text-[11px] text-faint rtl:text-end"
                  >
                    {MAX_NEW_TOKENS.min}–{MAX_NEW_TOKENS.max}
                  </span>
                </label>
                <input
                  id={maxTokensId}
                  dir="ltr"
                  type="number"
                  inputMode="numeric"
                  min={MAX_NEW_TOKENS.min}
                  max={MAX_NEW_TOKENS.max}
                  step={MAX_NEW_TOKENS.step}
                  value={generation.settings.maxNewTokens}
                  onChange={(event) =>
                    generation.onChange({
                      ...generation.settings,
                      maxNewTokens: event.target.value,
                    })
                  }
                  onBlur={() =>
                    generation.onChange({
                      ...generation.settings,
                      maxNewTokens: String(
                        resolveMaxNewTokens(generation.settings.maxNewTokens),
                      ),
                    })
                  }
                  className={fieldClass}
                />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
