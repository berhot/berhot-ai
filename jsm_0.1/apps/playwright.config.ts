import { defineConfig } from "@playwright/test";
import path from "node:path";

const fixture = path.resolve(process.env.JSM_TEST_WAV ?? "../../jsm-voice/storage/uploads/speech_001.wav").replaceAll("\\", "/");
export default defineConfig({
  testDir: "./tests", workers: 1, timeout: 90000,
  use: {
    baseURL: process.env.JSM_TEST_URL ?? "http://127.0.0.1:8000",
    headless: true, screenshot: "only-on-failure", trace: "retain-on-failure",
    launchOptions: { args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", `--use-file-for-fake-audio-capture=${fixture}`] },
  },
});
