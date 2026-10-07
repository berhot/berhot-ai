"use client";

import { useStrings } from "@/lib/i18n";
import { usePreferences } from "../../../../shared/preferences";
import { container, focusRing, label, textLink } from "./styles";

/**
 * The bilingual lockup. The active language leads as the headline, set at
 * the start edge; the other language answers from the opposite edge, with
 * one annotated hairline between the two.
 */
export function Hero() {
  const t = useStrings();
  const { language } = usePreferences();
  const other = t.hero.companionLang;

  return (
    <section
      aria-labelledby="hero-title"
      className={`${container} pt-8 pb-20 sm:pt-10 lg:pb-28`}
    >
      <p
        className={`${label} flex justify-between gap-6 motion-safe:animate-rise`}
      >
        <span className="hidden sm:inline">{t.hero.kicker}</span>
        <span className="whitespace-nowrap">{t.hero.tagline}</span>
      </p>

      <h1
        id="hero-title"
        className="mt-10 text-[clamp(2.6rem,7.7vw,7.25rem)] leading-[0.96] tracking-[-0.035em] text-balance motion-safe:animate-rise motion-safe:[animation-delay:70ms] sm:mt-14 sm:text-wrap ar:leading-[1.18] ar:tracking-normal"
      >
        {t.hero.lead.map(({ strong, light }, position) => (
          <span key={position} className="sm:block">
            {strong && <span className="font-semibold">{strong}</span>}
            {strong && light && " "}
            {light && <span className="font-normal">{light}</span>}{" "}
          </span>
        ))}
      </h1>

      <div
        aria-hidden
        lang="en"
        className={`${label} mt-9 flex items-center gap-4 motion-safe:animate-rise motion-safe:[animation-delay:140ms] sm:mt-12`}
      >
        <span>{language}</span>
        <span className="h-px flex-1 bg-line-strong" />
        <span className="h-[7px] w-[7px] rotate-45 bg-amber" />
        <span className="h-px flex-1 bg-line-strong" />
        <span>{other}</span>
      </div>

      <p
        lang={other}
        dir={other === "ar" ? "rtl" : "ltr"}
        className={`mt-6 text-balance motion-safe:animate-rise motion-safe:[animation-delay:210ms] sm:mt-8 ${
          other === "ar"
            ? "text-[clamp(1.9rem,5.1vw,4.75rem)] leading-[1.4] font-medium"
            : "text-[clamp(1.6rem,3.9vw,3.5rem)] leading-[1.08] tracking-[-0.025em]"
        }`}
      >
        {t.hero.companion}
      </p>

      <div className="mt-12 grid gap-x-8 gap-y-8 border-t border-line pt-8 motion-safe:animate-rise motion-safe:[animation-delay:280ms] sm:mt-16 lg:grid-cols-12">
        <p className="max-w-[36rem] text-[18px] leading-8 text-muted lg:col-span-7 ar:leading-9">
          {t.hero.body}
        </p>

        <div className="flex flex-wrap items-center gap-x-7 gap-y-4 lg:col-span-5 lg:justify-end">
          <a
            href="/chat/"
            className={`flex h-12 items-center gap-3 rounded-[4px] bg-amber px-6 text-[16px] font-semibold text-amber-ink transition-colors hover:bg-paper hover:text-ink ${focusRing}`}
          >
            {t.nav.try}
            <span aria-hidden className="rtl:-scale-x-100">
              →
            </span>
          </a>
          <a href="#models" className={`text-[16px] text-muted ${textLink}`}>
            {t.hero.learnMore}
          </a>
        </div>
      </div>
    </section>
  );
}
