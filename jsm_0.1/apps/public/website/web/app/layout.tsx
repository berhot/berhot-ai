import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans_Arabic } from "next/font/google";
import "./globals.css";

import { PreferencesProvider } from "../../../../shared/preferences";
import { preferencesScript } from "../../../../shared/preferences-script";

// One superfamily for every job. Plex Sans Arabic carries the Plex Sans
// Latin glyphs too, so prompts, model output and UI text share one face.
const plexSans = IBM_Plex_Sans_Arabic({
  variable: "--font-plex-sans",
  subsets: ["arabic", "latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  // No generated fallback face: it would claim Arabic before Plex does.
  adjustFontFallback: false,
});

export const metadata: Metadata = {
  title: "JSM — Arabic-first language models, built from scratch",
  description:
    "JSM is an Arabic-first language-model project: its own tokenizer, Transformer and training loop, served through one small API.",
};

export const viewport: Viewport = {
  themeColor: "#f6f2e9",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      // Defaults; the stored preferences take over on the client.
      lang="ar"
      dir="rtl"
      data-theme="light"
      suppressHydrationWarning
      className={`${plexSans.variable} ${plexMono.variable} h-full scroll-smooth antialiased`}
    >
      <head>
        <script
          dangerouslySetInnerHTML={{ __html: preferencesScript(false) }}
        />
      </head>
      <body className="h-full">
        <PreferencesProvider themable={false}>{children}</PreferencesProvider>
      </body>
    </html>
  );
}
