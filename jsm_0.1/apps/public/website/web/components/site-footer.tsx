"use client";

import { useStrings } from "@/lib/i18n";
import { container, focusRing, navText } from "./styles";

export function SiteFooter() {
  const t = useStrings();
  const links = [
    { href: "#models", label: t.nav.models },
    { href: "#developers", label: t.nav.developers },
    { href: "/chat/", label: t.nav.chat },
  ];

  return (
    <footer className="border-t border-line">
      <div
        className={`${container} flex flex-wrap items-center justify-between gap-x-10 gap-y-5 py-10`}
      >
        <p className="flex items-center gap-2.5">
          <span aria-hidden className="h-3.5 w-[3px] bg-amber" />
          <span
            lang="en"
            className="font-mono text-[13px] font-medium tracking-[0.22em]"
          >
            JSM
          </span>
        </p>

        <nav aria-label={t.nav.footer}>
          <ul className={`${navText} flex flex-wrap gap-x-7 gap-y-2`}>
            {links.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  className={`inline-block rounded-[2px] py-1 text-muted transition-colors hover:text-paper ${focusRing}`}
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
