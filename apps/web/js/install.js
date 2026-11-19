// 웹앱 설치(PWA): 서비스 워커 등록, 설치 버튼
export function setupInstall() {
  const btn = document.getElementById("install");
  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (!btn || standalone) return;
  let deferred = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferred = e;
    btn.hidden = false;
  });
  window.addEventListener("appinstalled", () => { btn.hidden = true; deferred = null; });
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  if (ios) btn.hidden = false;
  btn.onclick = async () => {
    if (deferred) {
      deferred.prompt();
      await deferred.userChoice.catch(() => null);
      deferred = null;
      btn.hidden = true;
      return;
    }
    const tip = document.getElementById("installTip");
    tip.hidden = !tip.hidden;
  };
}
