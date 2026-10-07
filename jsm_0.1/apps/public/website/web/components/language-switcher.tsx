"use client";

import { useStrings } from "@/lib/i18n";
import { LANGUAGES, usePreferences } from "../../../../shared/preferences";
import { focusRing } from "./styles";

/** العربية · English. Each name is written in its own language. */
export function LanguageSwitcher() {
  const t = useStrings();
  const { language, setLanguage } = usePreferences();

  return (
    <div
      role="group"
      aria-label={t.language.group}
      className="flex h-9 items-stretch rounded-[4px] border border-line-strong p-[3px]"
    >
      {LANGUAGES.map((code) => {
        const active = code === language;
        return (
          <button
            key={code}
            type="button"
            lang={code}
            aria-pressed={active}
            onClick={() => setLanguage(code)}
            className={`rounded-[2px] px-2.5 text-[13px] leading-none transition-colors ${
              active
                ? "bg-paper text-ink"
                : "text-muted hover:text-paper"
            } ${focusRing}`}
          >
            {t.language[code]}
          </button>
        );
      })}
    </div>
  );
}
