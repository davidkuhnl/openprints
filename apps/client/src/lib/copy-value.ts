const INIT_FLAG = "__openprintsCopyValueInitialized";
const CLS_BTN = "copy-value__btn";
const COPIED_CLASS = "copy-value__btn--copied";
const COPIED_DURATION_MS = 1500;

declare global {
  interface Window {
    __openprintsCopyValueInitialized?: boolean;
  }
}

export function initCopyValueButtons(): void {
  if (typeof window === "undefined") return;
  if (window[INIT_FLAG]) return;
  window[INIT_FLAG] = true;

  document.body.addEventListener("click", (e) => {
    const target = e.target instanceof Element ? e.target : null;
    const btn = target?.closest(`.${CLS_BTN}`) ?? null;
    if (!btn) return;
    if (btn instanceof HTMLButtonElement && btn.disabled) return;

    let value = btn.getAttribute("data-copy-value");
    if (value == null) value = "";

    if (!value) {
      const sourceSelector = btn.getAttribute("data-copy-source");
      if (sourceSelector) {
        const sourceNode = document.querySelector(sourceSelector);
        if (
          sourceNode instanceof HTMLInputElement ||
          sourceNode instanceof HTMLTextAreaElement
        ) {
          value = sourceNode.value;
        } else if (sourceNode) {
          value = sourceNode.textContent ?? "";
        }
      }
    }

    if (!value) return;

    const prevLabel = btn.getAttribute("aria-label") || "Copy";
    navigator.clipboard
      .writeText(value)
      .then(() => {
        btn.classList.add(COPIED_CLASS);
        btn.setAttribute("aria-label", "Copied!");
        setTimeout(() => {
          btn.classList.remove(COPIED_CLASS);
          btn.setAttribute("aria-label", prevLabel);
        }, COPIED_DURATION_MS);
      })
      .catch(() => {});
  });
}
