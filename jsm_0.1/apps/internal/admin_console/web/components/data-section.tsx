"use client";

import { ENDPOINTS, type DataSummary } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { useStrings, type Strings } from "@/lib/i18n";
import type { Resource } from "@/lib/use-resource";
import { Gate, Ltr, SectionHeader, SubHeading } from "./primitives";
import { label, note } from "./styles";

type Unit = keyof Strings["data"]["unit"];
type StageId = keyof Strings["data"]["stage"];

type Reading = { unit: Unit; value: number | null | undefined };

type Stage = {
  id: StageId;
  /** The API field(s) the readings come from. */
  field: string;
  readings: Reading[];
};

const PROCESSED: Unit[] = ["cleaned", "normalized", "filtered", "deduplicated"];
const SPLITS: Unit[] = ["train", "validation", "test"];

/** The pipeline in order. Every figure is a count the API reported. */
function stagesOf(summary: DataSummary): Stage[] {
  const processed = summary.processed_batches ?? {};
  const dataset = summary.dataset_documents ?? {};
  return [
    {
      id: "uploads",
      field: "uploads · upload_files",
      readings: [
        { unit: "sources", value: summary.uploads },
        { unit: "files", value: summary.upload_files },
      ],
    },
    {
      id: "incoming",
      field: "incoming_batches",
      readings: [{ unit: "batches", value: summary.incoming_batches }],
    },
    {
      id: "inspections",
      field: "inspections",
      readings: [{ unit: "inspections", value: summary.inspections }],
    },
    {
      id: "quarantined",
      field: "quarantined_batches",
      readings: [{ unit: "batches", value: summary.quarantined_batches }],
    },
    {
      id: "provenance",
      field: "provenance_decisions",
      readings: [{ unit: "decisions", value: summary.provenance_decisions }],
    },
    {
      id: "raw",
      field: "raw_batches",
      readings: [{ unit: "batches", value: summary.raw_batches }],
    },
    {
      id: "extracted",
      field: "extracted_batches",
      readings: [{ unit: "batches", value: summary.extracted_batches }],
    },
    {
      id: "processed",
      field: "processed_batches",
      readings: PROCESSED.map((unit) => ({ unit, value: processed[unit] })),
    },
    {
      id: "dataset",
      field: "dataset_documents",
      readings: SPLITS.map((unit) => ({ unit, value: dataset[unit] })),
    },
  ];
}

function Ledger({ summary }: { summary: DataSummary }) {
  const t = useStrings();
  const stages = stagesOf(summary);
  return (
    <div className="motion-safe:animate-rise">
      <SubHeading aside={t.data.stages(String(stages.length))}>{t.data.ledger}</SubHeading>
      <ol className="border-t border-line-strong">
        {stages.map((stage, index) => {
          const last = index === stages.length - 1;
          return (
            <li key={stage.id} className="grid grid-cols-[1.75rem_minmax(0,1fr)] gap-x-3 sm:grid-cols-[2.5rem_minmax(0,1fr)] sm:gap-x-4">
              {/* The spine: one node per stage, joined top to bottom. */}
              <div aria-hidden className="flex flex-col items-center">
                <span className={`h-[1.6rem] w-px ${index === 0 ? "bg-transparent" : "bg-line-strong"}`} />
                <span className="size-[7px] shrink-0 border border-muted bg-ink" />
                <span className={`w-px flex-1 ${last ? "bg-transparent" : "bg-line-strong"}`} />
              </div>

              <div className="flex flex-col gap-x-10 gap-y-3 border-b border-line py-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h3 className="flex items-baseline gap-3 text-[15px] leading-6 text-paper">
                    <span className="w-[1rem] shrink-0 font-mono text-[11px] text-faint tabular-nums">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    {t.data.stage[stage.id]}
                  </h3>
                  <p className="ms-[1.75rem] text-[11px] leading-4 break-all text-faint">
                    <Ltr className="font-mono">{stage.field}</Ltr>
                  </p>
                </div>

                <dl className="ms-[1.75rem] flex flex-wrap gap-x-7 gap-y-2 sm:ms-0 sm:justify-end">
                  {stage.readings.map((reading) => (
                    <div key={reading.unit} className="flex min-w-[4.5rem] flex-col sm:items-end">
                      <dt className={`${label} order-2 mt-0.5`}>{t.data.unit[reading.unit]}</dt>
                      <dd className="font-mono text-[22px] leading-7 text-paper tabular-nums">
                        {formatCount(reading.value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </div>
            </li>
          );
        })}
      </ol>
      <p className={`${note} mt-3`}>{t.data.note}</p>
    </div>
  );
}

export function DataSection({ data }: { data: Resource<DataSummary> }) {
  const t = useStrings();
  return (
    <>
      <SectionHeader
        index="04"
        title={t.nav.data}
        sources={[{ path: ENDPOINTS.data, resource: data }]}
      />
      <Gate path={ENDPOINTS.data} resource={data}>
        {(summary) => <Ledger summary={summary} />}
      </Gate>
    </>
  );
}
