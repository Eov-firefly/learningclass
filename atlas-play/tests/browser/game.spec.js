import { test, expect } from "@playwright/test";
import { PLACES } from "../../src/game.js";
async function answer(page, { lat, lng }) {
  const details = page.locator(".coordinate-input");
  await details.locator("summary").click();
  await page.locator('[name="lat"]').fill(String(lat));
  await page.locator('[name="lng"]').fill(String(lng));
  await page.getByRole("button", { name: "标点", exact: true }).click();
  await page.locator("#confirm").click();
}
test("complete daily, reveal real answers, persist summary and share result", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.locator("#confirm")).toBeDisabled();
  for (let i = 0; i < 5; i++) {
    const name = await page.locator(".place-name").innerText();
    const p = PLACES.find((p) => p.name === name);
    await answer(page, p);
    await expect(page.locator(".result-box")).toContainText("100");
    await expect(page.locator(".story")).toContainText(p.story);
    await page.locator("#next").click();
  }
  await expect(page.locator(".big-score")).toContainText("1000");
  await page.locator("#share").click();
  await expect(page.locator("#toast")).toContainText("已复制");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "1000 / 1000",
  );
  await page.reload();
  await expect(page.locator(".big-score")).toContainText("1000");
  await page.getByRole("button", { name: "历史成绩" }).click();
  await expect(page.locator(".history-row")).toHaveCount(1);
  await expect(page.locator(".history-row")).toContainText("1000");
  expect(errors).toEqual([]);
});
test("unfinished daily resumes at next unanswered round and practice does not overwrite it", async ({
  page,
}) => {
  await page.goto("/");
  await answer(page, { lat: 0, lng: 0 });
  await page.reload();
  await expect(page.locator(".pill")).toHaveText("2 / 5");
  const name = await page.locator(".place-name").innerText();
  const before = await page.evaluate(() => localStorage.getItem("atlas-daily"));
  await page.getByRole("button", { name: "练习模式" }).click();
  await page.getByRole("button", { name: "自然与人文" }).click();
  expect(PLACES.find((p) => p.name === name)).toBeTruthy();
  const practice = await page.locator(".place-name").innerText();
  expect(PLACES.find((p) => p.name === practice).category).toBe("landmark");
  await answer(page, { lat: 1, lng: 1 });
  expect(await page.evaluate(() => localStorage.getItem("atlas-daily"))).toBe(
    before,
  );
  await page.getByRole("button", { name: "每日挑战" }).click();
  await expect(page.locator(".place-name")).toHaveText(name);
  await expect(page.locator(".pill")).toHaveText("2 / 5");
});
test("mobile globe picking, rotation, zoom, modal and layout remain functional", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.locator("canvas")).toBeVisible();
  const canvas = page.locator("canvas");
  const box = await canvas.boundingBox();
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });
  await expect(page.locator("#confirm")).toBeEnabled();
  const coords = await page.locator("#coords").innerText();
  await page.locator("#zoom-in").click();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width / 2 + 70,
    box.y + box.height / 2 + 20,
    { steps: 10 },
  );
  await page.mouse.up();
  expect(await page.locator("#coords").innerText()).toBe(coords);
  await page.locator("#confirm").click();
  await expect(page.locator(".result-box")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "游戏说明" }).click();
  await expect(page.locator("#modal")).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.locator("#modal")).not.toBeVisible();
  await page.screenshot({ path: "artifacts/mobile.png", fullPage: true });
});
test("malformed saved state is ignored rather than crashing the game", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "atlas-daily",
      '{"date":"bad","places":[999],"rounds":{}}',
    );
  });
  await page.goto("/");
  await expect(page.locator(".pill")).toHaveText("1 / 5");
  await expect(page.locator(".place-name")).not.toBeEmpty();
});
test("coordinate input keeps game playable without WebGL", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      if (String(type).includes("webgl")) return null;
      return original.call(this, type, ...args);
    };
  });
  await page.goto("/");
  await expect(page.locator(".fallback")).toContainText("无法启动三维地球");
  await answer(page, { lat: 0, lng: 0 });
  await expect(page.locator(".result-box")).toBeVisible();
});
