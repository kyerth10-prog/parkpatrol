---
version: 1
slug: "static-index-html"
primary_target: "static/index.html"
related_targets: ["private/admin.html"]
---

# Park Patrol: guest page + admin console

Scope: `static/index.html` (guest) and `private/admin.html` (admin), sharing `static/ui.css`. Visitor mode: Operate for both surfaces. The guest needs a fast answer about whether to go; security monitors and acts. Code-led.

## Direction contract

THESIS: Every bay is a light, like the green-over-open indicators in Philippine mall car parks, and the page is the entrance sign. It refuses the KPI-tile dashboard of icon squares and gradient cards.

OWN-WORLD: White ground (#fff), ink #0f1712, hairline #e7eae8, one green family (#16a34a lamp, #15803d text, #ecfdf3 tint). Taken bays are unlit grey lamps. Amber/red only for admin violations. Onest for UI, Martian Mono for spot IDs, times, and counts only. Flat white panels with 1px hairlines and 14–20px radii, no icon tiles, no tinted card heads.

STORY: The guest reads the lit count, sees which lamps are on, and either taps a lamp, opens the map, or subscribes on Telegram. Security sees lamps go amber, then alerts or reviews events.

FIRST VIEWPORT: Top bar with logo, section nav, live pill, Admin. An entrance-sign panel: a huge green numeral, "Plenty of space"-style status heading with an updated line, and CTAs on the right. Right under it, a full-width row of 18 bay lamps A1–A18. The admin console uses the same lamp rail above its KPIs, inside a sidebar shell.

FORM: Bay Indicator, #1 on the ordered list (picked over the assigned #7 Computation Pad). seed: none (unavailable)

SIGNATURE: When a bay frees up, its lamp switches on with a short glow bloom and the sign numeral rolls. Admin violation lamps pulse amber.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
