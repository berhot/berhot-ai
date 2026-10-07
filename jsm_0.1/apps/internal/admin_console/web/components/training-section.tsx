"use client";

import { Fragment, useState } from "react";
import { ENDPOINTS, type TrainingRun } from "@/lib/api";
import {
  DASH,
  formatCount,
  formatDateTime,
  formatDuration,
  formatLoss,
  formatSeconds,
  formatText,
  formatValue,
  utcOffsetLabel,
} from "@/lib/format";
import { useStrings, type Strings } from "@/lib/i18n";
import type { Resource } from "@/lib/use-resource";
import { ChevronIcon } from "./icons";
import {
  Empty,
  Gate,
  Ltr,
  Readout,
  SectionHeader,
  StatusBadge,
  SubHeading,
  TableScroller,
  type ReadoutRow,
} from "./primitives";
import { focusRing, keyLabel, label, note, td, tdMono, tdNum, th, thNum } from "./styles";

const COLUMN_COUNT = 10;

function configRows(config: Record<string, unknown> | null): ReadoutRow[] {
  return Object.entries(config ?? {}).map(([key, value]) => ({
    label: key,
    rawKey: true,
    value: formatValue(value),
  }));
}

/** Local time on screen, the raw UTC value on hover and for machines. */
function Timestamp({ iso }: { iso: string | null }) {
  if (!iso) return <span className="block">{DASH}</span>;
  return (
    <time dateTime={iso} title={iso} className="block">
      <Ltr>{formatDateTime(iso)}</Ltr>
    </time>
  );
}

function ConfigBlock({
  title,
  rawTitle = false,
  rows,
  t,
}: {
  title: string;
  /** The title is an API field name, shown as-is. */
  rawTitle?: boolean;
  rows: ReadoutRow[];
  t: Strings;
}) {
  return (
    <div className="min-w-0">
      <h3 className={`${rawTitle ? keyLabel : label} mb-2`}>
        {rawTitle ? <Ltr>{title}</Ltr> : title}
      </h3>
      {rows.length > 0 ? (
        <Readout rows={rows} />
      ) : (
        <p className={`${note} border-y border-line py-2`}>{t.common.notRecorded}</p>
      )}
    </div>
  );
}

function RunDetail({ run, t }: { run: TrainingRun; t: Strings }) {
  const stats = run.training_stats;
  const recorded: ReadoutRow[] = [
    ...(stats
      ? [
          {
            label: "training_seconds",
            rawKey: true,
            value: formatSeconds(stats.training_seconds, t.duration),
          },
          { label: "learning_rate", rawKey: true, value: formatValue(stats.learning_rate) },
        ]
      : []),
    ...configRows(run.model_stats),
  ];
  return (
    <div className="grid gap-x-10 gap-y-6 md:grid-cols-2 xl:grid-cols-3">
      <ConfigBlock title="model_config" rawTitle rows={configRows(run.model_config)} t={t} />
      <ConfigBlock title="training_config" rawTitle rows={configRows(run.training_config)} t={t} />
      <ConfigBlock title={t.training.recordedStats} rows={recorded} t={t} />
    </div>
  );
}

function RunsTable({ runs, t }: { runs: TrainingRun[]; t: Strings }) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const h = t.training;

  function toggle(runId: string) {
    setOpen((current) => {
      const next = new Set(current);
      if (!next.delete(runId)) next.add(runId);
      return next;
    });
  }

  return (
    <TableScroller name={h.tableName}>
      <table className="w-full border-collapse text-[13.5px]">
        <thead>
          <tr>
            <th scope="col" className={th}>{h.runId}</th>
            <th scope="col" className={th}>{h.status}</th>
            <th scope="col" className={th}>{h.startFinish}</th>
            <th scope="col" className={thNum}>{h.duration}</th>
            <th scope="col" className={th}>{h.device}</th>
            <th scope="col" className={thNum}>{h.epochs}</th>
            <th scope="col" className={thNum}>{h.steps}</th>
            <th scope="col" className={thNum}>{h.tokens}</th>
            <th scope="col" className={thNum}>{h.finalLoss}</th>
            <th scope="col" className={th}>{h.modelFile}</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run, index) => {
            const stats = run.training_stats;
            const expanded = open.has(run.run_id);
            const detailId = `run-detail-${index}`;
            const configured = run.training_config?.epochs;
            return (
              <Fragment key={run.run_id}>
                <tr className="transition-colors hover:bg-surface">
                  <th scope="row" className={`${td} text-start font-normal`}>
                    <button
                      type="button"
                      onClick={() => toggle(run.run_id)}
                      aria-expanded={expanded}
                      aria-controls={detailId}
                      title={expanded ? h.hideConfig : h.showConfig}
                      className={`-mx-1 flex items-center gap-2 rounded-[3px] px-1 text-paper hover:text-amber ${focusRing}`}
                    >
                      {/* Points along the reading direction, then down when open. */}
                      <ChevronIcon
                        className={`shrink-0 text-faint transition-transform ${
                          expanded ? "rotate-90 rtl:-rotate-90 rtl:-scale-x-100" : "rtl:-scale-x-100"
                        }`}
                      />
                      <Ltr className="font-mono text-[12.5px]">{run.run_id}</Ltr>
                    </button>
                  </th>
                  <td className={td}>
                    <StatusBadge status={run.status} />
                  </td>
                  <td className={`${tdMono} leading-5`}>
                    <Timestamp iso={run.started_at} />
                    <Timestamp iso={run.finished_at} />
                  </td>
                  <td className={`${tdNum} ar:font-sans`}>
                    {formatDuration(run.started_at, run.finished_at, t.duration)}
                  </td>
                  <td className={tdMono}>
                    <Ltr>{formatText(run.device)}</Ltr>
                  </td>
                  <td className={tdNum}>
                    <Ltr>
                      {formatCount(stats?.epochs_completed)}
                      <span className="text-faint"> / </span>
                      {formatCount(configured)}
                    </Ltr>
                  </td>
                  <td className={tdNum}>{formatCount(stats?.global_step)}</td>
                  <td className={tdNum}>{formatCount(stats?.tokens_seen)}</td>
                  <td className={tdNum}>{formatLoss(stats?.final_loss)}</td>
                  <td className={tdMono}>
                    <Ltr
                      className="inline-block max-w-[11rem] truncate align-top"
                    >
                      <span title={run.checkpoint ?? undefined}>{formatText(run.checkpoint)}</span>
                    </Ltr>
                  </td>
                </tr>
                {expanded && (
                  <tr id={detailId}>
                    {/* Pinned to the scroller's visible width (100cqw), not the table's. */}
                    <td colSpan={COLUMN_COUNT} className="border-b border-line bg-surface p-0">
                      <div className="sticky start-0 w-[100cqw] px-3 py-5 motion-safe:animate-rise md:px-5">
                        <RunDetail run={run} t={t} />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </TableScroller>
  );
}

function RunsContent({ runs }: { runs: TrainingRun[] }) {
  const t = useStrings();
  if (runs.length === 0) {
    return <Empty title={t.training.emptyTitle}>{t.training.emptyBody}</Empty>;
  }
  return (
    <div className="motion-safe:animate-rise">
      <SubHeading aside={t.training.runCount(formatCount(runs.length))}>
        {t.training.runs}
      </SubHeading>
      <RunsTable runs={runs} t={t} />
      <p className={`${note} mt-3 max-w-[90ch]`}>
        {t.training.timesNoteBefore}
        <Ltr className="font-mono text-[11px]">{utcOffsetLabel()}</Ltr>
        {t.training.timesNoteAfter}
      </p>
    </div>
  );
}

export function TrainingSection({ runs }: { runs: Resource<TrainingRun[]> }) {
  const t = useStrings();
  return (
    <>
      <SectionHeader
        index="03"
        title={t.nav.training}
        sources={[{ path: ENDPOINTS.runs, resource: runs }]}
      />
      <Gate path={ENDPOINTS.runs} resource={runs}>
        {(data) => <RunsContent runs={data} />}
      </Gate>
    </>
  );
}
