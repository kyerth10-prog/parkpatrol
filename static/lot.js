// Parking lot map (top view of the Lot A diorama)
// Layout, matching the camera's view: a one-way road runs up between the park
// (left) and the covered parking (right). The parking has three bays of two
// spots each, numbered A1 at the top to A6 at the bottom.
const LOT = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const W = 400;
  const H = 540;

  // Covered parking: three bays, two spots per bay
  const FRAME = { x: 292, y: 30, w: 102, h: 448 };
  const BAYS = 3;
  const BAY_H = FRAME.h / BAYS;
  const PAD = 7;
  const GAP = 6;
  const SPOT_H = (BAY_H - PAD * 2 - GAP) / 2;

  const spots = [];
  for (let bay = 0; bay < BAYS; bay++) {
    const top = FRAME.y + bay * BAY_H + PAD;
    for (let i = 0; i < 2; i++) {
      const y1 = top + i * (SPOT_H + GAP);
      spots.push(["A" + (bay * 2 + i + 1), FRAME.x + 8, y1, FRAME.x + FRAME.w - 8, y1 + SPOT_H]);
    }
  }

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    parent.appendChild(node);
    return node;
  }

  function text(parent, cls, x, y, value, extra = {}) {
    el("text", { class: cls, x, y, "text-anchor": "middle", "dominant-baseline": "central", ...extra }, parent).textContent = value;
  }

  function drawScenery(svg) {
    const defs = el("defs", {}, svg);
    const marker = el("marker", {
      id: "lot-arrow", viewBox: "0 0 10 10", refX: 5, refY: 5,
      markerWidth: 3.2, markerHeight: 3.2, orient: "auto-start-reverse",
    }, defs);
    el("path", { class: "arrow-head", d: "M0 0 L10 5 L0 10 z" }, marker);

    const g = el("g", { "aria-hidden": "true" }, svg);
    el("rect", { class: "ground", x: 0, y: 0, width: W, height: H, rx: 16 }, g);

    // Road: top lane, one-way lane up the middle, bottom lane
    el("path", { class: "road", d: "M0 0 H290 V540 H0 V478 H185 V70 H0 Z" }, g);
    el("path", { class: "road-edge", d: "M0 70 H185 V478 H0" }, g);

    // Crosswalks across the middle lane
    for (const y of [147, 388]) {
      for (let i = 0; i < 5; i++) el("rect", { class: "crosswalk", x: 196 + i * 18, y, width: 9, height: 30, rx: 1.5 }, g);
    }

    // Direction arrows (traffic flows left along the top, up the middle, right along the bottom)
    const arrow = (d) => el("path", { class: "arrow", d, "marker-end": "url(#lot-arrow)" }, g);
    arrow("M110 35 H44");
    arrow("M226 100 V58 Q226 40 208 40 H198");
    arrow("M238 384 V318");
    arrow("M182 509 H208 Q226 509 226 491 V476");
    arrow("M44 509 H110");

    // Park across the street
    el("rect", { class: "park", x: 8, y: 80, width: 168, height: 388, rx: 12 }, g);
    el("rect", { class: "gazebo", x: 66, y: 252, width: 44, height: 40, rx: 6 }, g);
    text(g, "park-label", 92, 120, "Park");

    // Covered parking frame and bay posts
    el("rect", { class: "bay-frame", x: FRAME.x, y: FRAME.y, width: FRAME.w, height: FRAME.h, rx: 8 }, g);
    for (let bay = 1; bay < BAYS; bay++) {
      const y = FRAME.y + bay * BAY_H;
      el("line", { class: "bay-post", x1: FRAME.x, y1: y, x2: FRAME.x + FRAME.w, y2: y }, g);
    }
    text(g, "lot-label", FRAME.x + FRAME.w / 2, 15, "LOT A");
  }

  function render(container) {
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "group", "aria-label": "Parking lot layout" }, container);
    drawScenery(svg);

    const rects = {};
    const current = {};
    const geometry = {};
    for (const [id, x1, y1, x2, y2] of spots) {
      geometry[id] = [x1, y1, x2, y2];
      rects[id] = el("rect", {
        class: "spot", "data-spot": id, tabindex: 0, role: "button", "aria-label": "Spot " + id,
        x: x1, y: y1, width: x2 - x1, height: y2 - y1, rx: 6,
      }, svg);
      text(svg, "spot-label", (x1 + x2) / 2, (y1 + y2) / 2, id);
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
