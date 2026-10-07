"use client";

import type { ReactNode } from "react";

import { useStrings } from "@/lib/i18n";
import { Band } from "./band";
import { interpolate } from "./interpolate";
import { focusRing, label, textLink } from "./styles";

/** Arabic inside a left-to-right code line, isolated so it cannot reorder it. */
function Ar({ children }: { children: string }) {
  return (
    <bdi lang="ar" dir="rtl">
      {children}
    </bdi>
  );
}

function Key({ children }: { children: string }) {
  return <span className="text-muted">&quot;{children}&quot;</span>;
}

/** An identifier inside a sentence: always Latin, always left to right. */
function Code({ children }: { children: string }) {
  return (
    <code lang="en" dir="ltr" className="font-mono text-[13px] text-muted">
      {children}
    </code>
  );
}

type SheetProps = { caption: string; status?: string; children: ReactNode };

/** A code sample. It stays left to right in both languages. */
function Sheet({ caption, status, children }: SheetProps) {
  return (
    <figure className="min-w-0">
      <figcaption className={`${label} border-b border-line pb-3`}>
        {caption}
        {status && (
          <>
            {" · "}
            <span lang="en" dir="ltr" className="font-mono text-[11px]">
              {status}
            </span>
          </>
        )}
      </figcaption>
      <pre
        lang="en"
        dir="ltr"
        tabIndex={0}
        aria-label={caption}
        className={`overflow-x-auto py-5 text-left font-mono text-[13px] leading-6 text-paper sm:text-[14px] ${focusRing}`}
      >
        <code>{children}</code>
      </pre>
    </figure>
  );
}

export function DevelopersSection() {
  const t = useStrings();
  const d = t.developers;
  const clients = [
    { name: d.web, latin: false, status: d.today, live: true },
    { name: "iOS", latin: true, status: d.planned, live: false },
    { name: "Android", latin: true, status: d.planned, live: false },
  ];

  return (
    <Band id="developers" index="03" name={d.name} title={d.title}>
      <div className="mt-7 grid gap-x-8 gap-y-12 xl:grid-cols-9">
        <div className="xl:col-span-4">
          <p className="max-w-[34rem] text-[18px] leading-8 text-muted ar:leading-9">
            {d.body}
          </p>

          <ul className="mt-9 max-w-[24rem] border-b border-line">
            {clients.map(({ name, latin, status, live }) => (
              <li
                key={name}
                className="flex items-baseline justify-between gap-6 border-t border-line py-3"
              >
                <span lang={latin ? "en" : undefined} className="text-[16px]">
                  {name}
                </span>
                <span
                  className={`${label} ${live ? "text-paper" : "text-faint"}`}
                >
                  {status}
                </span>
              </li>
            ))}
          </ul>

          <p className="mt-9 max-w-[34rem] text-[15px] leading-7 text-muted ar:leading-8">
            {interpolate(d.tryNote, {
              chat: (
                <a href="/chat/" className={`text-paper ${textLink}`}>
                  {d.chatLink}
                </a>
              ),
            })}
          </p>
        </div>

        <div className="min-w-0 border-t border-line-strong pt-6 xl:col-span-5">
          <Sheet caption={d.request}>
            <span className="text-amber">POST</span> /generate{"\n"}
            <span className="text-muted">Content-Type: application/json</span>
            {"\n\n"}
            {"{\n  "}
            <Key>prompt</Key>: &quot;<Ar>مشروع</Ar>&quot;,{"\n  "}
            <Key>model</Key>: &quot;tiny_model.pt&quot;,{"\n  "}
            <Key>temperature</Key>: 0.7,{"\n  "}
            <Key>max_new_tokens</Key>: 80{"\n}"}
          </Sheet>

          <Sheet caption={d.response} status="200">
            {"{\n  "}
            <Key>model</Key>: &quot;tiny_model.pt&quot;,{"\n  "}
            <Key>text</Key>: &quot;<Ar>مشروع…</Ar>&quot;{"\n}"}
          </Sheet>

          <p className="border-t border-line pt-4 text-[14px] leading-6 text-faint ar:text-[15px] ar:leading-7">
            {interpolate(d.codeNote, {
              text: <Code>text</Code>,
              model: <Code>model</Code>,
              endpoint: <Code>GET /models</Code>,
            })}
          </p>
        </div>
      </div>
    </Band>
  );
}
