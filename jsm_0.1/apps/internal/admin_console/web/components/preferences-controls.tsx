"use client";

import {
  LANGUAGES,
  THEMES,
  usePreferences,
  type Language,
} from "../../../../shared/preferences";
import { useStrings } from "@/lib/i18n";
import { focusRing, label } from "./styles";

/** Each language is named in its own script, whatever the UI language. */
const LANGUAGE_NAMES: Record<Language, string> = {
  ar: "العربية",
  en: "English",
};

type Option<T extends string> = { value: T; text: string; lang?: Language };

/** Compact segmented control; the choice applies immediately. */
function Segmented<T extends string>({
  name,
  options,
  selected,
  onSelect,
}: {
  name: string;
  options: Option<T>[];
  selected: T;
  onSelect: (value: T) => void;
}) {
  return (
    <div className="min-w-0">
      <p className={`${label} mb-1.5`}>{name}</p>
      <div role="group" aria-label={name} className="flex rounded-[5px] border border-line p-0.5">
        {options.map((option) => {
          const active = option.value === selected;
          return (
            <button
              key={option.value}
              type="button"
              lang={option.lang}
              aria-pressed={active}
              onClick={() => onSelect(option.value)}
              className={`h-7 min-w-0 flex-1 rounded-[3px] px-2 text-[12.5px] whitespace-nowrap transition-colors ${
                active
                  ? "bg-raised font-medium text-paper"
                  : "text-muted hover:text-paper"
              } ${focusRing}`}
            >
              {option.text}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** Theme and language: the only controls in the console besides Refresh. */
export function PreferencesControls() {
  const t = useStrings();
  const { theme, setTheme, language, setLanguage } = usePreferences();

  return (
    <>
      <Segmented
        name={t.shell.theme}
        options={THEMES.map((value) => ({ value, text: t.shell.themes[value] }))}
        selected={theme}
        onSelect={setTheme}
      />
      <Segmented
        name={t.shell.language}
        options={LANGUAGES.map((value) => ({
          value,
          text: LANGUAGE_NAMES[value],
          lang: value,
        }))}
        selected={language}
        onSelect={setLanguage}
      />
    </>
  );
}
