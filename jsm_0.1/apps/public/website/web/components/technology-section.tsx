"use client";

import { useStrings } from "@/lib/i18n";
import { Band } from "./band";

export function TechnologySection() {
  const t = useStrings();
  const glossLang = t.technology.glossLang;

  return (
    <Band
      id="technology"
      index="02"
      name={t.technology.name}
      title={t.technology.title}
    >
      <ol className="mt-12 border-b border-line">
        {t.technology.points.map(({ title, gloss, body }, position) => (
          <li
            key={title}
            className="grid gap-x-8 gap-y-3 border-t border-line py-8 md:grid-cols-9 md:py-10"
          >
            <div className="flex items-baseline justify-between gap-4 md:col-span-4 md:block">
              <h3 className="flex items-baseline gap-4 text-[22px] leading-7 font-medium tracking-[-0.01em] ar:leading-8 ar:tracking-normal">
                <span
                  aria-hidden
                  lang="en"
                  dir="ltr"
                  className="w-7 shrink-0 font-mono text-[11px] tracking-[0.16em] text-faint tabular-nums"
                >
                  {`2.${position + 1}`}
                </span>
                {title}
              </h3>
              {/* The same idea in the other language, as a margin note. */}
              <p className="shrink-0 text-[16px] leading-7 text-faint md:mt-2 md:ms-11">
                <span lang={glossLang} dir={glossLang === "ar" ? "rtl" : "ltr"}>
                  {gloss}
                </span>
              </p>
            </div>
            <p className="max-w-[34rem] text-[16px] leading-7 text-muted md:col-span-5 ar:leading-8">
              {body}
            </p>
          </li>
        ))}
      </ol>
    </Band>
  );
}
