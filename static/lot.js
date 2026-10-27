// Parking lot map
const LOT = (() => {
  const S = 24;
  const BAND = 3.5;
  const AISLE = 4.5;
  const NS = "http://www.w3.org/2000/svg";

  const spots = [];
  for (let i = 0; i < 5; i++) spots.push(["A" + (1 + i), 5 + i * 2, 0, 7 + i * 2, 3.5]);
  for (let i = 0; i < 4; i++) spots.push(["A" + (6 + i), 16.5, 6 + i * 2, 20, 8 + i * 2]);
  for (let i = 0; i < 5; i++) spots.push(["A" + (10 + i), 13 - i * 2, 16.5, 15 - i * 2, 20]);
  for (let i = 0; i < 4; i++) spots.push(["A" + (15 + i), 0, 12 - i * 2, 3.5, 14 - i * 2]);

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    parent.appendChild(node);
    return node;
  }

  function render(container) {
    const svg = el("svg", { viewBox: "0 0 480 480", role: "group", "aria-label": "Parking lot layout" }, container);
    el("rect", { class: "band", x: 0, y: 0, width: 20 * S, height: 20 * S, rx: 18 }, svg);
    el("rect", { class: "asphalt", x: BAND * S, y: BAND * S, width: (20 - 2 * BAND) * S, height: (20 - 2 * BAND) * S, rx: 6 }, svg);
    const lane = BAND + AISLE / 2;
    el("rect", { class: "lane", x: lane * S, y: lane * S, width: (20 - 2 * lane) * S, height: (20 - 2 * lane) * S, rx: 14 }, svg);
    const island = BAND + AISLE;
    el("rect", { class: "island", x: island * S, y: island * S, width: (20 - 2 * island) * S, height: (20 - 2 * island) * S, rx: 14 }, svg);
    el("text", { class: "island-label", x: 10 * S, y: 10 * S - 6, "text-anchor": "middle", "dominant-baseline": "central" }, svg).textContent = "LOT A";
    el("text", { class: "island-sub", x: 10 * S, y: 10 * S + 12, "text-anchor": "middle", "dominant-baseline": "central" }, svg).textContent = "DLSL";

    const rects = {};
    const current = {};
    const geometry = {};
    for (const [id, x1, y1, x2, y2] of spots) {
      geometry[id] = [x1 * S, y1 * S, x2 * S, y2 * S];
      rects[id] = el("rect", {
        class: "spot", "data-spot": id, tabindex: 0, role: "button", "aria-label": "Spot " + id,
        x: x1 * S, y: y1 * S, width: (x2 - x1) * S, height: (y2 - y1) * S, rx: 6,
      }, svg);
      const label = el("text", { class: "spot-label", x: ((x1 + x2) / 2) * S, y: ((y1 + y2) / 2) * S, "text-anchor": "middle", "dominant-baseline": "central" }, svg);
      label.textContent = id;
    }

    const links = el("g", { class: "viol-links", "aria-hidden": "true" }, svg);

    // Keyboard support
    svg.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.dataset && e.target.dataset.spot) {
        e.preventDefault();
        e.target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      }
    });

    return {
      ids: spots.map((s) => s[0]),
      update(states) {
        container.classList.remove("is-loading");
        for (const id in rects) {
          const state = states[id] || "";
          const rect = rects[id];
          const changed = current[id] !== undefined && current[id] !== state;
          current[id] = state;
          rect.classList.remove("available", "taken", "violation", "changed");
          if (state) rect.classList.add(state);
          if (changed) {
            void rect.getBBox();
            rect.classList.add("changed");
          }
          rect.setAttribute("aria-label", "Spot " + id + (state ? ", " + state : ""));
        }
      },
      select(id) {
        for (const key in rects) rects[key].classList.toggle("is-selected", key === id);
      },
      groups(list) {
        links.replaceChildren();
        for (const group of list) {
          const boxes = group.map((id) => geometry[id]).filter(Boolean);
          if (boxes.length < 2) continue;
          const pad = 4;
          const x1 = Math.min(...boxes.map((b) => b[0])) - pad;
          const y1 = Math.min(...boxes.map((b) => b[1])) - pad;
          const x2 = Math.max(...boxes.map((b) => b[2])) + pad;
          const y2 = Math.max(...boxes.map((b) => b[3])) + pad;
          el("rect", { class: "viol-link", x: x1, y: y1, width: x2 - x1, height: y2 - y1, rx: 9 }, links);
        }
      },
    };
  }

  return { render };
})();
