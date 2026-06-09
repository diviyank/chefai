// Clipboard copy for generated prompts.
// navigator.clipboard only exists in secure contexts (HTTPS/localhost); chefai is served
// over plain HTTP on the LAN, so fall back to a textarea selection + execCommand("copy").
function copyText(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const text = el.value || el.textContent;
  const btn = document.activeElement;
  const flash = (msg) => {
    if (!btn) return;
    const old = btn.textContent;
    btn.textContent = msg;
    setTimeout(() => { btn.textContent = old; }, 1500);
  };
  const fallback = () => {
    el.focus();
    el.select();
    el.setSelectionRange(0, text.length);  // mobile Safari/Firefox need an explicit range
    const ok = document.execCommand("copy");
    flash(ok ? "Copié ✓" : "Copie impossible — sélectionnez puis copiez à la main");
  };
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(() => flash("Copié ✓"), fallback);
  } else {
    fallback();
  }
}

// Cooking-mode step timer (Alpine component).
document.addEventListener("alpine:init", () => {
  Alpine.data("timer", (seconds) => ({
    remaining: seconds, running: false, handle: null,
    start() {
      if (this.running) return;
      this.running = true;
      this.handle = setInterval(() => {
        if (this.remaining > 0) this.remaining--;
        else { clearInterval(this.handle); this.running = false; }
      }, 1000);
    },
    reset() { clearInterval(this.handle); this.running = false; this.remaining = seconds; },
    get label() {
      const m = Math.floor(this.remaining / 60), s = this.remaining % 60;
      return `${m}:${String(s).padStart(2, "0")}`;
    },
  }));
});

// Keep screen awake in cooking mode (best-effort).
async function keepAwake() {
  try { if ("wakeLock" in navigator) await navigator.wakeLock.request("screen"); } catch (e) {}
}

// Offline shopping: persist tick state in localStorage keyed by list signature.
function shoppingStore(key) {
  return {
    key,
    state: JSON.parse(localStorage.getItem(key) || "{}"),
    toggle(id) { this.state[id] = !this.state[id]; localStorage.setItem(this.key, JSON.stringify(this.state)); },
    checked(id) { return !!this.state[id]; },
  };
}
