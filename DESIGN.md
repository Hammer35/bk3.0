---
name: BOOSTKLIENT application UI
description: Operational workspace for marketplace-to-Pinterest work.
---

# BOOSTKLIENT application UI

## Fixed visual baseline

The approved baseline is **Catalog Workbench**: a serious, black operational
interface that makes the route from business data to Pinterest work visible.
It is not a generic SaaS dashboard, a landing page, or a visual clone of an
external design system.

The reference image is available in the local project at
`static/design-options/option-3-catalog-workbench.png`.

## Public and authenticated surfaces

- `/` is the public marketing landing. It uses `templates/landing_base.html`,
  `templates/core/landing.html` and `static/css/landing.css`.
- `/app/` is the authenticated operational workspace. It uses the application
  shell and workbench components.
- Public marketing navigation and authenticated product navigation are
  separate. A public page never exposes sidebar tools or business data.

## Foundations

`static/css/tokens.css` is the only source for color, typography, spacing,
radius and layout values. Components consume semantic tokens instead of
page-specific values.

- Canvas: the selected light or dark semantic palette. Both themes preserve the
  Catalog Workbench grid, line work and signal-red actions.
- Surfaces: flat and quiet; no gradients, glass or shadows.
- Accent: signal red only for the primary action and active navigation.
- Structure: 1px neutral rules; 3–4px control corners; no soft card walls.
- Type: clear sans hierarchy; compact mono-like metadata only when it conveys
  operational context.

## Shell

Authenticated screens use the same left rail, topbar and work area.
The rail contains only available product sections; future modules are never
rendered as fake controls. The topbar carries global context and account
controls. The application shell is defined in `static/css/shell.css`.

## Data composition

Pages use an operational hierarchy:

1. identify the current business or work item;
2. show its real source facts and current state;
3. show the next available action;
4. add tables, workflow lanes or content previews only when that real data
   exists.

The business home page uses the workbench pattern: workspace index, a three
stage route, and business rows with real profile fields. It does not invent a
catalogue, pins, traffic or analytics before those modules exist.

## Components

- `button-primary`: one decisive action within a local work area;
- `button-secondary`: supporting or setup action;
- `button-ghost`: utility action;
- `panel`: form, chat or semantically framed content;
- `form-field`: shared labels, inputs, help and error states;
- workbench rows: business data records with a distinct next action.

All controls retain hover, focus and keyboard states. Pages may vary their
composition, but they must use this single shell, token set and component
family.
