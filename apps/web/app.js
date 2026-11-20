// LG 빌트인 가상 리모델링 웹앱 (빌드 없음). 화면: 내 집 스캔(#/), 새 스캔(#/new), 방문 신청(#/r), 기사(#/t), 리모델링(#/c/:pid), 내 집(#/me), 기사 관리(#/admin)
// #/ 는 꾸미던 집이 있으면 그 집으로 바로 간다. 방문 신청 같은 화면에 다녀와도 다시 올릴 필요가 없다.
import { cleanup, lastHome, homeHref } from "./js/core.js";
import { selfScan, home, technicianHome, technician } from "./js/pages.js";
import { customer } from "./js/remodel.js";
import { setupInstall } from "./js/install.js";
import { mountAccount, myHomes, adminPage, techGate } from "./js/account.js";

function route() {
  // 한 화면의 정리 함수가 실패해도 나머지(저장 막대 타이머 등)는 꼭 정리한다
  cleanup.splice(0).forEach((f) => { try { f(); } catch { /* 이미 사라진 화면 */ } });
  const [path] = location.hash.slice(1).split("?");
  const parts = path.split("/").filter(Boolean);
  document.body.dataset.route = parts[0] || "home";
  if (parts[0] === "t") return techGate(() => (parts[1] ? technician(parts[1]) : technicianHome()));
  if (parts[0] === "me") return myHomes();
  if (parts[0] === "admin") return adminPage();
  if (parts[0] === "c" && parts[1]) return customer(parts[1]);
  if (parts[0] === "r") return home();
  if (parts[0] !== "new" && lastHome()) { location.replace(homeHref()); return; }
  document.body.dataset.route = "home";
  return selfScan();
}
window.addEventListener("hashchange", route);
route();
setupInstall();
mountAccount(document.getElementById("acct"));
