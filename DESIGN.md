---
name: Park Patrol
description: Live parking availability for DLSL Lot A, where every bay is a light and the page is the entrance sign.
colors:
  ground: "#ffffff"
  ground-subtle: "#f7f9f8"
  ground-muted: "#f0f3f1"
  ink: "#0f1712"
  ink-2: "#36413b"
  muted: "#5d6963"
  faint: "#6c7771"
  hairline: "#e6eae7"
  hairline-strong: "#d3d9d5"
  lamp-green: "#16a34a"
  lamp-green-bright: "#3fcf73"
  green-ink: "#15803d"
  green-ink-hover: "#116a33"
  green-deep: "#0e4f28"
  green-tint: "#ecfdf3"
  green-tint-2: "#cff5dd"
  lamp-off: "#d3d9d5"
  amber: "#e08a0b"
  amber-ink: "#a8540a"
  amber-tint: "#fff6e8"
  amber-line: "#f7d9a8"
  red: "#dc2626"
  red-ink: "#b42318"
  red-tint: "#fef3f2"
typography:
  display:
    fontFamily: "Onest, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "clamp(5.5rem, 9vw, 8.5rem)"
    fontWeight: 600
    lineHeight: 0.86
    letterSpacing: "-0.045em"
  headline:
    fontFamily: "Onest, ui-sans-serif, system-ui, sans-serif"
    fontSize: "clamp(1.75rem, 3vw, 2.5rem)"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  metric:
    fontFamily: "Onest, ui-sans-serif, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Onest, ui-sans-serif, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Onest, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
  body-sm:
    fontFamily: "Onest, ui-sans-serif, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Onest, ui-sans-serif, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.2
  data:
    fontFamily: "Martian Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
rounded:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  pill: "99px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
  3xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.green-ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.green-ink-hover}"
  button-secondary:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.ground-subtle}"
  button-soft:
    backgroundColor: "{colors.green-tint}"
    textColor: "{colors.green-ink}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "40px"
  button-ghost-hover:
    backgroundColor: "{colors.ground-muted}"
  lamp:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink-2}"
    typography: "{typography.data}"
    rounded: "{rounded.md}"
    padding: "16px 0 12px"
  lamp-light-available:
    backgroundColor: "{colors.lamp-green}"
    rounded: "{rounded.pill}"
    size: "20px"
  lamp-light-taken:
    backgroundColor: "{colors.lamp-off}"
    rounded: "{rounded.pill}"
    size: "20px"
  lamp-violation:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.amber-ink}"
    rounded: "{rounded.md}"
  panel:
    backgroundColor: "{colors.ground}"
    rounded: "{rounded.lg}"
    padding: "24px"
  sign:
    backgroundColor: "{colors.ground}"
    rounded: "{rounded.xl}"
    padding: "36px 40px 32px"
  pill-ok:
    backgroundColor: "{colors.green-tint}"
    textColor: "{colors.green-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 9px"
    height: "24px"
  pill-warn:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.amber-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 9px"
    height: "24px"
  chip:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "0 11px"
    height: "30px"
  chip-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
  input-search:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 10px 0 12px"
    height: "40px"
  navlink:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    padding: "0 10px"
    height: "36px"
  navlink-active:
    backgroundColor: "{colors.green-tint}"
    textColor: "{colors.green-deep}"
  toast:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.md}"
    padding: "10px 16px 10px 12px"
  sheet:
    backgroundColor: "{colors.ground}"
    rounded: "{rounded.xl}"
    padding: "28px"
    width: "440px"
---

# Design System: Park Patrol

## Overview

**Creative North Star: "The Entrance Sign"**

Every bay is a light, the way green-over-open indicators work in Philippine mall car parks, and the page itself is the sign at the lot entrance. The guest reads one huge green numeral and a row of eighteen lamps; security reads the same lamps at higher density, inside a sidebar console. One system serves both audiences: same palette, same lamp, same hairline panels, with the admin side adding amber violation states, KPIs, a camera, and an events table.

The material is white ground, ink text, and 1px hairlines. Panels are flat white with generous rounding; depth is reserved for things that float (sheets, menus, toasts). Colour is spent almost entirely on state: green means a bay is open, an unlit grey lamp means taken, amber means a violation, and red appears only as a count badge and destructive menu items. The type is Onest throughout, with Martian Mono reserved for machine values (spot IDs, times, counts).

The system rejects the KPI-tile dashboard: no icon squares, no gradient cards, no tinted card heads. The admin KPIs are plain hairline panels with a number, a label, and a meter.

**Key Characteristics:**
- White ground, ink text, one green family; amber only for violations.
- The bay lamp is the signature unit, repeated on guest, admin, legend dots, map, and spot detail.
- Flat hairline panels (1px, 12–20px radii); shadows only on floating layers.
- Onest for everything a person reads; Martian Mono only for IDs, times, and counts.
- Motion is a state signal: lamps switch on, numbers pop, violations pulse. All of it is disabled under reduced motion.

## Colors

A near-monochrome white-and-ink palette where colour carries status, not decoration.

### Primary
- **Lamp Green** (lamp-green): the lit lamp, the entrance-sign numeral, the meter fill, the live dot, focus rings, and the active tab-bar indicator. This is the "open" signal; use it for availability and for interaction affordance (focus, caret), nothing else.
- **Green Ink** (green-ink): green that has to pass as text or a solid button fill. Primary buttons, link buttons, pill and KPI text for "available", help-list icons. Hover deepens to Green Ink Hover (green-ink-hover).
- **Deep Green** (green-deep): green text on a green tint: lit lamp IDs, active sidebar navlink, avatar initials, island label on the map, and text selection.
- **Green Tint** (green-tint) and **Green Tint 2** (green-tint-2): soft fills for the live pill, soft buttons, active navlink, empty-state marks, the flat halo around a lit lamp, and available map spots. Tint 2 is the hover and the stronger fill.
- **Bright Lamp Green** (lamp-green-bright): only on dark ground (the brand mark dot and the toast success icon).

### Secondary
- **Signal Amber** (amber): the violation lamp and warning dot. Admin only; guests never see violations.
- **Amber Ink** (amber-ink), **Amber Tint** (amber-tint), **Amber Line** (amber-line): text, fill, and border for violation lamps, the alert KPI, the warning banner, and violation list items.

### Tertiary
- **Alarm Red** (red): the notification count badge only.
- **Red Ink** (red-ink) on **Red Tint** (red-tint): destructive menu items (sign out).

### Neutral
- **Ground** (ground): page and panel background. The admin page sits on Ground Subtle with white panels on top.
- **Ground Subtle** (ground-subtle): hover fill for buttons, lamps, tiles, and table rows; the outer band of the lot map; table headers; footer.
- **Ground Muted** (ground-muted): pill, segmented-control, and meter tracks; ghost-button hover; unlit lamp interior; taken map spots.
- **Ink** (ink): primary text, the selected-lamp outline, selected chips, toasts, the camera letterbox.
- **Ink 2** (ink-2): secondary text, button and navlink labels, the full-lot numeral.
- **Muted** (muted) and **Faint** (faint): supporting copy, captions, legends, placeholders, table headers, sidebar section labels.
- **Hairline** (hairline) and **Hairline Strong** (hairline-strong): 1px panel borders and dividers; button, input, and chip borders.
- **Lamp Off** (lamp-off): the unlit lamp, which is deliberately the same value as Hairline Strong. A taken bay is a dead bulb, not a red one.

### Named Rules
**The Light Means Open Rule.** Green belongs to availability. A green fill or lamp always means "a bay is open" or "this is the action". Never use it as a neutral accent.

**The Dead Bulb Rule.** Taken is grey (lamp-off), never red. Red is for alarms (badge, destructive action), not for ordinary occupancy.

**The Amber Is Admin Rule.** Amber appears only on admin surfaces (violations, the alert KPI, the warning banner). Offline and no-data states use neutral grey (bg-muted ground, faint dot), never amber.

## Typography

**Display Font:** Onest (with ui-sans-serif, system-ui, -apple-system, Segoe UI)
**Label/Mono Font:** Martian Mono (with ui-monospace, SF Mono, Menlo), for data only

**Character:** Onest is a clean, slightly geometric grotesk that reads as a modern product without looking like a template. Martian Mono's wide, squared shapes make bay IDs and timestamps read like stencilled bay markings. Both load from Google Fonts (Onest 400–700, Martian Mono 400–600).

### Hierarchy
- **Display** (600, clamp(5.5rem, 9vw, 8.5rem), 0.86): the entrance-sign free-spot numeral only. Green when spots are free, Ink 2 when the lot is full. Proportional figures.
- **Headline** (600, clamp(1.75rem, 3vw, 2.5rem), 1.2, -0.03em): the sign's status line ("Filling up").
- **Metric** (600, 34px, 1.1, -0.035em; 28px under 760px): admin KPI values, with a 16px Faint unit beside them.
- **Title** (600, 17px, 1.2): panel headings. Sheet headings step up to 20px; the admin top-bar title is 18px; help-item and small section heads are 14–15px.
- **Body** (400, 15px, 1.55): default copy. The sign subline is 16px Muted.
- **Body small** (400, 13–14px): panel subtitles, help text, legends, table cells, menus.
- **Label** (500, 12px): pills, table headers, sidebar section labels, top-bar subtitles. Sentence case.
- **Data** (Martian Mono 500, 11–12px, -0.03em, tabular figures): lamp IDs, lamp durations, map spot labels, spot-ID chips, timestamps, badge counts, chip counts, the keyboard hint. The spot-detail ID and spot-tile ID step up to 18px and 14px at 600.

All headings are 600 with negative tracking (-0.02em default) and balanced wrapping.

### Named Rules
**The Mono Is Data Rule.** Martian Mono is for values a machine produced (IDs, times, counts). Headings, labels, buttons, and prose are always Onest.

**The One Big Number Rule.** The display size exists for one numeral per surface: the free-spot count. Nothing else gets that scale.

## Layout

The guest page is a centred container (max 1200px, 32px side padding, 16px under 760px) under a 64px sticky translucent app bar. The entrance sign spans the full width: numeral, status block, and actions in a three-column grid (auto / 1fr / auto, 48px gap), with the 18-lamp rail beneath a hairline. Below it, a two-column grid (1.65fr / 1fr, 20px gap) holds the lot map and help panel.

The admin console is a 248px sticky sidebar plus a main column on Ground Subtle. A 64px translucent top bar sits over a content stack with a 20px gap and 32px side padding. Rows: the lamp rail, four KPI columns, then split rows (1.45fr / 1fr and 1fr / 1.45fr) for camera, map, violations, and events.

Spacing follows a 4px base, mostly in 8px steps: 8px between lamps and chips, 12–16px inside tiles and between controls, 20px between panels, 24px panel padding, 32px for large section breaks.

Responsive behaviour:
- **1200px:** admin KPIs drop to two columns and the split rows stack.
- **1024px:** the lamp rail goes from 18 to 9 columns; the admin sidebar becomes an off-canvas drawer with a scrim.
- **960px:** the sign's actions wrap below the numeral and status; the guest grid stacks.
- **760px:** the top nav hides and a fixed 64px bottom tab bar appears; admin padding tightens to 12px.
- **640px:** sheets become bottom sheets with a grip.
- **560px:** six lamps per row with a 6px gap; panels go to 18px padding and a 14px radius; the sign goes to 18px radius.

## Elevation & Depth

Surfaces rest flat. Panels, the sign, lamps, tiles, and list items sit on the ground with a 1px hairline and no shadow. Shadows mark layers that float above the page (sheets, menus, toasts, the mobile drawer), plus a near-invisible 1px lift on bordered controls. The sticky bars use translucency and blur instead of shadow, and gain a hairline only once the page scrolls.

### Shadow Vocabulary
- **Control lift** (`box-shadow: 0 1px 2px rgba(15, 23, 18, .05)`): secondary buttons, bordered icon buttons, the search field.
- **Pop** (`box-shadow: 0 16px 40px -12px rgba(15, 23, 18, .22), 0 2px 6px rgba(15, 23, 18, .06)`): sheets, the account menu, toasts, the mobile sidebar drawer.
- **Segment thumb** (`box-shadow: 0 1px 3px rgba(15, 23, 18, .12), 0 0 0 1px rgba(15, 23, 18, .04)`): the sliding thumb of the segmented control.
- **Lamp halo** (`box-shadow: 0 0 0 5px` Green Tint): a flat, unblurred ring around a lit lamp (amber ring for a violation). This is a ring, not a glow.

### Named Rules
**The Float Only Rule.** A shadow means "this sits above the page". Resting panels and cards never get one; they get a hairline.

**The Flat Lamp Rule.** Lamps are flat discs with a solid spread ring. No blur, gradients, or inner highlights. The switch-on bloom is a moving spread ring that settles back to flat.

## Shapes

The shapes are soft rounded rectangles in a stepped scale: 6px for small ID chips and badges, 8px for buttons, inputs, and navlinks, 12px for lamps, tiles, list items, menus, and the camera, 16px for panels, and 20px for the entrance sign and dialog sheets. Large buttons and the segmented control use 10px. Everything that reports status in a line (pills, chips, the live indicator, badges, meters) is a full pill. Lamp lights, dots, and avatars are perfect circles. The lot map uses the same language in SVG: rounded bands, a dashed lane, and a rounded green island. Borders are always 1px hairlines; state changes the border colour, not its weight (the selected lamp adds a 1px ink ring).

## Components

### Buttons
Quiet and solid: green for the one action that matters, white bordered for the rest.
- **Shape:** gently rounded (8px; 10px at the 48px large size). Heights 34 / 40 / 48px.
- **Primary:** Green Ink fill, white 14px/500 label, faint inset top highlight. Hover deepens to Green Ink Hover.
- **Secondary (default):** white with a Hairline Strong border and control lift. Hover goes to Ground Subtle.
- **Soft:** Green Tint fill, Green Ink label, no border. Hover goes to Green Tint 2.
- **Ghost:** transparent with an Ink 2 label. Hover goes to Ground Muted.
- **Press:** all buttons shift down 1px on press. Disabled is 50% opacity.
- **Focus:** a 2px Lamp Green outline at a 2px offset (global).
- **Link button:** Green Ink 13px/500 text; an underline fades in on hover.
- **Icon buttons:** 40px square (34 / 48 variants), transparent or bordered. Icons are 1.75-stroke inline SVG line icons at 16–20px.

### Chips
- **Style:** 30px pill, white with a Hairline Strong border, 13px/500 Ink 2 label, optional mono count in Faint.
- **State:** selected chips invert to an Ink fill with white text. Used as event filters.

### Pills and badges
- **Pills:** 24px tinted pill with a 12px/500 label. Variants: ok (green tint), taken (muted), warn (amber tint), muted (outline only).
- **Live indicator:** 28px Green Tint pill with a 7px Lamp Green dot that pings every 2s. Offline swaps to a neutral grey pill (bg-muted, ink-2 text, faint dot) and stops pinging.
- **Badge:** 18px Alarm Red pill, white mono count, bumps when it changes.

### Cards / Containers
- **Corner Style:** 16px panels; 20px for the entrance sign.
- **Background:** Ground, on Ground (guest) or Ground Subtle (admin).
- **Shadow Strategy:** none (see Float Only).
- **Border:** 1px Hairline. An alert KPI swaps to an Amber Line border on Amber Tint.
- **Internal Padding:** 24px (18px on small screens). The sign uses 36px / 40px. A panel head (17px title, 13px Muted subtitle, tools on the right) sits 20px above the content; an optional foot sits below a hairline.

### Inputs / Fields
- **Style:** the search field is 40px tall, white, with a Hairline Strong border, 8px radius, control lift, a leading icon, and a mono keyboard hint.
- **Focus:** the border turns Lamp Green with a 3px Green Tint 2 ring. The caret is green.

### Navigation
- **Guest top nav:** 14px/500 Muted links in 8px-radius pills. Hover and active fill with Ground Muted and switch to Ink.
- **Guest tab bar (under 760px):** fixed, translucent white with a top hairline, 11px labels under 20px icons. Active is Green Ink with a 2px Lamp Green bar at the top edge.
- **Admin sidebar:** 36px navlinks (14px/500 Ink 2, Muted icon). Hover is Ground Muted; active is Green Tint with Deep Green text and a Green Ink icon. Sections are separated by 12px Faint labels. A tracker-health card sits at the foot.
- **Segmented control:** a Ground Muted track with a white sliding thumb (10px / 7px radii). Used for Map / List.

### Bay Lamp (signature)
The unit of the whole system. It is a 12px-radius white cell with a hairline border, containing a 20px circular light, a mono ID, and an optional mono duration.
- **Available:** a Lamp Green disc with a 5px Green Tint flat ring; the ID turns Deep Green.
- **Taken:** a solid Lamp Off disc with no ring; the ID turns Muted.
- **Unknown:** a Ground Muted disc with a 1.5px Lamp Off inner stroke.
- **Violation (admin):** the cell takes Amber Tint and Amber Line; an amber disc pulses its ring every 1.4s.
- **Switch-on:** when a bay frees up, the disc scales from 0.85 through 1.12 to 1 while a green spread ring blooms out and fades (1.1s, ease-out). Switch-off is a short 1.1 to 1 settle.
- **Hover / Selected:** hover lifts 1px onto Ground Subtle. Selected gets an Ink border plus a 1px Ink ring.
- **Rail:** 18 columns at 8px gap, then 9, then 6.
- **Echoes:** 10px legend dots (3px ring), map spots (Green Tint 2 fill with a Lamp Green stroke for available, amber fill pulse for a violation), and the spot-detail ID tile with a corner status dot.

### Entrance Sign
The guest hero is a 20px-radius hairline panel. It holds the display numeral (green, or Ink 2 when full), a "spots free in Lot A" unit line, the status headline with an updated subline and a 6px pill meter, primary/secondary actions stacked on the right, and the lamp rail below a hairline.

### Sheets and Toasts
- **Sheet:** a centred 440px dialog with a 20px radius, 28px padding, and the pop shadow over a 36% ink scrim. It rises 12px while fading in. Under 640px it becomes a bottom sheet (22px top corners) with a 40×4 grip.
- **Toast:** a 12px-radius Ink pill with white 14px/500 text and the pop shadow, bottom-centred. Its leading circular icon is bright green on a translucent green (amber for warnings).

### Lot Map
An SVG drawn to the real lot geometry: a Ground Subtle outer band, white asphalt, a dashed Hairline Strong lane, and a rounded Green Tint island labelled "LOT A / DLSL". Spots are 1.5px-stroke rectangles with mono labels. They are keyboard focusable, with a 3px green stroke on focus and a 2.5px ink stroke when selected.

## Do's and Don'ts

### Do:
- **Do** express bay status through the lamp: Lamp Green disc with a Green Tint ring for open, a solid Lamp Off disc for taken, an amber pulse for a violation. Always pair it with a text label (legend, pill, or ID colour).
- **Do** keep resting surfaces flat white with a 1px Hairline (#e6eae7) and a 12–20px radius.
- **Do** use Green Ink (#15803d) for green text and solid green buttons, and Lamp Green (#16a34a) for lights, meters, and focus.
- **Do** set IDs, times, and counts in Martian Mono with tabular figures and -0.03em tracking.
- **Do** reserve shadows for floating layers (sheets, menus, toasts, drawer).
- **Do** gate all motion behind prefers-reduced-motion. The stylesheet collapses every animation and transition to near zero.

### Don't:
- **Don't** build KPI-tile dashboards with icon squares, gradient cards, or tinted card heads. KPIs are plain hairline panels.
- **Don't** show a taken bay in red. Red is for the alert badge and destructive actions only.
- **Don't** show amber or violation states on guest surfaces.
- **Don't** add blur glows, gradients, or inner highlights to lamps. Lamps are flat.
- **Don't** use Martian Mono for headings, labels, buttons, or prose.
- **Don't** introduce a second accent hue. The palette is one green family plus amber and red as status.
