import { DevelopersSection } from "@/components/developers-section";
import { Hero } from "@/components/hero";
import { ModelsSection } from "@/components/models-section";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { TechnologySection } from "@/components/technology-section";

export default function Home() {
  return (
    <div id="top" className="min-h-full overflow-x-clip">
      <SiteHeader />
      <main id="main">
        <Hero />
        <ModelsSection />
        <TechnologySection />
        <DevelopersSection />
      </main>
      <SiteFooter />
    </div>
  );
}
