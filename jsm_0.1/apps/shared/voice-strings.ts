"use client";

import { usePreferences } from "./preferences";

const en = {
  text: "JSM Text", voice: "JSM Voice", record: "Start recording", stop: "Stop and send",
  cancel: "Cancel", consent: "I have permission to record and process this audio.",
  privacy: "Audio is processed on this server and deleted after the request. Replies use a synthetic voice.",
  ready: "Voice ready", starting: "Loading voice models…", unavailable: "Voice unavailable",
  recording: "Recording", processing: "Transcribing, thinking, and speaking…", recorded: "Voice message",
  upload: "Upload WAV", limits: "Up to 30 seconds · mono PCM16 WAV",
  synthetic: "Generated voice", retry: "Refresh status", stopped: "Request cancelled",
  permission: "Microphone access needs your permission and localhost or HTTPS.",
  empty: "How can JSM help you?", hint: "Write a message or try a voice conversation.",
  placeholder: "Message JSM…", quality: "JSM is an experimental model. Responses may be inaccurate.",
  voiceTitle: "Voice models", activityTitle: "Voice activity", openChat: "Test live in chat",
  asr: "Speech recognition", tts: "Speech synthesis", llm: "Text model", device: "Device",
  retention: "Recording retention", deleted: "Deleted after each request", busy: "Processing a turn",
  idle: "Available", recent: "Recent voice turns", noTurns: "No voice turns in this server session yet.",
  sessionOnly: "Last 100 requests in this server session. Audio and transcripts are not included.",
  time: "Time", model: "Model", status: "Status", latency: "Total time", completed: "Completed",
  error: "Failed", loading: "Loading…", flow: "Microphone → speech recognition → selected JSM model → speech synthesis",
  selected: "The chat model picker controls which JSM checkpoint answers in both modes.",
  listeningHint: "Speak, then stop to send. Recording stops automatically at 30 seconds.",
};
const ar: typeof en = {
  text: "JSM نص", voice: "JSM صوت", record: "بدء التسجيل", stop: "إيقاف وإرسال",
  cancel: "إلغاء", consent: "لدي إذن بتسجيل هذا الصوت ومعالجته.",
  privacy: "تُعالج الملفات الصوتية على هذا الخادم وتُحذف بعد الطلب. الردود بصوت اصطناعي.",
  ready: "الصوت جاهز", starting: "جارٍ تحميل نماذج الصوت…", unavailable: "الصوت غير متاح",
  recording: "جارٍ التسجيل", processing: "جارٍ التفريغ والتوليد والنطق…", recorded: "رسالة صوتية",
  upload: "رفع WAV", limits: "حتى 30 ثانية · WAV أحادي PCM16",
  synthetic: "صوت مولّد", retry: "تحديث الحالة", stopped: "أُلغي الطلب",
  permission: "يتطلب الميكروفون إذنك وفتح الموقع عبر localhost أو HTTPS.",
  empty: "كيف يمكن لـ JSM مساعدتك؟", hint: "اكتب رسالة أو جرّب المحادثة الصوتية.",
  placeholder: "راسل JSM…", quality: "JSM نموذج تجريبي. قد تكون الردود غير دقيقة.",
  voiceTitle: "نماذج الصوت", activityTitle: "نشاط الصوت", openChat: "تجربة مباشرة في المحادثة",
  asr: "التعرف على الكلام", tts: "توليد الكلام", llm: "النموذج النصي", device: "الجهاز",
  retention: "الاحتفاظ بالتسجيل", deleted: "يُحذف بعد كل طلب", busy: "جارٍ معالجة طلب",
  idle: "متاح", recent: "الطلبات الصوتية الأخيرة", noTurns: "لا توجد طلبات صوتية في جلسة الخادم بعد.",
  sessionOnly: "آخر 100 طلب في جلسة الخادم الحالية، دون صوت أو نصوص المحادثات.",
  time: "الوقت", model: "النموذج", status: "الحالة", latency: "المدة الإجمالية", completed: "مكتمل",
  error: "فشل", loading: "جارٍ التحميل…", flow: "الميكروفون ← التعرف على الكلام ← نموذج JSM المحدد ← توليد الكلام",
  selected: "يحدد اختيار النموذج في المحادثة نقطة حفظ JSM المستخدمة في الوضعين.",
  listeningHint: "تحدث ثم أوقف التسجيل للإرسال. يتوقف التسجيل تلقائيًا بعد 30 ثانية.",
};
export const useVoiceStrings = () => usePreferences().language === "ar" ? ar : en;
