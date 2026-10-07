"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import {
  fetchDataSummary,
  fetchHealth,
  fetchModels,
  fetchOverview,
  fetchRuns,
  type Health,
} from "@/lib/api";
import { useStrings } from "@/lib/i18n";
import { useResource, type Resource } from "@/lib/use-resource";
import { DataSection } from "./data-section";
import { ArrowOutIcon, RefreshIcon, SlidersIcon } from "./icons";
import { ModelsSection } from "./models-section";
import { OverviewSection } from "./overview-section";
import { PreferencesControls } from "./preferences-controls";
import { failureText, Ltr } from "./primitives";
import { focusRing, note, quietButton } from "./styles";
import { SystemSection } from "./system-section";
import { TrainingSection } from "./training-section";

const SECTIONS = ["overview", "models", "training", "data", "system"] as const;

type SectionId = (typeof SECTIONS)[number];

// The section lives in the URL hash, so reloads and deep links keep it.
function subscribeToHash(onChange: () => void) {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

function sectionFromHash(): SectionId {
  const hash = window.location.hash.slice(1);
  return SECTIONS.find((id) => id === hash) ?? "overview";
}

const defaultSection = (): SectionId => "overview";

const capsLink = `items-center gap-1.5 rounded-[3px] font-mono text-[11px] tracking-[0.12em] text-faint uppercase transition-colors hover:text-paper ar:font-sans ar:text-[12.5px] ar:tracking-normal ${focusRing}`;

/** API status from /health: amber when it answers ok, danger when it does not. */
function ApiStatus({ health }: { health: Resource<Health> }) {
  const t = useStrings();
  const ok = health.data?.status === "ok";
  const failed = health.error !== null || (health.data !== null && !ok);

  return (
    <p
      role="status"
      title={health.error ? failureText(health.error, t) : undefined}
      className={`flex min-w-0 items-center gap-2 font-mono text-[11px] tracking-[0.12em] uppercase ar:font-sans ar:text-[12.5px] ar:tracking-normal ar:normal-case ${failed ? "text-danger" : "text-muted"}`}
    >
      <span
        aria-hidden
        className={`size-[7px] shrink-0 rounded-full ${
          failed ? "bg-danger" : ok ? "bg-amber" : "bg-line-strong"
        }`}
      />
      {/* Below 480px only the dot shows; the text stays for screen readers. */}
      <span className="truncate max-[479px]:sr-only md:overflow-visible md:whitespace-normal">
        {health.data
          ? ok
            ? t.shell.apiOk
            : t.shell.apiStatus(String(health.data.status))
          : health.error !== null
            ? t.shell.apiUnreachable
            : t.shell.apiChecking}
        {ok && health.data?.device && (
          <span className="text-faint">
            {" "}
            · <Ltr className="font-mono text-[11px] tracking-normal normal-case">{health.data.device}</Ltr>
          </span>
        )}
      </span>
    </p>
  );
}

export function Console() {
  // TODO(security): production /admin MUST require authentication and authorization.
  const t = useStrings();
  const section = useSyncExternalStore(subscribeToHash, sectionFromHash, defaultSection);
  // Narrow screens tuck the theme and language controls behind a toggle.
  const [preferencesOpen, setPreferencesOpen] = useState(false);

  // Read-only: five GETs. Nothing here loads a model or calls /generate.
  const health = useResource(fetchHealth);
  const overview = useResource(fetchOverview);
  const models = useResource(fetchModels);
  const runs = useResource(fetchRuns);
  const data = useResource(fetchDataSummary);

  const all = [health, overview, models, runs, data];
  const refreshing = all.some((resource) => resource.loading);

  function refresh() {
    for (const resource of all) resource.reload();
  }

  // A newly chosen section starts at its top, with its nav item in view
  // (the nav scrolls sideways on narrow screens).
  useEffect(() => {
    window.scrollTo(0, 0);
    document
      .querySelector('nav [aria-current="page"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [section]);

  return (
    <div className="min-h-dvh bg-ink text-paper md:grid md:grid-cols-[14rem_minmax(0,1fr)]">
      {/* Sidebar on wide screens (at the start edge: right in Arabic), top bar
          with a scrolling nav below 768px. */}
      <header className="sticky top-0 z-10 flex flex-wrap items-center border-b border-line bg-ink md:h-dvh md:flex-col md:flex-nowrap md:items-stretch md:overflow-y-auto md:border-e md:border-b-0">
        <p className="order-1 flex h-12 shrink-0 items-center gap-2.5 ps-4 whitespace-nowrap md:h-auto md:px-5 md:pt-6 md:pb-6">
          <span aria-hidden className="h-4 w-[3px] bg-amber" />
          <span dir="ltr" className="font-mono text-[14px] font-medium tracking-[0.2em]">
            JSM
          </span>
          <span className="font-mono text-[14px] tracking-[0.16em] text-muted ar:font-sans ar:text-[14.5px] ar:tracking-normal">
            {t.shell.admin}
          </span>
        </p>

        <nav
          aria-label={t.shell.sections}
          className="order-3 w-full min-w-0 shrink-0 overflow-x-auto border-t border-line md:order-2 md:overflow-visible md:border-t-0"
        >
          <ul className="flex md:flex-col">
            {SECTIONS.map((id, index) => {
              const active = id === section;
              return (
                <li key={id} className="shrink-0">
                  <a
                    href={`#${id}`}
                    aria-current={active ? "page" : undefined}
                    className={`flex h-10 items-baseline gap-2.5 border-b-2 px-4 pt-[11px] text-[13.5px] whitespace-nowrap transition-colors focus-visible:-outline-offset-2 md:h-9 md:border-s-2 md:border-b-0 md:px-[18px] md:pt-2 ar:pt-[9px] ar:text-[14.5px] ar:md:pt-1.5 ${
                      active
                        ? "border-amber text-paper"
                        : "border-transparent text-muted hover:text-paper"
                    } ${focusRing}`}
                  >
                    <span
                      aria-hidden
                      className={`font-mono text-[10.5px] tabular-nums ${active ? "text-amber" : "text-faint"}`}
                    >
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {t.nav[id]}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>

        <div
          id="preferences"
          className={`order-4 w-full shrink-0 gap-3 border-t border-line px-4 py-3 md:order-3 md:mt-auto md:flex md:flex-col md:gap-4 md:px-5 md:py-5 ${
            preferencesOpen ? "grid grid-cols-1 min-[420px]:grid-cols-2" : "hidden"
          }`}
        >
          <PreferencesControls />
        </div>

        <div className="order-2 ms-auto flex min-w-0 shrink-0 items-center gap-2.5 pe-4 md:order-4 md:ms-0 md:flex-col md:items-stretch md:gap-4 md:border-t md:border-line md:px-5 md:py-5">
          <ApiStatus health={health} />
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            aria-label={t.shell.refreshAll}
            title={t.shell.refreshAll}
            className={`${quietButton} md:justify-center`}
          >
            <RefreshIcon className={refreshing ? "motion-safe:animate-spin" : undefined} />
            <span className="hidden md:inline">
              {refreshing ? t.shell.refreshing : t.shell.refresh}
            </span>
          </button>
          <button
            type="button"
            onClick={() => setPreferencesOpen((open) => !open)}
            aria-expanded={preferencesOpen}
            aria-controls="preferences"
            aria-label={t.shell.preferences}
            title={t.shell.preferences}
            className={`${quietButton} md:hidden ${preferencesOpen ? "border-line-strong text-paper" : ""}`}
          >
            <SlidersIcon />
          </button>
          <a href="/chat/" className={`hidden self-start md:inline-flex ${capsLink}`}>
            {t.shell.openChat}
            <ArrowOutIcon />
          </a>
        </div>
      </header>

      <div className="flex min-w-0 flex-col">
        <main className="mx-auto w-full max-w-[82rem] min-w-0 flex-1 px-4 pt-6 pb-12 sm:px-6 md:px-8 md:pt-8">
          {section === "overview" && <OverviewSection overview={overview} />}
          {section === "models" && <ModelsSection models={models} />}
          {section === "training" && <TrainingSection runs={runs} />}
          {section === "data" && <DataSection data={data} />}
          {section === "system" && <SystemSection health={health} overview={overview} />}
        </main>

        <footer className="mx-auto flex w-full max-w-[82rem] flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-line px-4 py-4 sm:px-6 md:px-8">
          <p className={note}>{t.shell.notice}</p>
          <a href="/chat/" className={`inline-flex md:hidden ${capsLink}`}>
            {t.shell.openChat}
            <ArrowOutIcon />
          </a>
        </footer>
      </div>
    </div>
  );
}
