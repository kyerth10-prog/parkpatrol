# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Guests:** De La Salle Lipa students, staff, and visitors checking whether Lot A has free spots. Used about equally on phones (arriving on campus) and desktops (from class or offices).
- **Admins:** Campus security officers who keep the console open to watch the live camera and act on violations, plus admins who later review activity and status.

## Product Purpose

Park Patrol shows live parking availability for Lot A at De La Salle Lipa (18 spots, A1–A18), and flags double-parking violations to campus security. Success means a guest can tell at a glance whether to head to the lot, and security can see and act on a violation within seconds.

## Positioning

A single camera running a vision tracker watches the actual lot and updates each spot every few seconds. It is live ground truth for one real campus lot, not an estimate or a booking system.

## Operating Context

- Guest page polls `/api/spots` every 2s. Each spot is `available` or `taken` (guests never see violations).
- Admin console polls `/api/admin/state` every 2s and the camera frame every 1s. It shows spot statuses VACANT / OCCUPIED / VIOLATION_DOUBLE_PARKED with how long each has held, the tracker's health, and the last 30 events.
- Admins sign in with Google, limited to an allowlist of emails.
- Telegram: guests subscribe through a bot (link + QR) and get a message when a full lot frees a spot; security receives violation alerts automatically and can send manual alerts.

## Capabilities and Constraints

- Static HTML/CSS/JS served by FastAPI (`static/`, `private/admin.html`); no build step or framework.
- Guest features to keep: availability count and meter, lot map, map/list toggle, spot detail sheet, Telegram notify sheet with QR, share, help cards, admin sign-in link.
- Admin features to keep: KPIs, live camera (pause, snapshot, fullscreen), lot map with spot sheet, active violations with Alert, events table with filters, search ("/" shortcut) and CSV export, tracker health, account menu.
- The user wants all existing buttons and copy kept, including the "coming soon" placeholders (Reports, Settings, Profile, Directions, Override, Resolve, guidelines, contact security, privacy).

## Brand Commitments

- Name: Park Patrol, for De La Salle Lipa (DLSL).
- The user has set the look: modern and clean like a tech startup, mostly white with hints of green. It must feel like a real product, not a generated template.

## Evidence on Hand

- Real lot geometry in `static/lot.js` (18 spots around a central island).
- Live data only while the tracker runs; there are no testimonials, usage stats, or metrics. Do not invent any.

## Product Principles

1. The answer comes first: free-spot count and status are readable in under two seconds.
2. Live is the product: freshness and connection state are always visible and honest.
3. Security acts, not browses: violations are impossible to miss and one action away.
4. One system, two audiences: guest and admin share a visual language at different densities.

## Accessibility & Inclusion

Status is never shown by color alone; it also has a label. Keyboard access is required on the map, and reduced motion is respected.
