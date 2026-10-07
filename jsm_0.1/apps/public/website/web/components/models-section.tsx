"use client";

import { useStrings } from "@/lib/i18n";
import { Band } from "./band";
import { LiveModel } from "./live-model";
import { label } from "./styles";

export function ModelsSection() {
  const t = useStrings();

  return (
    <Band id="models" index="01" name={t.models.name} title={t.models.title}>
      <p className="mt-7 max-w-[40rem] text-[18px] leading-8 text-muted ar:leading-9">
        {t.models.body}
      </p>

      <div className="mt-12">
        <LiveModel />
      </div>

      <dl className="mt-12 grid gap-x-8 gap-y-8 sm:grid-cols-2">
        {t.models.scale.map(({ when, what }) => (
          <div key={when}>
            <dt className={label}>{when}</dt>
            <dd className="mt-3 max-w-[30rem] text-[16px] leading-7 text-muted ar:leading-8">
              {what}
            </dd>
          </div>
        ))}
      </dl>
    </Band>
  );
}
