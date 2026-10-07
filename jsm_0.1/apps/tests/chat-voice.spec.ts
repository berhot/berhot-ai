import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const fixture = path.resolve(process.env.JSM_TEST_WAV ?? "../../jsm-voice/storage/uploads/speech_001.wav");

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("jsm.language", "en"));
});

test("selected real text model answers and carries conversation history", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/chat/");
  await expect(page.getByRole("combobox", { name: "Model", exact: true })).toBeEnabled();
  const picker = page.getByRole("combobox", { name: "Model", exact: true });
  const selectedId = await picker.locator("option").first().getAttribute("value");
  expect(selectedId).toBeTruthy();
  await picker.selectOption(selectedId!);
  await page.getByRole("textbox", { name: "Prompt", exact: true }).fill("مرحبا");
  const response = page.waitForResponse((res) => res.url().endsWith("/api/chat"));
  await page.getByRole("button", { name: "Send", exact: true }).click();
  expect((await response).status()).toBe(200);
  await expect(page.locator("article")).toHaveCount(1);
  await expect(page.getByText("Generating…", { exact: true })).toHaveCount(0);
  const nextRequest = page.waitForRequest((req) => req.url().endsWith("/api/chat"));
  await page.getByRole("textbox", { name: "Prompt", exact: true }).fill("شكرا");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const payload = (await nextRequest).postDataJSON();
  expect(payload.history.map((item: { role: string }) => item.role)).toEqual(["user", "assistant"]);
  expect(payload.model).toBe(selectedId);
  await expect(page.getByText("Generating…", { exact: true })).toHaveCount(0, { timeout: 30000 });
  expect(errors).toEqual([]);
});

test("real WAV upload returns a transcript and playable synthesized audio", async ({ page }) => {
  test.skip(!fs.existsSync(fixture), "Set JSM_TEST_WAV to a consented speech WAV.");
  await page.goto("/chat/");
  await page.getByRole("button", { name: "JSM Voice", exact: true }).click();
  await expect(page.getByText("Voice ready", { exact: true })).toBeVisible({ timeout: 120000 });
  await expect(page.getByRole("button", { name: "Start recording", exact: true })).toBeDisabled();
  await page.getByRole("checkbox").check();
  const response = page.waitForResponse((res) => res.url().endsWith("/api/voice/turn"));
  await page.locator('input[type="file"]').setInputFiles(fixture);
  const result = await response;
  expect(result.status()).toBe(200);
  const payload = await result.json();
  expect(payload.transcript.length).toBeGreaterThan(3);
  expect(payload.synthetic).toBe(true);
  await expect(page.locator("audio")).toBeVisible();
  await expect.poll(() => page.locator("audio").evaluate((audio: HTMLAudioElement) => audio.readyState)).toBeGreaterThan(0);
  await page.screenshot({ path: "test-results/voice-chat.png", fullPage: true });
  await page.getByRole("button", { name: "Clear chat", exact: true }).click();
  await expect(page.locator("audio")).toHaveCount(0);
});

test("microphone worklet produces a real voice request and releases its track", async ({ page, context }) => {
  test.skip(!fs.existsSync(fixture), "Set JSM_TEST_WAV to a consented speech WAV.");
  await context.grantPermissions(["microphone"]);
  await page.addInitScript(() => {
    const tracks: MediaStreamTrack[] = [];
    Object.defineProperty(window, "__recordingTracks", { value: tracks });
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const stream = await original(constraints); tracks.push(...stream.getTracks()); return stream;
    };
  });
  await page.goto("/chat/");
  await page.getByRole("button", { name: "JSM Voice", exact: true }).click();
  await page.getByRole("checkbox").check();
  await expect(page.getByRole("button", { name: "Start recording", exact: true })).toBeEnabled({ timeout: 120000 });
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop and send", exact: true })).toBeVisible();
  await page.waitForTimeout(5200);
  const response = page.waitForResponse((res) => res.url().endsWith("/api/voice/turn"));
  await page.getByRole("button", { name: "Stop and send", exact: true }).click();
  expect((await response).status()).toBe(200);
  await expect(page.locator("audio")).toBeVisible();
  await expect(page.getByRole("button", { name: "Stop and send", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { __recordingTracks: MediaStreamTrack[] }).__recordingTracks.every((track) => track.readyState === "ended"))).toBe(true);
});

test("cancelling a recording sends no request and restores the composer", async ({ page, context }) => {
  test.skip(!fs.existsSync(fixture), "Set JSM_TEST_WAV to a consented speech WAV.");
  await context.grantPermissions(["microphone"]);
  const requests: string[] = [];
  page.on("request", (req) => { if (req.url().endsWith("/api/voice/turn")) requests.push(req.url()); });
  await page.goto("/chat/");
  await page.getByRole("button", { name: "JSM Voice", exact: true }).click();
  await page.getByRole("checkbox").check();
  await expect(page.getByRole("button", { name: "Start recording", exact: true })).toBeEnabled({ timeout: 120000 });
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await expect(page.getByRole("button", { name: "Stop and send", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(page.getByRole("button", { name: "Start recording", exact: true })).toBeEnabled();
  await expect(page.getByRole("textbox", { name: "Prompt", exact: true })).toBeEnabled();
  expect(requests).toEqual([]);
});

test("microphone denial is visible and recording can be retried", async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException("Permission denied", "NotAllowedError"); };
  });
  await page.goto("/chat/");
  await page.getByRole("button", { name: "JSM Voice", exact: true }).click();
  await page.getByRole("checkbox").check();
  await expect(page.getByRole("button", { name: "Start recording", exact: true })).toBeEnabled({ timeout: 120000 });
  await page.getByRole("button", { name: "Start recording", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "Permission denied" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start recording", exact: true })).toBeEnabled();
});

test("admin voice pages display real readiness and request activity", async ({ page }) => {
  await page.goto("/admin/#voice");
  await expect(page.getByRole("heading", { name: "Voice models", exact: true })).toBeVisible();
  await expect(page.getByText("ar_JO-kareem-medium", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: /Voice activity/ }).click();
  await expect(page.getByRole("heading", { name: "Voice activity", exact: true })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: "test-results/voice-admin.png", fullPage: true });
});

test("Arabic mobile chat stays within the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/chat/");
  await page.evaluate(() => localStorage.setItem("jsm.language", "ar"));
  // The initialization script sets English; switch after reload using the shared event.
  await page.evaluate(() => window.dispatchEvent(new Event("jsm:preferences")));
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByRole("button", { name: "JSM صوت", exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "test-results/voice-mobile-ar.png", fullPage: true });
});
