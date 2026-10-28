// Parking lot map (top view of the Lot A diorama)
//
// The map artwork is static/lot-map.svg, designed in Figma and exported as SVG.
// The six spot layers must be named A1 ... A6 (A1 at the top); this script finds
// them by id and colours them live. Everything else in the file is decoration
// and can be redesigned freely. If the file can't be loaded, a built-in drawing
// of the same layout is used instead.
const LOT = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const MAP_URL = "/static/lot-map.svg";
  const IDS = ["A1", "A2", "A3", "A4", "A5", "A6"];
  const SHAPES = "rect, path, polygon, circle, ellipse";

  function el(name, attrs, parent) {
    const node = document.createElementNS(NS, name);
    for (const key in attrs) node.setAttribute(key, attrs[key]);
    parent.appendChild(node);
    return node;
  }

  // ---------------------------------------------------------------------------
  // Built-in fallback drawing (same layout as the starter lot-map.svg)
  // ---------------------------------------------------------------------------
  function fallbackSvg() {
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 400 540");
    el("rect", { class: "ground", width: 400, height: 540, rx: 16 }, svg);
    el("path", { class: "road", d: "M0 0 H290 V540 H0 V478 H185 V70 H0 Z" }, svg);
    el("rect", { class: "park", x: 8, y: 80, width: 168, height: 388, rx: 12 }, svg);
    el("rect", { class: "bay-frame", x: 292, y: 30, width: 102, height: 448, rx: 8 }, svg);
    const bayH = 448 / 3, spotH = (bayH - 20) / 2;
    IDS.forEach((id, i) => {
      const bay = Math.floor(i / 2), y = 30 + bay * bayH + 7 + (i % 2) * (spotH + 6);
      const g = el("g", { id }, svg);
      el("rect", { x: 300, y, width: 86, height: spotH, rx: 6 }, g);
      const t = el("text", { x: 343, y: y + spotH / 2 + 4, "text-anchor": "middle" }, g);
      t.textContent = id;
    });
    return svg;
  }

  // ---------------------------------------------------------------------------
  // Wiring the spots of whichever SVG is loaded
  // ---------------------------------------------------------------------------
  function findSpot(svg, id) {
    // Figma exports a layer named "A1" as id="A1" (duplicates become "A1_2")
    const node = svg.querySelector(`[id="${id}"]`) || svg.querySelector(`[id^="${id}_"]`);
    if (!node) return null;
    if (node.matches(SHAPES)) return { group: node, shape: node, labels: [] };
    // A group: its largest shape is the spot, the rest (text or outlined text) are labels
    const shapes = [...node.querySelectorAll(SHAPES)];
    let shape = null, best = -1;
    for (const s of shapes) {
      let area = 0;
      try { const b = s.getBBox(); area = b.width * b.height; } catch (e) { /* not rendered yet */ }
      if (area > best) { best = area; shape = s; }
    }
    const labels = [...node.querySelectorAll("text"), ...shapes.filter((s) => s !== shape)];
    return shape ? { group: node, shape, labels } : null;
  }

  function prepare(svg) {
    svg.removeAttribute("width");
    svg.removeAttribute("height");
    svg.setAttribute("role", "group");
    svg.setAttribute("aria-label", "Parking lot layout");
    const spots = {};
    for (const id of IDS) {
      const spot = findSpot(svg, id);
      if (!spot) { console.warn(`lot-map.svg has no layer named ${id}`); continue; }
      // Live colours come from the stylesheet; drop inline colours set in the design file
      spot.shape.style.removeProperty("fill");
      spot.shape.style.removeProperty("stroke");
      spot.shape.classList.add("spot");
      spot.group.classList.add("spot-g");
      spot.labels.forEach((l) => l.classList.add("spot-label"));
      Object.assign(spot.group.dataset, { spot: id });
      spot.group.setAttribute("tabindex", "0");
      spot.group.setAttribute("role", "button");
      spot.group.setAttribute("aria-label", "Spot " + id);
      spots[id] = spot;
    }
    return spots;
  }

  // Bounding box of a spot in the SVG's own coordinates (handles Figma transforms)
  function boxOf(svg, shape) {
    const b = shape.getBBox();
    const m = shape.getCTM(), root = svg.getCTM();
    if (!m || !root) return [b.x, b.y, b.x + b.width, b.y + b.height];
    const toRoot = root.inverse().multiply(m);
    const pts = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]]
      .map(([x, y]) => new DOMPoint(x, y).matrixTransform(toRoot));
    return [Math.min(...pts.map((p) => p.x)), Math.min(...pts.map((p) => p.y)),
            Math.max(...pts.map((p) => p.x)), Math.max(...pts.map((p) => p.y))];
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------
  function render(container) {
    let svg = null, spots = {}, links = null;
    let states = {}, selected = null, groups = [];
    const current = {};

    function applyStates(animate) {
      for (const id in spots) {
        const state = states[id] || "";
        const { group, shape } = spots[id];
        const changed = animate && current[id] !== undefined && current[id] !== state;
        current[id] = state;
        for (const node of [group, shape]) node.classList.remove("available", "taken", "violation", "changed");
        if (state) { group.classList.add(state); shape.classList.add(state); }
        if (changed) { void shape.getBBox(); shape.classList.add("changed"); }
        group.setAttribute("aria-label", "Spot " + id + (state ? ", " + state : ""));
      }
    }

    function applySelection() {
      for (const id in spots) spots[id].shape.classList.toggle("is-selected", id === selected);
    }

    function applyGroups() {
      if (!links) return;
      links.replaceChildren();
      for (const group of groups) {
        const boxes = group.filter((id) => spots[id]).map((id) => boxOf(svg, spots[id].shape));
        if (boxes.length < 2) continue;
        const pad = 4;
        const x1 = Math.min(...boxes.map((b) => b[0])) - pad, y1 = Math.min(...boxes.map((b) => b[1])) - pad;
        const x2 = Math.max(...boxes.map((b) => b[2])) + pad, y2 = Math.max(...boxes.map((b) => b[3])) + pad;
        el("rect", { class: "viol-link", x: x1, y: y1, width: x2 - x1, height: y2 - y1, rx: 9 }, links);
      }
    }

    function mount(node) {
      container.replaceChildren(node);
      svg = node;
      spots = prepare(svg);
      links = el("g", { class: "viol-links", "aria-hidden": "true" }, svg);
      svg.addEventListener("keydown", (e) => {
        const target = e.target.closest && e.target.closest("[data-spot]");
        if ((e.key === "Enter" || e.key === " ") && target) {
          e.preventDefault();
          target.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        }
      });
      applyStates(false);
      applySelection();
      applyGroups();
      if (Object.keys(states).length) container.classList.remove("is-loading");
    }

    fetch(MAP_URL, { cache: "no-cache" })
      .then((res) => (res.ok ? res.text() : Promise.reject(new Error(res.status))))
      .then((text) => {
        const doc = new DOMParser().parseFromString(text, "image/svg+xml");
        const node = doc.documentElement;
        if (node.nodeName.toLowerCase() !== "svg" || doc.querySelector("parsererror")) throw new Error("not an SVG");
        node.querySelectorAll("script, foreignObject").forEach((n) => n.remove());
        mount(document.importNode(node, true));
      })
      .catch((error) => {
        console.warn("Using the built-in lot map:", error);
        mount(fallbackSvg());
      });

    return {
      ids: IDS,
      update(next) {
        states = { ...next };
        if (!svg) return;
        container.classList.remove("is-loading");
        applyStates(true);
      },
      select(id) {
        selected = id;
        applySelection();
      },
      groups(list) {
        groups = list || [];
        applyGroups();
      },
    };
  }

  return { render };
})();
