// 공통: API 호출, 라벨, 알림
export const $app = document.getElementById("app");
export const cleanup = [];
export const LABEL = { fit: "적합", conditional: "조건부", no_fit: "불가", unknown: "판정 불가" };
export const PURPOSE = { kitchen: "주방", living: "거실", bedroom: "침실", utility: "다용도실", other: "기타" };
export const CATEGORY = {
  refrigerator: "냉장고", freezer: "냉동고", kimchi_refrigerator: "김치냉장고", wine_cellar: "와인셀러", dishwasher: "식기세척기",
  oven: "광파오븐", microwave: "전자레인지", cooktop: "인덕션", water_purifier: "정수기",
  washer: "세탁기", dryer: "건조기", wash_tower: "워시타워", washer_dryer: "워시콤보", styler: "스타일러", shoe_care: "슈케어",
  tv: "TV", portable_tv: "스탠바이미", air_conditioner: "에어컨", air_purifier: "공기청정기", humidifier: "가습기",
  dehumidifier: "제습기", vacuum: "청소기", massage_chair: "안마의자", plant_grower: "식물재배기",
};
// 제품 서랍 위 큰 분류 (LGE.COM 메뉴 묶음과 같은 순서)
export const CATEGORY_GROUP = [
  ["kitchen", "주방", ["refrigerator", "freezer", "kimchi_refrigerator", "wine_cellar", "dishwasher", "oven", "microwave", "cooktop", "water_purifier"]],
  ["laundry", "세탁·의류", ["washer", "dryer", "wash_tower", "washer_dryer", "styler", "shoe_care"]],
  ["living", "TV·거실", ["tv", "portable_tv", "air_conditioner", "massage_chair", "plant_grower"]],
  ["air", "공기·청소", ["air_purifier", "humidifier", "dehumidifier", "vacuum"]],
];
export const DIM = { width: "폭", height: "높이", depth: "깊이" };
export const OBJ = { chair: "의자", table: "테이블", storage: "수납장", sofa: "소파", bed: "침대", refrigerator: "냉장고", stove: "레인지",
  sink: "싱크", washer_dryer: "세탁기", oven: "오븐", dishwasher: "식기세척기", television: "TV", toilet: "변기", bathtub: "욕조", fireplace: "벽난로", stairs: "계단" };
export const VCOLOR = { fit: "var(--fit)", conditional: "var(--cond)", no_fit: "var(--nofit)", unknown: "var(--unk)" };
export const NOTE = { clearance_unknown: "이격 정보 없음", scan_based: "스캔값 사용(실측 필요)", no_wall_in_zone: "영역에 벽 없음" };

// ---------- 공통 ----------
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
export const mm = (v) => (v == null ? "–" : `${Math.round(v).toLocaleString()}`);
// API 서버 주소. config.js에서 정한다 (비우면 웹과 같은 서버)
export const API_BASE = String(window.LGB_API || "").replace(/\/+$/, "");
export const apiUrl = (path) => (path.startsWith("/api/") ? API_BASE + path : path);
// ---------- 로그인 상태 ----------
// 웹과 API가 다른 사이트라 쿠키 대신 토큰을 Authorization 헤더로 보낸다. 서버에는 토큰 해시만 남는다.
const AUTH_KEY = "lgb.auth";
const authListeners = new Set();
let authState = (() => { try { const a = JSON.parse(localStorage.getItem(AUTH_KEY) || "null"); return a?.token ? a : null; } catch { return null; } })();
export const currentUser = () => authState?.user || null;
export const authToken = () => authState?.token || null;
export function setAuth(token, user) {
  authState = token ? { token, user } : null;
  try { authState ? localStorage.setItem(AUTH_KEY, JSON.stringify(authState)) : localStorage.removeItem(AUTH_KEY); } catch { /* 저장 못 해도 이번 창에선 로그인 유지 */ }
  authListeners.forEach((f) => f(currentUser()));
}
export const onAuth = (f) => { authListeners.add(f); return () => authListeners.delete(f); };

export async function api(path, opt = {}) {
  const headers = { ...(opt.body && !(opt.body instanceof FormData) ? { "content-type": "application/json" } : {}), ...(opt.headers || {}) };
  const tok = authToken();
  if (tok && path.startsWith("/api/")) headers.authorization = `Bearer ${tok}`;
  const r = await fetch(apiUrl(path), { ...opt, headers });
  // 토큰이 만료됐거나 계정이 정지되면 로그아웃 상태로 돌린다
  if (r.status === 401 && tok && authToken() === tok) setAuth(null);
  if (r.status === 204) return null;
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : r.statusText);
    err.status = r.status;
    throw err;
  }
  return data;
}
export const post = (p, b) => api(p, { method: "POST", body: JSON.stringify(b) });
export const put = (p, b) => api(p, { method: "PUT", body: JSON.stringify(b) });
let toastT;
export function toast(msg, err = false) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "on" + (err ? " err" : "");
  clearTimeout(toastT);
  toastT = setTimeout(() => (t.className = ""), 2800);
}
export const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };


// ---------- 내 집 기억하기: 다른 화면에 다녀와도 스캔한 집과 보던 화면을 그대로 이어 간다 ----------
// 브라우저 저장소는 막혀 있을 수 있어서(사생활 보호 창 등) 실패해도 화면은 그냥 돌아간다.
const HOME_KEY = "lgb.home", UI_KEY = (pid) => `lgb.ui.${pid}`;
const readStore = (k) => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch { return null; } };
const writeStore = (k, v) => { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, JSON.stringify(v)); } catch { /* 저장 못 해도 괜찮다 */ } };
/** 마지막으로 열어 본 집 {pid, token} 또는 null */
export const lastHome = () => { const h = readStore(HOME_KEY); return h && typeof h.pid === "string" ? h : null; };
export const rememberHome = (pid, token) => {
  const old = lastHome();
  writeStore(HOME_KEY, { pid, token: token || (old?.pid === pid ? old.token : "") });
};
export const forgetHome = (pid) => { if (!pid || lastHome()?.pid === pid) writeStore(HOME_KEY, null); };
export const homeHref = (h = lastHome()) => (h ? `#/c/${encodeURIComponent(h.pid)}${h.token ? `?t=${encodeURIComponent(h.token)}` : ""}` : "#/new");
/** 집마다 보던 화면(보기·탭·살아 보기·카메라) */
export const uiState = (pid) => readStore(UI_KEY(pid)) || {};
export const saveUiState = (pid, patch) => writeStore(UI_KEY(pid), { ...uiState(pid), ...patch });
