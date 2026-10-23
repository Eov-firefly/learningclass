import test from "node:test";
import assert from "node:assert/strict";
import {
  distanceKm,
  scoreDistance,
  selectPlaces,
  totalScore,
  localDate,
  validSave,
  streak,
  PLACES,
} from "../src/game.js";
test("great-circle distance handles same points, known route, date line and antipodes", () => {
  assert.equal(distanceKm({ lat: 0, lng: 0 }, { lat: 0, lng: 0 }), 0);
  assert.ok(
    Math.abs(
      distanceKm(
        { lat: 51.5074, lng: -0.1278 },
        { lat: 40.7128, lng: -74.006 },
      ) - 5570,
    ) < 15,
  );
  assert.ok(
    Math.abs(distanceKm({ lat: 0, lng: 179 }, { lat: 0, lng: -179 }) - 222.39) <
      1,
  );
  assert.ok(
    Math.abs(distanceKm({ lat: 0, lng: 0 }, { lat: 0, lng: 180 }) - 20015.09) <
      1,
  );
});
test("score is bounded, monotonic, full within tolerance, zero near antipode", () => {
  assert.equal(scoreDistance(0), 100);
  assert.equal(scoreDistance(22), 100);
  assert.equal(scoreDistance(20015), 0);
  let previous = 100;
  for (let d = 0; d < 21000; d += 10) {
    const s = scoreDistance(d);
    assert.ok(s >= 0 && s <= 100 && s <= previous);
    previous = s;
  }
});
test("daily set deterministic, unique, varies across dates and respects categories", () => {
  assert.deepEqual(selectPlaces("2026-10-23"), selectPlaces("2026-10-23"));
  assert.notDeepEqual(selectPlaces("2026-10-23"), selectPlaces("2026-10-24"));
  assert.equal(new Set(selectPlaces("2026-10-23").map((p) => p.id)).size, 5);
  assert.ok(
    selectPlaces("practice", "landmark").every(
      (p) => p.category === "landmark",
    ),
  );
});
test("weighted total is 1000 and late rounds count triple", () => {
  assert.equal(
    totalScore(Array.from({ length: 5 }, () => ({ score: 100 }))),
    1000,
  );
  assert.equal(
    totalScore([
      { score: 0 },
      { score: 0 },
      { score: 0 },
      { score: 0 },
      { score: 100 },
    ]),
    300,
  );
});
test("saved daily validates date and rejects malformed round data", () => {
  const ids = selectPlaces("2026-10-23").map((p) => p.id);
  const s = { date: "2026-10-23", places: ids, rounds: [] };
  assert.ok(validSave(s, "2026-10-23"));
  assert.ok(!validSave(s, "2026-10-24"));
  assert.ok(!validSave({ ...s, places: [999, 1, 2, 3, 4] }, s.date));
  assert.ok(
    !validSave(
      {
        ...s,
        rounds: [
          {
            placeId: ids[0],
            score: 999,
            distance: 0,
            guess: { lat: 0, lng: 0 },
          },
        ],
      },
      s.date,
    ),
  );
  assert.ok(
    !validSave(
      {
        ...s,
        rounds: [
          {
            placeId: ids[0],
            score: 100,
            distance: 0,
            guess: { lat: 100, lng: 0 },
          },
        ],
      },
      s.date,
    ),
  );
});
test("local date and streak work across months and allow yesterday before today completed", () => {
  assert.equal(localDate(new Date(2026, 9, 3)), "2026-10-03");
  const h = { "2026-09-30": {}, "2026-10-01": {}, "2026-10-02": {} };
  assert.equal(streak(h, "2026-10-03"), 3);
  assert.equal(streak(h, "2026-10-04"), 0);
});
test("question bank has unique valid geographic targets and enough in each category", () => {
  assert.equal(PLACES.length, 30);
  for (const p of PLACES) {
    assert.ok(Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180);
    assert.ok(p.story && p.name);
  }
  assert.ok(PLACES.filter((p) => p.category === "landmark").length >= 5);
});
