// LG 빌트인 가상 리모델링 웹앱 (빌드 없음). 화면: 내 집 스캔(#/), 방문 신청(#/r), 기사(#/t), 리모델링(#/c/:pid)
import { cleanup } from "./js/core.js";
import { selfScan, home, technicianHome, technician } from "./js/pages.js";
import { customer } from "./js/remodel.js";
import { setupInstall } from "./js/install.js";

function route() {
  cleanup.splice(0).forEach((f) => f());
  const [path] = location.hash.slice(1).split("?");
  const parts = path.split("/").filter(Boolean);
  document.body.dataset.route = parts[0] || "home";
  if (parts[0] === "t") return parts[1] ? technician(parts[1]) : technicianHome();
  if (parts[0] === "c" && parts[1]) return customer(parts[1]);
  if (parts[0] === "r") return home();
  return selfScan();
}
window.addEventListener("hashchange", route);
route();
setupInstall();
