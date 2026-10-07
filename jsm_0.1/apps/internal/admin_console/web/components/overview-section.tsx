"use client";

import type { ReactNode } from "react";
import { ENDPOINTS, type Overview } from "@/lib/api";
import { DASH, formatCount, formatDateTime, formatLoss, formatText } from "@/lib/format";
import { useStrings } from "@/lib/i18n";
import type { Resource } from "@/lib/use-resource";
import { Gate, Ltr, SectionHeader, StatusBadge, SubHeading } from "./primitives";
import { label, note } from "./styles";

/** One ruled cell of the summary grid: label, figure, one line of context. */
function Cell({
  name,
  figure,
  context,
  text = false,
}: {
  name: string;
  figure: string;
  context?: ReactNode;
  /** A name from the API rather than a number. */
  text?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col bg-ink px-4 py-4 sm:px-5">
      <dt className={label}>{name}</dt>
      <dd
        className={`mt-3 break-words text-paper ${
          text
            ? "text-[19px] leading-8 font-medium sm:text-[22px]"
            : "font-mono text-[26px] leading-8 tabular-nums sm:text-[30px]"
        }`}
      >
        <bdi>{figure}</bdi>
      </dd>
      {context && (
        <dd className={`${note} mt-1.5 leading-4 [overflow-wrap:anywhere] ar:leading-5`}>
          {context}
        </dd>
      )}
    </div>
  );
}

function Summary({ overview }: { overview: Overview }) {
  const t = useStrings();
  const o = t.overview;
  const model = overview.latest_model;
  const run = overview.latest_training_run;
  const stats = run?.training_stats ?? null;

  return (
    <div className="motion-safe:animate-rise">
      {/* Hairlines are the 1px gaps showing the grid's own background. */}
      <dl className="grid grid-cols-2 gap-px border border-line bg-line lg:grid-cols-3">
        <Cell name={o.models} figure={formatCount(overview.model_count)} context={o.modelsContext} />
        <Cell name={o.runs} figure={formatCount(overview.training_run_count)} context={o.runsContext} />
        <Cell
          name={o.latestModel}
          figure={model ? formatText(model.display_name) : DASH}
          context={model ? <Ltr className="font-mono text-[11px]">{model.id}</Ltr> : o.noModel}
          text
        />
        <Cell name={o.tokensSeen} figure={formatCount(model?.tokens_seen)} context={o.ofLatestModel} />
        <Cell
          name={o.parameters}
          figure={formatCount(model?.parameters)}
          context={
            typeof model?.trainable_parameters === "number" ? (
              <>
                <span className="font-mono text-[11px] tabular-nums">
                  {formatCount(model.trainable_parameters)}
                </span>{" "}
                {o.trainable}
              </>
            ) : (
              o.ofLatestModel
            )
          }
        />
        <Cell name={o.device} figure={formatText(overview.device)} context={o.servingDevice} />
      </dl>

      <div className="mt-8">
        <SubHeading>{o.latestRun}</SubHeading>
        {run ? (
          <p className="flex flex-wrap items-center gap-x-5 gap-y-2 border-y border-line py-3 text-[12.5px] text-muted ar:text-[13.5px]">
            <StatusBadge status={run.status} />
            <Ltr className="font-mono text-[12.5px] break-all text-paper">{run.run_id}</Ltr>
            <span>
              {o.started}{" "}
              <time dateTime={run.started_at ?? undefined} title={run.started_at ?? undefined}>
                <Ltr className="font-mono text-[12.5px] text-paper tabular-nums">
                  {formatDateTime(run.started_at)}
                </Ltr>
              </time>
            </span>
            <span>
              {o.finalLoss}{" "}
              <span className="font-mono text-[12.5px] text-paper tabular-nums">
                {formatLoss(stats?.final_loss)}
              </span>
            </span>
          </p>
        ) : (
          <p className="border-y border-line py-3 text-[13.5px] text-muted">{o.noRuns}</p>
        )}
      </div>
    </div>
  );
}

export function OverviewSection({ overview }: { overview: Resource<Overview> }) {
  const t = useStrings();
  return (
    <>
      <SectionHeader
        index="01"
        title={t.nav.overview}
        sources={[{ path: ENDPOINTS.overview, resource: overview }]}
      />
      <Gate path={ENDPOINTS.overview} resource={overview}>
        {(data) => <Summary overview={data} />}
      </Gate>
    </>
  );
}
