// Every user-visible string, in both languages. Arabic is the source
// shape: English is typed against it, so a missing key fails the build.

import { usePreferences } from "../../../../shared/preferences";

const ar = {
  // Header
  aboutJsm: "حول JSM",
  close: "إغلاق",
  clearChat: "مسح المحادثة",
  settings: "الإعدادات",
  model: "النموذج",
  latest: "الأحدث",
  latestModel: "أحدث نموذج",

  // Model list states
  loadingModels: "جارٍ تحميل النماذج…",
  readingCheckpoints: "جارٍ قراءة النماذج…",
  modelsUnavailable: "تعذّر الوصول إلى النماذج",
  couldNotLoadModels: "تعذّر تحميل النماذج",
  noModelsFound: "لا توجد نماذج",
  noModelsHint:
    "درّب نموذجًا ثم أعد تحميل الصفحة. يبقى الإرسال معطّلًا إلى أن يتوفر نموذج.",
  noMetadata: "لا توجد بيانات وصفية",
  tryAgain: "أعد المحاولة",

  // Model readout
  readout: {
    params: "المعاملات",
    tokensSeen: "الرموز المقروءة",
    epochs: "دورات التدريب",
    context: "طول السياق",
    vocab: "المفردات",
  },
  readoutInline: {
    params: (value: string) => `المعاملات ${value}`,
    tokensSeen: (value: string) => `الرموز المقروءة ${value}`,
    epochs: (value: string) => `دورات التدريب ${value}`,
    context: (value: string) => `السياق ${value}`,
    vocab: (value: string) => `المفردات ${value}`,
  },

  // Conversation
  conversation: "المحادثة",
  greeting: "اكتب بداية نص، وسيكمله النموذج.",
  examples: "أمثلة",
  promptPrefix: "النص المُدخل: ",
  generating: "جارٍ التوليد…",
  error: "خطأ",
  eosTitle: "أنهى النموذج التسلسل دون أن يولّد نصًا",
  conditions: (temperature: string, maxNewTokens: number) =>
    `الحرارة ${temperature} · الحد ${maxNewTokens}`,
  requestFailed: (status: number) => `فشل الطلب (${status})`,
  somethingWrong: "حدث خطأ غير متوقع.",

  // Composer
  prompt: "النص",
  placeholder: "اكتب نصًا…",
  noModelAvailable: "لا يوجد نموذج متاح",
  send: "إرسال",
  hintSend: "للإرسال",
  hintNewline: "لسطر جديد",

  // Settings
  generation: "التوليد",
  temperature: "درجة الحرارة",
  temperatureHint: "0 تعني اختيار الأرجح دائمًا",
  maxNewTokens: "أقصى عدد للرموز الجديدة",
  theme: "المظهر",
  themes: { system: "النظام", light: "فاتح", dark: "داكن" },
  language: "اللغة",

  // About dialog
  aboutKicker: "منضدة فحص نقاط الحفظ",
  aboutBody:
    "نموذج لغوي صغير جدًا، دُرِّب من الصفر. اختر نقطة حفظ، واكتب بداية نص، ثم اقرأ ما يُكمله به النموذج.",
  selectedModel: "النموذج المحدد",
  noModelSelected: "لا يوجد نموذج محدد.",
};

export type Strings = typeof ar;

const en: Strings = {
  aboutJsm: "About JSM",
  close: "Close",
  clearChat: "Clear chat",
  settings: "Settings",
  model: "Model",
  latest: "latest",
  latestModel: "Latest model",

  loadingModels: "Loading models…",
  readingCheckpoints: "Reading models…",
  modelsUnavailable: "Models unavailable",
  couldNotLoadModels: "Could not load models",
  noModelsFound: "No models found",
  noModelsHint:
    "Train a model, then reload this page. Sending is disabled until one is available.",
  noMetadata: "No metadata recorded",
  tryAgain: "Try again",

  readout: {
    params: "Params",
    tokensSeen: "Tokens seen",
    epochs: "Epochs",
    context: "Context",
    vocab: "Vocab",
  },
  readoutInline: {
    params: (value) => `${value} params`,
    tokensSeen: (value) => `${value} tokens seen`,
    epochs: (value) => `${value} epochs`,
    context: (value) => `context ${value}`,
    vocab: (value) => `vocab ${value}`,
  },

  conversation: "Conversation",
  greeting: "Write the start of a text; the model continues it.",
  examples: "Examples",
  promptPrefix: "Prompt: ",
  generating: "Generating…",
  error: "Error",
  eosTitle: "The model ended the sequence without producing text",
  conditions: (temperature, maxNewTokens) =>
    `temp ${temperature} · max ${maxNewTokens}`,
  requestFailed: (status) => `Request failed (${status})`,
  somethingWrong: "Something went wrong.",

  prompt: "Prompt",
  placeholder: "Write a prompt…",
  noModelAvailable: "No model available",
  send: "Send",
  hintSend: "send",
  hintNewline: "newline",

  generation: "Generation",
  temperature: "Temperature",
  temperatureHint: "0 is greedy",
  maxNewTokens: "Max new tokens",
  theme: "Theme",
  themes: { system: "System", light: "Light", dark: "Dark" },
  language: "Language",

  aboutKicker: "Checkpoint workbench",
  aboutBody:
    "A tiny language model, trained from scratch. Pick a checkpoint, write the start of a text, and read what the model continues with.",
  selectedModel: "Selected model",
  noModelSelected: "No model selected.",
};

const dictionary: Record<"ar" | "en", Strings> = { ar, en };

/** Language names are shown in their own language, whatever the UI's. */
export const LANGUAGE_NAMES = { ar: "العربية", en: "English" } as const;

export function useStrings(): Strings {
  return dictionary[usePreferences().language];
}

/** What went wrong, kept as data so it follows a language switch. */
export type Failure = { detail: string | null; status: number | null };

/** Server `detail` is shown as-is; our own fallbacks are translated. */
export function describeFailure(failure: Failure, t: Strings): string {
  if (failure.detail) return failure.detail;
  return failure.status === null
    ? t.somethingWrong
    : t.requestFailed(failure.status);
}
