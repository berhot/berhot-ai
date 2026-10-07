"use client";

// Every user-visible string, in both languages. `en` is typed against
// `ar`, so a key missing from either one fails the build.

import { usePreferences } from "../../../../shared/preferences";

type Lang = "ar" | "en";

/** One headline line: a heavy part, then a light part (either may be empty). */
type LeadLine = { strong: string; light: string };

const ar = {
  language: {
    group: "اللغة",
    ar: "العربية",
    en: "English",
  },
  nav: {
    skip: "تخطَّ إلى المحتوى",
    home: "JSM، أعلى الصفحة",
    sections: "أقسام الصفحة",
    footer: "روابط التذييل",
    models: "النماذج",
    technology: "التقنية",
    developers: "المطوّرون",
    chat: "المحادثة",
    try: "جرّب JSM",
  },
  hero: {
    kicker: "نماذج لغوية",
    tagline: "عربية أولًا · من الصفر",
    lead: [
      { strong: "نبني النماذج اللغوية الذكية", light: "" },
      { strong: "", light: "وندرّبها ونشغّلها." },
    ] as LeadLine[],
    // The other language's line, set opposite the headline.
    companion: "Build, train, and serve intelligent language models.",
    companionLang: "en" as Lang,
    body: "JSM مشروع نماذج لغوية يضع العربية أولًا. المُرمِّز ومعمارية Transformer وحلقة التدريب كُتبت كلها ودُرِّبت من الصفر، وتُقدَّم عبر واجهة برمجية صغيرة واحدة يمكنك تجربتها الآن.",
    learnMore: "اعرف المزيد",
  },
  models: {
    name: "النماذج",
    title: "نموذج واحد صغير، نعرضه كما هو.",
    body: "نماذج JSM نماذج لغوية بمعمارية Transformer لإكمال النصوص: تكتب البداية، ويكتب النموذج ما يليها. تضمّ العائلة اليوم نموذجًا واحدًا فقط، وهو صغير. والأرقام أدناه ليست عبارات تسويقية، بل تُقرأ من الواجهة البرمجية العاملة لحظة تحميل هذه الصفحة.",
    current: "النموذج الحالي",
    latest: "الأحدث",
    loading: "جارٍ قراءة النموذج الحالي…",
    none: "لا يوجد نموذج منشور حاليًا.",
    unavailable: "القراءة الحيّة غير متاحة حاليًا.",
    parameters: "المعاملات",
    context: "طول السياق",
    vocabulary: "حجم المفردات",
    tokens: "بالرموز",
    scale: [
      {
        when: "اليوم",
        what: "نموذج بحثي صغير واحد. يُكمل نصًّا تبدؤه أنت، وغايته إثبات أن المسار يعمل كاملًا من أوله إلى آخره.",
      },
      {
        when: "قيد التخطيط",
        what: "نماذج أكبر، تُدرَّب على نصوص عربية أكثر بالمسار نفسه. وستظهر في القراءة أعلاه حين تصبح موجودة.",
      },
    ],
  },
  technology: {
    name: "التقنية",
    title: "أربعة التزامات، نصوغها كأهداف.",
    glossLang: "en" as Lang,
    points: [
      {
        title: "نماذج أساس تضع العربية أولًا",
        gloss: "Arabic-first",
        body: "صُمِّم JSM حول العربية منذ الخطوة الأولى: إعداد البيانات وترميز النص يبدآن من النص العربي، لا من تكييف نظام بُني أصلًا للإنجليزية.",
      },
      {
        title: "تركيز على اللهجة السعودية",
        gloss: "Saudi dialect",
        body: "وجهتنا هي العربية كما تُكتب وتُنطق في السعودية، إلى جانب العربية الفصحى المعاصرة. هذا تركيز في البيانات التي نجمعها، وليس قدرة ندّعيها اليوم.",
      },
      {
        title: "تدريب من الصفر",
        gloss: "From scratch",
        body: "مُرمِّزنا، ونموذج Transformer الخاص بنا، وحلقة تدريبنا. النموذج مدرَّب من الصفر بمُرمِّزه الخاص، ليبقى كل جزء قابلًا للقراءة والفهم والتعديل.",
      },
      {
        title: "معمارية قابلة للتوسّع",
        gloss: "Scalable",
        body: "المسار نفسه وواجهة التقديم نفسها مُعدّان لحمل نماذج أكبر. والمقصود أن يعني النموّ بيانات أكثر ومعاملات أكثر، لا نظامًا مختلفًا.",
      },
    ],
  },
  developers: {
    name: "المطوّرون",
    title: "واجهة HTTP واحدة خلف كل عميل.",
    body: "كل ما يفعله JSM يمرّ عبر واجهة HTTP واحدة. محادثة الويب عميل لها اليوم، وتطبيقا iOS و Android قيد التخطيط ومصمَّمان لاستدعاء نقاط النهاية نفسها، دون خادم خلفي منفصل لكل منصة.",
    web: "الويب",
    today: "اليوم",
    planned: "قيد التخطيط",
    // {chat} becomes a link labelled with `chatLink`.
    tryNote:
      "يوضّح المثال شكل الواجهة. وأسرع طريقة لرؤيتها تجيب هي {chat}، فهي ترسل الطلب نفسه.",
    chatLink: "المحادثة",
    request: "الطلب",
    response: "الاستجابة",
    // {text}, {model} and {endpoint} become inline code.
    codeNote:
      "{text} هو نصّك متبوعًا بتكملة النموذج، و{model} معرّف مأخوذ من {endpoint}.",
  },
};

export type Strings = typeof ar;

const en: Strings = {
  language: {
    group: "Language",
    ar: "العربية",
    en: "English",
  },
  nav: {
    skip: "Skip to content",
    home: "JSM, top of page",
    sections: "Sections",
    footer: "Footer",
    models: "Models",
    technology: "Technology",
    developers: "Developers",
    chat: "Chat",
    try: "Try JSM",
  },
  hero: {
    kicker: "Language models",
    tagline: "Arabic-first · From scratch",
    lead: [
      { strong: "Build, train,", light: "" },
      { strong: "and serve", light: "intelligent" },
      { strong: "", light: "language models." },
    ],
    companion: "نماذج لغوية عربية أولًا، مبنية من الصفر",
    companionLang: "ar",
    body: "JSM is an Arabic-first language-model project. The tokenizer, the Transformer and the training loop are written and trained from scratch, and served through one small API you can try right now.",
    learnMore: "Learn more",
  },
  models: {
    name: "Models",
    title: "One small model, shown exactly as it is.",
    body: "JSM models are Transformer language models for text continuation: you write the beginning, the model writes what comes next. Right now the family has a single member, and it is small. The numbers below are not marketing copy — they are read from the running API when this page loads.",
    current: "Current model",
    latest: "Latest",
    loading: "Reading the current model…",
    none: "No model is published right now.",
    unavailable: "The live readout is unavailable right now.",
    parameters: "Parameters",
    context: "Context length",
    vocabulary: "Vocabulary size",
    tokens: "tokens",
    scale: [
      {
        when: "Today",
        what: "One small research model. It continues a text you start, and it exists to prove the whole pipeline end to end.",
      },
      {
        when: "Planned",
        what: "Larger models, trained on more Arabic text with the same pipeline. They will appear in the readout above when they exist.",
      },
    ],
  },
  technology: {
    name: "Technology",
    title: "Four commitments, stated as intentions.",
    glossLang: "ar",
    points: [
      {
        title: "Arabic-first foundation models",
        gloss: "العربية أولًا",
        body: "JSM is designed around Arabic from the first step. Data preparation and tokenization start from Arabic text, rather than adapting a system that was built for English.",
      },
      {
        title: "Saudi dialect focus",
        gloss: "اللهجة السعودية",
        body: "The direction is Arabic as it is written and spoken in Saudi Arabia, alongside Modern Standard Arabic. This is a focus for the data we gather — not a capability we claim today.",
      },
      {
        title: "Trained from scratch",
        gloss: "من الصفر",
        body: "Our own tokenizer, our own Transformer, our own training loop. The model is trained from scratch with its own tokenizer, so every stage can be read, understood and changed.",
      },
      {
        title: "Scalable architecture",
        gloss: "قابلة للتوسّع",
        body: "The same pipeline and the same serving API are meant to carry larger models. Growing should mean more data and more parameters, not a different system.",
      },
    ],
  },
  developers: {
    name: "Developers",
    title: "One HTTP API behind every client.",
    body: "Everything JSM does goes through one HTTP API. The web chat is a client of it today; iOS and Android apps are planned and are meant to call the same endpoints, with no separate backend per platform.",
    web: "Web",
    today: "Today",
    planned: "Planned",
    tryNote:
      "The example shows the shape of the interface. The quickest way to see it answer is {chat}, which sends this same request.",
    chatLink: "the chat",
    request: "Request",
    response: "Response",
    codeNote:
      "{text} is your prompt followed by the model’s continuation. {model} is an id from {endpoint}.",
  },
};

const STRINGS: Record<Lang, Strings> = { ar, en };

/** The dictionary for the current language. */
export function useStrings(): Strings {
  return STRINGS[usePreferences().language];
}
