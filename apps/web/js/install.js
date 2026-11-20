// 웹앱 설치(PWA): 서비스 워커 등록, 설치 버튼
export function setupInstall() {
  const btn = document.getElementById("install");
  if ("serviceWorker" in navigator && window.isSecureContext) {
    // 새 버전이 배포되면 새로 고침 없이 알아서 바뀌게: 서비스 워커를 자주 확인하고, 바뀌면 한 번 다시 읽는다
    const hadController = !!navigator.serviceWorker.controller;
    let reloading = false;
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (!hadController || reloading) return;
      reloading = true;
      location.reload();
    });
    navigator.serviceWorker.register("./sw.js", { updateViaCache: "none" }).then((reg) => {
      const check = () => reg.update().catch(() => {});
      document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") check(); });
      setInterval(check, 60 * 1000);
    }).catch(() => {});
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
