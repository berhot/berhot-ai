import type { ReactNode } from "react";

import { container, label } from "./styles";

type Props = {
  id: string;
  index: string;
  name: string;
  title: string;
  children: ReactNode;
};

/**
 * One editorial band: a hairline, a numbered label in the margin column,
 * and the content on a shared twelve-column grid.
 */
export function Band({ id, index, name, title, children }: Props) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="border-t border-line"
    >
      <div
        className={`${container} grid gap-x-8 gap-y-8 py-20 lg:grid-cols-12 lg:py-32`}
      >
        <p className={`${label} lg:col-span-3 lg:pt-3`}>
          <span className="font-mono text-[11px] text-amber tabular-nums">
            {index}
          </span>
          <span aria-hidden> — </span>
          {name}
        </p>

        <div className="min-w-0 lg:col-span-9">
          <h2
            id={`${id}-title`}
            className="max-w-[22ch] text-[clamp(2rem,4.4vw,3.75rem)] leading-[1.04] font-medium tracking-[-0.025em] text-balance ar:leading-[1.3] ar:tracking-normal"
          >
            {title}
          </h2>
          {children}
        </div>
      </div>
    </section>
  );
}
