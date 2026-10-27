// Park Patrol UI helpers
const UI = (() => {
  const ICONS = "/static/icons.svg";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function icon(name, cls = "icon") {
    return `<svg class="${cls}" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`;
  }

  // Toasts
  let region;
  function toast(message, { icon: name = "check", tone = "", duration = 3200 } = {}) {
    if (!region) {
      region = document.createElement("div");
      region.className = "toasts";
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      document.body.appendChild(region);
    }
    const el = document.createElement("div");
    el.className = "toast" + (tone ? " toast--" + tone : "");
    el.innerHTML = `<span class="toast__icon">${icon(name)}</span><span></span>`;
    el.lastElementChild.textContent = message;
    region.appendChild(el);
    while (region.children.length > 3) region.firstElementChild.remove();
    setTimeout(() => {
      el.classList.add("is-leaving");
      el.addEventListener("animationend", () => el.remove(), { once: true });
    }, duration);
  }

  function soon(feature) {
    toast((feature || "This feature") + " is coming soon", { icon: "clock" });
  }

  // Counters
  function count(el, value, { suffix = "" } = {}) {
    if (!el) return;
    const target = Number(value);
    const from = Number(el.dataset.value ?? NaN);
    el.dataset.value = target;
    el.classList.remove("skeleton");
    if (Number.isNaN(from) || reduceMotion || from === target) {
      el.textContent = target + suffix;
      return;
    }
    const start = performance.now();
    const dur = 600;
    (function frame(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(from + (target - from) * eased) + suffix;
      if (t < 1) requestAnimationFrame(frame);
    })(start);
    el.classList.remove("value-pop");
    void el.offsetWidth;
    el.classList.add("value-pop");
  }

  // Sheets
  let lastFocus = null;
  const sheet = {
    open(id) {
      const el = document.getElementById(id);
      if (!el) return;
      lastFocus = document.activeElement;
      el.hidden = false;
      requestAnimationFrame(() => {
        el.classList.add("is-open");
        const focusable = el.querySelector(".sheet__panel button, .sheet__panel a");
        if (focusable) focusable.focus({ preventScroll: true });
      });
      document.body.style.overflow = "hidden";
    },
    close(id) {
      const el = typeof id === "string" ? document.getElementById(id) : id;
      if (!el || !el.classList.contains("is-open")) return;
      el.classList.remove("is-open");
      document.body.style.overflow = "";
      el.dispatchEvent(new CustomEvent("sheet:close"));
      if (lastFocus) lastFocus.focus({ preventScroll: true });
    },
  };

  // Menus
  function closeMenus(except) {
    document.querySelectorAll(".menu.is-open").forEach((m) => {
      if (m === except) return;
      m.classList.remove("is-open");
      const btn = m.parentElement.querySelector("[data-menu]");
      if (btn) btn.setAttribute("aria-expanded", "false");
    });
  }

  // Event handlers
  document.addEventListener("click", (e) => {
    const soonBtn = e.target.closest("[data-soon]");
    if (soonBtn) {
      e.preventDefault();
      soon(soonBtn.dataset.soon);
      closeMenus();
      return;
    }

    const menuBtn = e.target.closest("[data-menu]");
    if (menuBtn) {
      const menu = menuBtn.parentElement.querySelector(".menu");
      const open = !menu.classList.contains("is-open");
      closeMenus(menu);
      menu.classList.toggle("is-open", open);
      menuBtn.setAttribute("aria-expanded", String(open));
      return;
    }
    if (!e.target.closest(".menu")) closeMenus();

    if (e.target.closest("[data-drawer-open]")) document.body.classList.add("drawer-open");
    if (e.target.closest("[data-drawer-close]")) document.body.classList.remove("drawer-open");
    if (e.target.closest(".sidebar a[href^='#']")) document.body.classList.remove("drawer-open");

    const sheetClose = e.target.closest("[data-sheet-close]");
    if (sheetClose) sheet.close(sheetClose.closest(".sheet"));
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeMenus();
    document.body.classList.remove("drawer-open");
    document.querySelectorAll(".sheet.is-open").forEach((s) => sheet.close(s));
  });

  // Scroll state
  const elevated = document.querySelectorAll(".js-elevate");
  const onScroll = () => elevated.forEach((el) => el.classList.toggle("is-scrolled", window.scrollY > 4));
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  // Reveal
  const reveals = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      }
    }, { rootMargin: "0px 0px -8% 0px" });
    reveals.forEach((el, i) => {
      if (!el.style.getPropertyValue("--delay")) el.style.setProperty("--delay", Math.min(i, 6) * 60 + "ms");
      io.observe(el);
    });
  } else {
    reveals.forEach((el) => el.classList.add("is-in"));
  }

  // Scroll spy
  const spyLinks = [...document.querySelectorAll(".js-spy a[href^='#']")];
  const sections = [...new Set(spyLinks.map((a) => a.getAttribute("href")))]
    .map((h) => document.querySelector(h))
    .filter(Boolean);
  function setActive(id) {
    spyLinks.forEach((a) => {
      const on = a.getAttribute("href") === "#" + id;
      a.classList.toggle("is-active", on);
      if (on) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    });
  }
  if (sections.length) setActive(sections[0].id);
  if (sections.length && "IntersectionObserver" in window) {
    const visible = new Map();
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((en) => visible.set(en.target.id, en.isIntersecting ? en.intersectionRatio : 0));
      if (window.scrollY > 0 && window.innerHeight + window.scrollY >= document.body.scrollHeight - 4) {
        setActive(sections[sections.length - 1].id);
        return;
      }
      const best = sections.find((s) => visible.get(s.id) > 0);
      if (best) setActive(best.id);
    }, { rootMargin: "-20% 0px -55% 0px", threshold: [0, .25, .5, 1] });
    sections.forEach((s) => spy.observe(s));
  }

  // Segmented controls
  function syncSegmented(group) {
    const thumb = group.querySelector(".segmented__thumb");
    const active = group.querySelector("[aria-pressed='true']");
    if (!thumb || !active) return;
    thumb.style.width = active.offsetWidth + "px";
    thumb.style.transform = `translateX(${active.offsetLeft - 3}px)`;
  }
  document.querySelectorAll(".segmented").forEach((group) => {
    group.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      group.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
      syncSegmented(group);
      group.dispatchEvent(new CustomEvent("change", { detail: btn.dataset.value }));
    });
    syncSegmented(group);
  });
  const resyncAll = () => document.querySelectorAll(".segmented").forEach(syncSegmented);
  window.addEventListener("resize", resyncAll);
  if (document.fonts) document.fonts.ready.then(resyncAll);

  // Bay lamps
  function lamps(container, ids) {
    const els = {};
    const current = {};
    container.classList.add("is-loading");
    container.replaceChildren(...ids.map((id) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "lamp";
      btn.dataset.spot = id;
      btn.innerHTML = '<span class="lamp__light" aria-hidden="true"></span><span class="lamp__id"></span><span class="lamp__meta"></span>';
      btn.querySelector(".lamp__id").textContent = id;
      btn.setAttribute("aria-label", "Spot " + id);
      els[id] = btn;
      return btn;
    }));
    return {
      update(states, meta = {}, words = {}) {
        container.classList.remove("is-loading");
        for (const id of ids) {
          const state = states[id] || "";
          const el = els[id];
          const changed = current[id] !== undefined && current[id] !== state;
          current[id] = state;
          el.classList.remove("available", "taken", "violation", "changed");
          if (state) el.classList.add(state);
          if (changed && !reduceMotion) { void el.offsetWidth; el.classList.add("changed"); }
          el.querySelector(".lamp__meta").textContent = meta[id] || "";
          el.setAttribute("aria-label", "Spot " + id + ", " + (words[state] || state || "no data"));
        }
      },
      select(id) {
        for (const key in els) els[key].classList.toggle("is-selected", key === id);
      },
    };
  }

  // Time formatting
  function ago(seconds) {
    if (seconds < 5) return "just now";
    if (seconds < 60) return Math.round(seconds) + " s ago";
    if (seconds < 3600) return Math.round(seconds / 60) + " min ago";
    return Math.round(seconds / 3600) + " h ago";
  }

  return { toast, soon, count, sheet, icon, ago, lamps };
})();
