import "./style.css";
import { Globe } from "./globe.js";
import {
  PLACES,
  WEIGHTS,
  localDate,
  selectPlaces,
  distanceKm,
  scoreDistance,
  totalScore,
  validSave,
  streak,
} from "./game.js";
const icons = {
  globe: "◎",
  daily: "◈",
  practice: "⌖",
  history: "◷",
  help: "?",
  arrow: "↗",
};
const $ = (s) => document.querySelector(s);
function read(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}
let storageWarning = false;
function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    storageWarning = true;
    toast("浏览器存储不可用，本次成绩仅保留在当前页面");
  }
}
const day = localDate();
let history = read("atlas-history", {});
if (!history || typeof history !== "object" || Array.isArray(history))
  history = {};
let saved = read("atlas-daily", null);
let state = {
  mode: "daily",
  places: selectPlaces(day),
  rounds: [],
  phase: "guess",
  guess: null,
};
if (validSave(saved, day)) {
  state.places = saved.places.map((id) => PLACES[id]);
  state.rounds = saved.rounds;
  state.phase = saved.rounds.length === 5 ? "summary" : "guess";
}
let practiceCategory = "all";
$("#app").innerHTML =
  `<aside class="rail"><a class="brand" href="#" aria-label="Atlas Play 首页"><span class="brand-mark">a<span>·</span></span></a><div class="rail-links"><button class="nav-btn active" data-nav="daily" aria-label="每日挑战">${icons.daily}<span>每日</span></button><button class="nav-btn" data-nav="practice" aria-label="练习模式">${icons.practice}<span>练习</span></button><button class="nav-btn" data-nav="history" aria-label="历史成绩">${icons.history}<span>记录</span></button></div><button class="help-btn" aria-label="游戏说明">?</button></aside><main><header><div class="wordmark">ATLAS <span>PLAY</span><small>指尖环游</small></div><div class="header-right"><span class="local-badge"><i></i> 每天，发现一点世界</span><button class="streak" title="连续完成每日挑战的天数">♨ <b id="streak">0</b><span>天</span></button></div></header><section class="game-layout"><div class="world-panel"><div class="world-heading"><span class="eyebrow">A LITTLE CURIOSITY. A WHOLE WORLD.</span><h1>世界很大，<br>凭直觉去<span>探索。</span></h1><p>五个地点，一颗星球。你对世界的了解，<br>比想象中更多一点。</p></div><div class="globe-wrap"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div id="globe"></div><div class="globe-tag"><i></i> LIVE EXPLORATION <span>地球 · EARTH</span></div><div class="zoom-tools"><button id="zoom-in" aria-label="放大地球">+</button><button id="zoom-out" aria-label="缩小地球">−</button><button id="reset-view" aria-label="重置视角">⌾</button></div><div class="globe-hint"><span>↔ 拖动旋转</span><span>⊕ 滚动缩放</span><span>⌖ 点击标点</span></div></div><div class="world-footer"><span>无需远行，也能遇见世界。</span><span>22 KM 内 · 满分落点 ↗</span></div></div><aside class="play-panel"><div id="card"></div><div class="below-card"><span>✧</span><p>不是每一次探索，都需要知道答案。<br><strong>猜一猜，也是认识世界的开始。</strong></p></div></aside></section><footer><span>© 2026 Atlas Play · 原创地理探索小游戏</span><button id="rules-footer">规则与说明 ↗</button><span>为好奇心而造 <span class="tiny-star">✳</span></span></footer></main><dialog id="modal"><button class="modal-close" aria-label="关闭">×</button><div id="modal-content"></div></dialog><div id="toast" role="status"></div>`;
const globe = new Globe($("#globe"), (p) => pick(p));
function persist() {
  if (state.mode === "daily")
    write("atlas-daily", {
      date: day,
      places: state.places.map((p) => p.id),
      rounds: state.rounds,
    });
}
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("#toast").classList.remove("show"), 3200);
}
function pick(p) {
  if (state.phase !== "guess") return;
  state.guess = p;
  globe.guess(p);
  const coords = $("#coords");
  if (coords)
    coords.textContent = `${Math.abs(p.lat).toFixed(2)}° ${p.lat >= 0 ? "N" : "S"}  /  ${Math.abs(p.lng).toFixed(2)}° ${p.lng >= 0 ? "E" : "W"}`;
  const btn = $("#confirm");
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = "确认我的落点 <span>↗</span>";
  }
  $("#pick-status")?.classList.add("selected");
}
function render() {
  const n = state.rounds.length;
  globe.enabled = state.phase === "guess";
  $("#streak").textContent = streak(history);
  document
    .querySelectorAll("[data-nav]")
    .forEach((b) => b.classList.toggle("active", b.dataset.nav === state.mode));
  if (state.phase === "summary") {
    renderSummary();
    return;
  }
  const result = state.phase === "reveal" ? state.rounds.at(-1) : null;
  const index = result ? n - 1 : n;
  const place = state.places[index];
  const points = totalScore(state.rounds);
  $("#card").innerHTML =
    `<div class="card-header"><span class="eyebrow">${state.mode === "daily" ? "THE DAILY FIVE" : "PRACTICE SESSION"}</span><span class="edition">${state.mode === "daily" ? day.replaceAll("-", ".") : "自由练习"}</span></div><div class="card-title"><h2>${state.mode === "daily" ? "今日探索" : "练习时刻"}</h2><span class="pill">${index + 1} / 5</span></div><div class="progress">${WEIGHTS.map((w, i) => `<div class="step ${i < index ? "done" : ""} ${i === index ? "current" : ""}"><span>${i < index ? "✓" : String(i + 1).padStart(2, "0")}</span><i></i><small>×${w}</small></div>`).join("")}</div><div class="question-label"><span>${result ? "这一站，你抵达了" : "在地球上找到"}</span><span>${["启程", "热身", "深入", "远行", "终章"][index]} · ×${WEIGHTS[index]} 分</span></div><h3 class="place-name">${place.name}</h3><p class="question-sub">${result ? place.region : "相信你的空间直觉，找到它的位置。"}</p>${result ? `<div class="result-box"><div><span>距离目标</span><strong>${Math.round(result.distance).toLocaleString()}<small> km</small></strong></div><div><span>本题得分</span><strong class="lime">${result.score}<small> / 100</small></strong></div></div><div class="story"><span>✧ 一点新发现</span><p>${place.story}</p></div><button class="primary" id="next">${n === 5 ? "查看探索报告" : "继续下一站"} <span>→</span></button><div class="legend"><span><i class="lime-dot"></i>你的落点</span><span><i class="white-dot"></i>目标位置</span></div>` : `<div class="pick-box" id="pick-status"><span class="crosshair">⌖</span><div><strong>你的目的地，由你标记</strong><span id="coords">在左侧地球上点击，放下你的标记</span></div></div><button class="primary" id="confirm" disabled>先在地球上选择位置 <span>↗</span></button><details class="coordinate-input"><summary>也可以用经纬度定位</summary><form id="coordinate-form"><label>纬度<input name="lat" type="number" min="-90" max="90" step="any" placeholder="−90 至 90" required></label><label>经度<input name="lng" type="number" min="-180" max="180" step="any" placeholder="−180 至 180" required></label><button type="submit">标点</button></form></details><div class="micro-copy">不计时，慢慢找。每一次猜测都有收获。</div>`}<div class="card-bottom"><div><span>本次总分</span><strong>${String(points).padStart(3, "0")}<small> / 1,000</small></strong></div><div class="score-spark">▂ ▄ ▃ ▆ ▅ █</div></div>`;
  $("#confirm")?.addEventListener("click", submit);
  $("#next")?.addEventListener("click", () => {
    state.phase = n === 5 ? "summary" : "guess";
    state.guess = null;
    globe.reset();
    render();
  });
  $("#coordinate-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    pick({ lat: Number(data.get("lat")), lng: Number(data.get("lng")) });
  });
}
function submit() {
  if (!state.guess || state.phase !== "guess") return;
  const place = state.places[state.rounds.length];
  const distance = distanceKm(state.guess, place);
  const round = {
    placeId: place.id,
    guess: { ...state.guess },
    distance,
    score: scoreDistance(distance),
  };
  state.rounds.push(round);
  state.phase = "reveal";
  persist();
  if (state.rounds.length === 5 && state.mode === "daily") {
    history[day] = { score: totalScore(state.rounds), rounds: state.rounds };
    write("atlas-history", history);
  }
  globe.reveal(round.guess, place);
  render();
}
function renderSummary() {
  const score = totalScore(state.rounds);
  $("#card").innerHTML =
    `<div class="card-header"><span class="eyebrow">EXPLORATION COMPLETE</span><span class="edition">${state.mode === "daily" ? "每日挑战" : "练习模式"}</span></div><div class="summary-orbit">✳</div><h2 class="summary-title">世界，又熟悉了一点。</h2><p class="summary-sub">${score >= 800 ? "你是当之无愧的世界探索家！" : score >= 500 ? "走过的每一站，都让世界更近。" : "未知的地方，就是下一次出发的理由。"}</p><div class="big-score">${score}<span>/ 1,000</span></div><div class="summary-list">${state.rounds.map((r, i) => `<button class="summary-row" data-review="${i}" aria-label="回顾${state.places[i].name}"><span class="round-number">0${i + 1}</span><div><b>${state.places[i].name}</b><small>${Math.round(r.distance).toLocaleString()} km · ×${WEIGHTS[i]}</small></div><strong>${r.score * WEIGHTS[i]}<small> / ${100 * WEIGHTS[i]}</small></strong><span>↗</span></button>`).join("")}</div><button class="primary" id="share">分享我的探索 <span>↗</span></button><button class="secondary" id="practice-more">再来一次自由练习 →</button><p class="micro-copy">${storageWarning ? "存储不可用，请保留本页以免成绩丢失。" : state.mode === "daily" ? "今日成绩已保存在此浏览器，明天再见。" : "练习成绩不计入每日记录。"}</p>`;
  $("#share").onclick = share;
  $("#practice-more").onclick = () => startPractice();
  document.querySelectorAll("[data-review]").forEach(
    (b) =>
      (b.onclick = () => {
        const i = Number(b.dataset.review);
        globe.reveal(state.rounds[i].guess, state.places[i]);
        toast(`${state.places[i].name} · ${state.places[i].region}`);
      }),
  );
}
async function share() {
  const text = `Atlas Play · ${state.mode === "daily" ? day : "自由练习"}\n${totalScore(state.rounds)} / 1000\n${state.rounds.map((r) => (r.score >= 90 ? "🟩" : r.score >= 60 ? "🟨" : r.score >= 30 ? "🟧" : "⬜")).join("")}\n五个地点，一颗星球。`;
  try {
    await navigator.clipboard.writeText(text);
    toast("成绩已复制，粘贴给朋友吧！");
  } catch {
    modal(
      `<h2>分享探索成绩</h2><p>复制下方文字，分享给朋友。</p><textarea readonly id="share-text"></textarea>`,
    );
    $("#share-text").value = text;
    $("#share-text").select();
  }
}
function modal(content) {
  $("#modal-content").innerHTML = content;
  if (!$("#modal").open) $("#modal").showModal();
}
function startPractice(category = "all") {
  practiceCategory = category;
  state = {
    mode: "practice",
    places: selectPlaces(`${Date.now()}-${Math.random()}`, category),
    rounds: [],
    phase: "guess",
    guess: null,
  };
  globe.reset();
  render();
  $("#modal").close();
}
function practiceModal() {
  modal(
    `<span class="eyebrow">KEEP EXPLORING</span><h2>下一站，随你选择。</h2><p>每次随机抽取五个地点，无限次练习，不影响每日成绩。</p><div class="mode-cards"><button data-category="all"><span>◎</span><b>整个世界</b><small>城市与地标，意料之外的相遇</small></button><button data-category="city"><span>▥</span><b>世界城市</b><small>从熟悉的名字，找到真实的位置</small></button><button data-category="landmark"><span>△</span><b>自然与人文</b><small>山峰、遗址与值得记住的地方</small></button></div>`,
  );
  document.querySelectorAll("[data-category]").forEach(
    (b) =>
      (b.onclick = () => {
        if (
          state.mode === "practice" &&
          state.rounds.length > 0 &&
          state.rounds.length < 5 &&
          !confirm("开始新练习将放弃当前练习，是否继续？")
        )
          return;
        startPractice(b.dataset.category);
      }),
  );
}
function showHistory() {
  const entries = Object.entries(history)
    .filter(
      ([date, v]) =>
        /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(v?.score),
    )
    .sort((a, b) => b[0].localeCompare(a[0]));
  modal(
    `<span class="eyebrow">YOUR FIELD NOTES</span><h2>每一天，都算数。</h2><p>每日探索记录仅保存在当前浏览器，清除浏览器数据会删除记录。</p><div class="history-list">${
      entries.length
        ? entries
            .slice(0, 30)
            .map(
              ([date, v]) =>
                `<div class="history-row"><span>${date}</span><strong>${v.score}<small> / 1,000</small></strong></div>`,
            )
            .join("")
        : '<div class="empty">⌖<h3>你的旅行手记，等待第一笔。</h3><p>完成今天的五个地点，记录就会出现在这里。</p></div>'
    }</div>`,
  );
}
function rules() {
  modal(
    `<span class="eyebrow">A QUICK FIELD GUIDE</span><h2>凭直觉，找到世界。</h2><ol class="rules"><li><b>找到地点</b><p>拖动地球旋转，滚轮或双指缩放。点击地球标记位置，确认后提交。也可以输入经纬度。</p></li><li><b>越近，越精彩</b><p>按球面距离计分，22公里内为100分，越远分数越低。采用本站原创平方衰减曲线，不含国家奖励，不计时。</p></li><li><b>五站，一千分</b><p>五题权重为1、1、2、3、3倍。每题确认后不可重答；揭晓后可看到正确位置与地点小知识。</p></li><li><b>每天有新发现</b><p>以本地日期确定每日题目；练习模式不限次数。当前题库有${PLACES.length}个城市与地标。</p></li></ol><p class="notice">这是原创独立原型，与 MapTap 无关联。无账号、联网排名或付费功能；请勿将本地成绩当作可信竞技记录。地图为概化地理示意，不用于边界或导航判断。</p>`,
  );
}
document.querySelectorAll("[data-nav]").forEach(
  (b) =>
    (b.onclick = () => {
      if (b.dataset.nav === "practice") practiceModal();
      else if (b.dataset.nav === "history") showHistory();
      else {
        const current = read("atlas-daily", null);
        state = {
          mode: "daily",
          places: selectPlaces(day),
          rounds: [],
          phase: "guess",
          guess: null,
        };
        if (validSave(current, day)) {
          state.places = current.places.map((id) => PLACES[id]);
          state.rounds = current.rounds;
          state.phase = current.rounds.length === 5 ? "summary" : "guess";
        }
        globe.reset();
        render();
      }
    }),
);
$(".brand").onclick = (e) => {
  e.preventDefault();
  document.querySelector('[data-nav="daily"]').click();
};
$(".help-btn").onclick = rules;
$("#rules-footer").onclick = rules;
$(".modal-close").onclick = () => $("#modal").close();
$("#modal").addEventListener("click", (e) => {
  if (e.target === $("#modal")) {
    const r = $("#modal").getBoundingClientRect();
    if (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    )
      $("#modal").close();
  }
});
$("#zoom-in").onclick = () => globe.zoom(0.8);
$("#zoom-out").onclick = () => globe.zoom(1.25);
$("#reset-view").onclick = () => {
  globe.reset();
  if (state.phase === "reveal") {
    globe.reveal(
      state.rounds.at(-1).guess,
      state.places[state.rounds.length - 1],
    );
  } else if (state.guess) globe.guess(state.guess);
};
render();
