"use client";

import { useStrings } from "@/lib/i18n";
import { LanguageSwitcher } from "./language-switcher";
import { container, focusRing, navText } from "./styles";

export function SiteHeader() {
  const t = useStrings();
  const nav = [
    { href: "#models", label: t.nav.models },
    { href: "#technology", label: t.nav.technology },
    { href: "#developers", label: t.nav.developers },
  ];

  return (
    <header className="border-b border-line">
      <a
        href="#main"
        className={`sr-only focus-visible:not-sr-only focus-visible:absolute focus-visible:start-3 focus-visible:top-3 focus-visible:z-10 focus-visible:rounded-[4px] focus-visible:bg-amber focus-visible:px-3 focus-visible:py-2 focus-visible:text-[14px] focus-visible:font-semibold focus-visible:text-amber-ink ${focusRing}`}
      >
        {t.nav.skip}
      </a>

      <div
        className={`${container} flex flex-wrap items-center gap-x-3 gap-y-0 py-4 sm:gap-x-6 lg:gap-x-8`}
      >
        <a
          href="#top"
          aria-label={t.nav.home}
          className={`me-auto flex items-center gap-2.5 rounded-[2px] ${focusRing}`}
        >
          <span aria-hidden className="h-4 w-[3px] bg-amber" />
          <span
            lang="en"
            className="font-mono text-[15px] font-medium tracking-[0.22em]"
          >
            JSM
          </span>
        </a>

        <nav
          aria-label={t.nav.sections}
          className="order-3 -mx-5 mt-4 w-[calc(100%+2.5rem)] border-t border-line px-5 pt-3 sm:order-none sm:m-0 sm:w-auto sm:border-0 sm:p-0"
        >
          <ul className={`${navText} flex gap-x-6 lg:gap-x-8`}>
            {nav.map((item) => (
              <li key={item.href}>
                <a
                  href={item.href}
                  className={`inline-block rounded-[2px] py-1 text-muted transition-colors hover:text-paper ${focusRing}`}
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <LanguageSwitcher />

        <a
          href="/chat/"
          className={`${navText} flex h-9 items-center gap-2 rounded-[4px] border border-line-strong px-3 text-paper transition-colors hover:border-amber sm:px-3.5 ${focusRing}`}
        >
          {t.nav.try}
          <span aria-hidden className="text-amber rtl:-scale-x-100">
            →
          </span>
        </a>
      </div>
    </header>
  );
}
