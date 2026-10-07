"use client";

import type { ReactNode } from "react";
import type { ApiFailure } from "@/lib/api";
import { formatClock } from "@/lib/format";
import { useStrings, type Strings } from "@/lib/i18n";
import type { Resource } from "@/lib/use-resource";
import { badge, focusRing, keyLabel, label, note, quietButton } from "./styles";

/**
 * Latin readouts (ids, paths, timestamps, config values) keep their
 * left-to-right order inside Arabic text, without changing the alignment
 * of the block they sit in.
 */
export function Ltr({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <bdi dir="ltr" className={className}>
      {children}
    </bdi>
  );
}

/** `GET /models`, always Latin. */
export function Endpoint({ path }: { path: string }) {
  return <Ltr className="font-mono">GET {path}</Ltr>;
}

/** One line for a failed read, in the viewer's language. */
export function failureText(failure: ApiFailure, t: Strings): string {
  switch (failure.kind) {
    case "detail":
      return failure.detail;
    case "status":
      return t.errors.status(String(failure.status));
    case "network":
      return t.errors.network;
    case "notJson":
      return t.errors.notJson;
    case "unexpected":
      return t.errors.unexpected;
    default:
      return t.errors.unknown;
  }
}

export type Source = {
  path: string;
  // Only the read state is needed here, whatever the payload is.
  resource: Pick<Resource<unknown>, "data" | "error" | "loading" | "loadedAt">;
};

/** Section title with the endpoints it reads and when each was last read. */
export function SectionHeader({
  index,
  title,
  sources,
}: {
  index: string;
  title: string;
  sources: Source[];
}) {
  const t = useStrings();
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b border-line-strong pb-3">
      <div>
        <p className={label}>
          <span className="font-mono tabular-nums">{index}</span> / {t.common.section}
        </p>
        <h1 className="mt-1 text-[22px] leading-7 font-medium tracking-tight text-paper ar:leading-8 ar:tracking-normal">
          {title}
        </h1>
      </div>
      <ul className="flex flex-col gap-0.5 text-[11px] leading-4 text-faint tabular-nums sm:items-end">
        {sources.map(({ path, resource }) => (
          <li key={path} className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-muted">
              <Endpoint path={path} />
            </span>
            <span aria-live="polite" className="font-mono ar:font-sans ar:text-[12px]">
              {resource.loading ? (
                t.common.reading
              ) : resource.error ? (
                <span className="text-danger">{t.common.failed}</span>
              ) : resource.loadedAt ? (
                <>
                  {t.common.readAt}{" "}
                  <Ltr className="font-mono text-[11px]">{formatClock(resource.loadedAt)}</Ltr>
                </>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </header>
  );
}

/** Small ruled heading inside a section. */
export function SubHeading({
  children,
  aside,
}: {
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-4">
      <h2 className={label}>{children}</h2>
      {aside && <p className={`${note} tabular-nums`}>{aside}</p>}
    </div>
  );
}

export function Loading({ path }: { path: string }) {
  const t = useStrings();
  return (
    <p
      role="status"
      className="flex items-center gap-2 border-y border-line py-4 font-mono text-[12px] text-faint ar:font-sans ar:text-[13px]"
    >
      <span aria-hidden className="h-3 w-[5px] bg-line-strong motion-safe:animate-caret" />
      {t.common.loading}
      <span className="text-[11.5px]">
        <Endpoint path={path} />
      </span>
    </p>
  );
}

export function ErrorNote({
  path,
  failure,
  onRetry,
}: {
  path: string;
  failure: ApiFailure;
  onRetry: () => void;
}) {
  const t = useStrings();
  return (
    <div role="alert" className="border-s-2 border-danger py-1 ps-4">
      <p className="text-[11.5px] text-danger">
        <span className="font-mono tracking-[0.12em] uppercase ar:font-sans ar:text-[12.5px] ar:tracking-normal">
          {t.common.failedLabel}
        </span>{" "}
        · <Endpoint path={path} />
      </p>
      <p className="mt-1.5 max-w-[60ch] text-[14px] leading-6 break-words text-paper">
        {/* A server `detail` may be in either script; it sets its own direction. */}
        <bdi>{failureText(failure, t)}</bdi>
      </p>
      <button type="button" onClick={onRetry} className={`mt-3 ${quietButton}`}>
        {t.common.retry}
      </button>
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="border-y border-line py-8">
      <p className="text-[15px] text-paper">{title}</p>
      {children && (
        <p className="mt-1 max-w-[60ch] text-[13.5px] leading-6 text-muted">{children}</p>
      )}
    </div>
  );
}

/** Loading, error or content for one API read. */
export function Gate<T>({
  path,
  resource,
  children,
}: {
  path: string;
  resource: Resource<T>;
  children: (data: T) => ReactNode;
}) {
  if (resource.data !== null) return <>{children(resource.data)}</>;
  if (resource.error !== null) {
    return <ErrorNote path={path} failure={resource.error} onRetry={resource.reload} />;
  }
  return <Loading path={path} />;
}

export type ReadoutRow = {
  label: string;
  value: ReactNode;
  /** The label is a literal API key: Latin, left-to-right, not translated. */
  rawKey?: boolean;
};

/** Plain key/value readout, one ruled row per key. */
export function Readout({ rows }: { rows: ReadoutRow[] }) {
  return (
    <dl className="border-t border-line">
      {rows.map((row) => (
        <div
          key={row.label}
          className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] items-baseline gap-x-4 border-b border-line py-2 sm:grid-cols-[13rem_minmax(0,1fr)]"
        >
          <dt className={`${row.rawKey ? keyLabel : label} [overflow-wrap:anywhere]`}>
            {row.rawKey ? <Ltr>{row.label}</Ltr> : row.label}
          </dt>
          <dd className="font-mono text-[13px] [overflow-wrap:anywhere] text-paper tabular-nums">
            {/* Text values pick their own direction: Latin ids, numbers or Arabic units. */}
            {typeof row.value === "string" ? <bdi>{row.value}</bdi> : row.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** A wide table scrolls inside this box; the page itself never does. */
export function TableScroller({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div
      role="region"
      aria-label={name}
      tabIndex={0}
      className={`@container relative max-w-full overflow-x-auto border-t border-line-strong ${focusRing}`}
    >
      {children}
    </div>
  );
}

export function LatestBadge() {
  const t = useStrings();
  return <span className={`${badge} border-amber/60 text-amber`}>{t.common.latest}</span>;
}

const FAILED = ["failed", "error", "errored", "crashed"];

/**
 * Quiet text badge. Amber marks a live run, danger a failed one. The three
 * statuses the console knows are translated; anything else is shown as sent.
 */
export function StatusBadge({ status }: { status: string | null }) {
  const t = useStrings();
  const value = (status ?? "").trim().toLowerCase();
  const failed = FAILED.includes(value);
  const running = value === "running";
  const known = value === "completed" || value === "running" || value === "failed";

  return (
    <span
      className={`${badge} ${
        failed
          ? "border-danger/60 text-danger"
          : value === "completed" || running
            ? "border-line-strong text-paper"
            : "border-line text-muted"
      }`}
    >
      {running && <span aria-hidden className="size-[6px] rounded-full bg-amber" />}
      {known ? t.status[value] : value === "" ? t.status.unknown : <Ltr className="font-mono tracking-normal normal-case">{(status ?? "").trim()}</Ltr>}
    </span>
  );
}
