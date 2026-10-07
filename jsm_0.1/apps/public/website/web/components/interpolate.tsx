import { Fragment, type ReactNode } from "react";

/**
 * Fill `{name}` placeholders in a translated sentence with elements, so
 * each language decides where its links and code fragments sit.
 */
export function interpolate(
  template: string,
  parts: Record<string, ReactNode>,
): ReactNode {
  return template.split(/\{(\w+)\}/).map((piece, position) => (
    <Fragment key={position}>
      {position % 2 === 1 ? (parts[piece] ?? null) : piece}
    </Fragment>
  ));
}
