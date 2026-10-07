"use client";

import { ENDPOINTS, type Model } from "@/lib/api";
import { formatCount, formatText } from "@/lib/format";
import { useStrings, type Strings } from "@/lib/i18n";
import type { Resource } from "@/lib/use-resource";
import {
  Empty,
  Gate,
  LatestBadge,
  Ltr,
  SectionHeader,
  SubHeading,
  TableScroller,
} from "./primitives";
import { td, tdNum, th, thNum } from "./styles";

type NumericHead = "parameters" | "epochs" | "globalStep" | "tokensSeen" | "context" | "vocab";

const NUMERIC: { head: NumericHead; key: keyof Model }[] = [
  { head: "parameters", key: "parameters" },
  { head: "epochs", key: "epochs" },
  { head: "globalStep", key: "global_step" },
  { head: "tokensSeen", key: "tokens_seen" },
  { head: "context", key: "context_length" },
  { head: "vocab", key: "vocab_size" },
];

/** One presentation for one model or many: a ledger row per model. */
function ModelsTable({ models, t }: { models: Model[]; t: Strings }) {
  return (
    <TableScroller name={t.models.list}>
      <table className="w-full border-collapse text-[13.5px]">
        <thead>
          <tr>
            <th scope="col" className={th}>{t.models.model}</th>
            {NUMERIC.map(({ head, key }) => (
              <th key={key} scope="col" className={thNum}>{t.models[head]}</th>
            ))}
            <th scope="col" className={th}>{t.models.latest}</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.id} className="transition-colors hover:bg-surface">
              <th scope="row" className={`${td} text-start font-normal`}>
                <span className="block text-paper">
                  <bdi>{formatText(model.display_name)}</bdi>
                </span>
                <span className="block text-[11px] leading-4 text-faint">
                  <Ltr className="font-mono">{model.id}</Ltr>
                </span>
              </th>
              {NUMERIC.map(({ key }) => (
                <td key={key} className={tdNum}>{formatCount(model[key])}</td>
              ))}
              <td className={td}>{model.latest && <LatestBadge />}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroller>
  );
}

function ModelsContent({ models }: { models: Model[] }) {
  const t = useStrings();
  if (models.length === 0) {
    return <Empty title={t.models.emptyTitle}>{t.models.emptyBody}</Empty>;
  }
  return (
    <div className="motion-safe:animate-rise">
      <SubHeading aside={t.models.count(formatCount(models.length))}>
        {t.models.list}
      </SubHeading>
      <ModelsTable models={models} t={t} />
    </div>
  );
}

export function ModelsSection({ models }: { models: Resource<Model[]> }) {
  const t = useStrings();
  return (
    <>
      <SectionHeader
        index="02"
        title={t.nav.models}
        sources={[{ path: ENDPOINTS.models, resource: models }]}
      />
      <Gate path={ENDPOINTS.models} resource={models}>
        {(data) => <ModelsContent models={data} />}
      </Gate>
    </>
  );
}
