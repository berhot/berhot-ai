"use client";

import { useSyncExternalStore } from "react";
import { ENDPOINTS, type Health, type Overview } from "@/lib/api";
import { DASH, formatCount, formatText } from "@/lib/format";
import { useStrings } from "@/lib/i18n";
import type { Resource } from "@/lib/use-resource";
import { Gate, Ltr, Readout, SectionHeader, SubHeading } from "./primitives";

const noSubscription = () => () => {};

/** The origin every API path resolves against; empty during prerender. */
function useOrigin(): string {
  return useSyncExternalStore(
    noSubscription,
    () => window.location.origin,
    () => "",
  );
}

export function SystemSection({
  health,
  overview,
}: {
  health: Resource<Health>;
  overview: Resource<Overview>;
}) {
  const t = useStrings();
  const s = t.system;
  const origin = useOrigin();
  const apiBase = { label: s.apiBase, value: origin || DASH };

  return (
    <>
      <SectionHeader
        index="05"
        title={t.nav.system}
        sources={[
          { path: ENDPOINTS.health, resource: health },
          { path: ENDPOINTS.overview, resource: overview },
        ]}
      />

      <div className="grid gap-x-12 gap-y-9 xl:grid-cols-2">
        <section aria-label={s.api}>
          <SubHeading>{s.api}</SubHeading>
          {health.data ? (
            <Readout
              rows={[
                { label: s.apiStatus, value: formatText(health.data.status) },
                { label: s.servingDevice, value: formatText(health.data.device) },
                apiBase,
              ]}
            />
          ) : (
            <>
              <Readout rows={[apiBase]} />
              <div className="mt-5">
                <Gate path={ENDPOINTS.health} resource={health}>
                  {() => null}
                </Gate>
              </div>
            </>
          )}
        </section>

        <section aria-label={s.inventory}>
          <SubHeading>{s.inventory}</SubHeading>
          <Gate path={ENDPOINTS.overview} resource={overview}>
            {(data) => (
              <Readout
                rows={[
                  { label: s.models, value: formatCount(data.model_count) },
                  {
                    label: s.latestModel,
                    value: data.latest_model ? (
                      <>
                        <bdi className="font-sans text-[13.5px]">
                          {formatText(data.latest_model.display_name)}
                        </bdi>
                        <span className="block text-[11px] text-faint">
                          <Ltr>{data.latest_model.id}</Ltr>
                        </span>
                      </>
                    ) : (
                      DASH
                    ),
                  },
                  { label: s.runs, value: formatCount(data.training_run_count) },
                ]}
              />
            )}
          </Gate>
        </section>
      </div>
    </>
  );
}
