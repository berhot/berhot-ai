"use client";

import { useId } from "react";

type Props<T extends string> = {
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (value: T) => void;
};

/**
 * Compact one-of-many switch. Real radio inputs underneath, so arrow
 * keys, focus and screen readers behave as a radio group.
 */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: Props<T>) {
  const name = useId();

  return (
    <fieldset className="flex items-center justify-between gap-4">
      <legend className="float-start py-2 text-[13px]">{label}</legend>
      <div className="flex rounded-[5px] border border-line bg-ink p-0.5">
        {options.map((option) => (
          <label
            key={option.value}
            className="cursor-pointer rounded-[3px] px-2.5 py-1 text-[13px] text-muted transition-colors hover:text-paper has-checked:bg-amber has-checked:font-medium has-checked:text-amber-ink has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-amber"
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
