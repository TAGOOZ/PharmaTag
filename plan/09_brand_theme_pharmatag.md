# PharmaTag فارما تاج — Brand & Design-Token Foundation (09)

**Author role:** Design-system lead
**Scope:** Planning only — visual identity direction + full design-token schema for the TITAN.W1 rebuild (Next.js web + Tauri/React desktop, Arabic-first RTL, keyboard-first POS, dense grids). No code written.
**Sources read:** `plan/03_frontend_plan.md` (token home, fonts, RTL rules, component inventory), `titan_extract/ui_complete.md` (screen/forms inventory), `titan_extract/feature_sales_invoices.md` (POS workflow, states, strings), `titan_extract/feature_reports_analytics.md` (grid/report patterns, printer templates).
**Absent source (corrected 2026-08-16):** `plan/08_app_architecture_plugins.md` **does exist** (A08–A12; plugin UI = pilot plugins `pharmatag-eta`/`pharmatag-ledger`). "Plugin/install screen" below is therefore the activation/setup wizard + integrations hub (see §5.6 and Open decision #1 → resolved).
**Companion contracts honored:** token home = `packages/ui` (03 §1.2), RTL-first logical properties (03 §3.3; fonts now **Thmanyah** per P05 / 00 master), keyboard-first POS F9/F12 (03 §3.4), data-grid on TanStack Table with sticky inline-end column (03 §5.2), shell sync-status chip (03 §5.1), report grid with totals + group subtotals (03 §5.2).

---

## Reconciled 2026-08-16

Synced to `plan/00_decisions_master.md` Tier-2 picks:

- **P02 — light is the PRIMARY theme.** Light is the brand default on BOTH web + desktop; dark is the supported alternate. `:root` = light, `[data-theme="dark"]` = dark. The `data-theme` switch architecture (`system | light | dark`) and the anti-flash inline script are unchanged.
- **P05 — Thmanyah fonts + bookmarkX token reuse.** Fonts = Thmanyah family per the shared `bookmarkX/docs/style-guide.md` (UI = Thmanyah Sans 300–900, headings = Thmanyah Serif Display, body = Thmanyah Serif Text; fallback `'Thmanyah', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`). Token architecture + NAMING reused from bookmarkX (`--background-primary/-secondary/-tertiary`, `--text-normal/-muted/-faint`, `--accent-color/-hover`, `--priority-high/-medium/-low`, `--color-error`, `--color-success`, `--space-*`, `--radius-*`, `--shadow-*`, `--transition-*`, `--z-*`) with PharmaTag's brand hexes as the values; the derived-WCAG layer is retained (§6).
- **P01, P03, P04, P06–P10 confirmed as authored.** §7 open decisions marked resolved inline; §8 assumptions updated.

---

## 0. Executive summary — top decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Tokens are CSS custom properties, all semantic, light-by-default (P02).** `:root` = light (brand default on web + desktop); `[data-theme="dark"]` overrides. Naming follows the bookmarkX architecture (P05): `--background-primary/-secondary/-tertiary`, `--text-normal/-muted/-faint`, `--accent-color/-hover`, `--priority-*`, `--color-error`/`--color-success`, shared `--space-*`/`--radius-*`/`--shadow-*`/`--transition-*`/`--z-*` — with PharmaTag brand hexes as the values + a derived-WCAG layer. Brand hexes live as *primitives*; components consume only *semantic* tokens. | Light is the brand default (00 P02); dark is the night-shift alternate. Hex→semantic indirection is what makes theme switching and WCAG fixes possible without touching components. |
| D2 | **Two-layer color system: primitives + derived.** The client palette is kept verbatim as primitives. Derived values (secondary-strong, muted-strong, priority-text-strong, soft tints, zebra, selection) are computed to pass WCAG on every surface. | The spec palette fails AA in several places (§6). We extend, never replace. |
| D3 | **Tailwind (v3 `extend`/v4 `@theme inline`) maps 1:1 to tokens** via `rgb(var(--color-*) / <alpha-value>)`. shadcn-style components consume tokens only. | Matches 03 §5 `packages/ui` (Tailwind, shadcn-style). Alpha compositing requires RGB-triplet storage, so token sheets list hex for humans and the CSS stores `R G B` triplets. |
| D4 | **Fonts self-hosted in `packages/ui`: Thmanyah family (P05)** — UI = Thmanyah Sans 300–900, headings = Thmanyah Serif Display, body = Thmanyah Serif Text; fallback `'Thmanyah', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` (covers Arabic + Latin). Mono for Latin digits/barcode stays. Western digits (`latn`) forced via Intl. | Per shared `bookmarkX/docs/style-guide.md` §3; one family covers Arabic + Latin; offline-first constraint (no Google Fonts CDN on desktop). Replaces the IBM Plex Sans Arabic + Cairo pairing. |
| D5 | **Theme switch = pure CSS swap, no re-render.** `data-theme` set by an anti-flash inline script in `<head>` (default `light` per P02), persisted (localStorage on web / Tauri config on desktop), `system|light|dark` setting. | POS speed: zero JS layout cost when toggling; light is the brand default on both platforms, dark the supported alternate. |
| D6 | **RTL is structural, not cosmetic.** `dir="rtl"` + `lang="ar"` on `<html>`; logical properties everywhere; sticky action column anchored to inline-end; directional icons mirrored; charts reversed. | 03 §3.3 mandates this. LTR (English mode) is a mirror, not a redesign. |
| D7 | **POS density tier is a first-class token family** (row heights, cell padding, hit targets, motion ≤150 ms), not an afterthought. | Revenue screen (03 §6 item 4); legacy keyboard/touch muscle memory must survive (F9/F12, ↑/↓ batch picker). |

**Biggest design risk:** the muted-gray `#808080`/`#999999` (dark) and `#999999` (light) text values from the spec **fail WCAG AA as body text on their own surfaces** (§6). The plan keeps them as primitives but routes all real content text through derived, passing tokens. Second-tier: accent as small text on raised dark surfaces and all three light-theme priority colors as small text — same extension pattern.

---

## 1. Brand identity — PharmaTag / فارما تاج

### 1.1 Logo mark direction: pharmacy cross × tag/label

The two brand concepts are **pharmacy (cross/plus, هلال/صليب الصيدلية)** and **tag/label** (tag = the barcode/tag identity of a pharmaceutical product — the product's `tag` in the system; also "Tag" echoes "TAG = TITAN.gen"), unified in **purple accent** (#a882ff dark / #7c5cbf light).

Recommended direction — **cross-through-tag**: a rectangular tag/label silhouette (rounded-corner ticket with a punched hole at one corner — the "قائمة/تاغ" motif) whose notched top corner carries the pharmacy **cross**. The cross sits inside the tag as a solid accent square with a notched/cut corner, the tag body is a dark neutral. The negative space between tag edge and cross reads as a barcode tick when scaled small.

Build-ready options to develop (decision needed — Open question #2):

- **Option A (recommended) "Tag-Cross":** single accent tag with cross; wordmark sits to its left (RTL: to the right of the glyph). Simplest, survives favicon size (a 32px tag + cross reads fine).
- **Option B "Cross & Tag duo":** cross glyph + separate tag glyph (tag drawn as a loose prescription slip with a fold). More expressive at app-shell size (72px rail), muddier at 16px favicon.
- **Option C "Taj + tick":** accent Arabic letterform `ت`/`ج` (for تاج) drawn to double as a tag with a barcode tick at its baseline. Risky at small sizes; typography-dependent.

Iconography rules: never put Arabic text in the mark; the mark must read monochrome (dark bg) and accent-on-dark and accent-on-white; keep the cross's inner cut ≥ 2px at 16px.

### 1.2 Wordmark

- **Latin:** `PharmaTag` — `Pharma` in regular weight, `Tag` in bold (emphasis on the Latin glyph; the two-word cadence maps to English-reading trainers).
- **Arabic:** `فارما تاج` — both words in Thmanyah Serif Display SemiBold, generous `letter-spacing: 0` (Arabic must never be letter-spaced).
- No translation of "Tag" in the wordmark line; the standalone Arabic noun `تاج` (crown) is a deliberate second read — we lean into it in taglines only, not in the mark.

### 1.3 Arabic + English lockup

Horizontal lockup: `[mark] [فارما تاج]` primary line with `[PharmaTag]` as a muted caption directly beneath (never side-by-side at small sizes). In the English toggle mode the lockup flips: `[mark] [PharmaTag]` with `فارما تاج` as the caption. Same glyph block in both; only the caption line swaps. Vertical stack (login/setup screens) = mark above, both text lines stacked.

### 1.4 Tagline options (one-word-feel, Arabic-first, double-coded تاج)

1. `صيدليتك، متوّجة بالدقة` — "Your pharmacy, crowned with accuracy" (crown/تاج double-meaning; accuracy = money/stock integrity).
2. `نظام صيدلية يوثّق كل تاج` — "A pharmacy system that tags every item" (tag = product record; trust = audit).
3. `الدرج والرصيد، بنظام واحد` — "Drawer and stock, under one system" (practical, speaks to day-close + stock truth — the two riskiest modules).
4. Short form for loading/splash: `دقة. سرعة. تاج.` ("Accuracy. Speed. Tag.")

Recommendation: #1 primary (brand feel), #4 for the boot/splash line. Decision needed (Open question #2).

---

## 2. Design-token architecture

### 2.1 Storage model

- **Primitive layer** (`--pr-*`, "brand primitives"): the exact client hexes, per theme. Never referenced directly by components.
- **Semantic layer** — canonical names reused from the bookmarkX style guide (P05): `--background-primary/-secondary/-tertiary`, `--text-normal/-muted/-faint`, `--text-on-accent`, `--accent-color`/`--accent-color-hover`, `--priority-high/-medium/-low`, `--color-error`/`--color-success`; shared scales `--space-*`, `--radius-*`, `--shadow-*`, `--transition-*`, `--z-*`. PharmaTag keeps its **brand hexes as the values** and extends with a **derived-WCAG layer** (`-strong`/`-soft`/`-solid` text+fill variants, table/pos/chart tokens, `--ease-*`, `--density-*`) so every surface passes AA (§6).
- **CSS storage:** primitives as `#hex`; semantic colors as space-separated `R G B` triplets so Tailwind's `<alpha-value>` compositing works (`rgb(var(--color-accent) / 0.35)`). Token sheets below show hex for readability; the triplets are mechanical conversions.
- **Tailwind mapping:** every semantic token becomes a utility name. In Tailwind v4: `@theme inline { --color-accent: rgb(var(--color-accent)); ... }`. In v3: `theme.extend.colors = { accent: 'rgb(var(--color-accent) / <alpha-value>)', ... }`. Same for `spacing`, `borderRadius`, `fontSize`, `boxShadow`, `transitionDuration`.
- Home: `packages/ui/src/styles/tokens.css` (light in `:root` — brand default per P02, dark under `[data-theme="dark"]`), `tailwind.config`/`@theme` in `packages/config`.

### 2.2 Semantic color groups (the schema — bookmarkX naming, P05)

**Canonical bookmarkX names for the base set:** `--background-primary/-secondary/-tertiary`, `--background-modifier-border/-form-field`, `--text-normal/-muted/-faint`, `--text-on-accent`, `--accent-color`/`--accent-color-hover`, `--priority-high/-medium/-low`, `--color-error`/`--color-success`. **PharmaTag's derived-WCAG layer extends each group** (PharmaTag sheet aliases in parentheses below); the brand hexes stay the values:

```
backgrounds      background-primary (bg-app), -secondary (bg-surface), -tertiary (bg-raised),
                 background-modifier-border (bg-overlay/border), -form-field (bg-input),
                 bg-well, bg-scrim
text             text-normal (text-primary), text-muted (text-secondary), text-faint (muted),
                 text-on-accent; derived: -secondary-strong, -muted-strong, -disabled,
                 -placeholder, -inverse
accent           accent-color, accent-color-hover; derived: accent-active, accent-soft,
                 accent-border, accent-contrast, accent-focus-ring
border           border, border-strong, border-faint
priority         priority-high/-medium/-low × {base fills, derived: -text, -text-strong,
                 -soft, -solid, -on-solid}
feedback         color-success = priority-low, warning = priority-medium, color-error = priority-high,
                 info = accent; each also gets -soft/-solid/-on-solid
controls         control-bg, control-bg-hover, control-bg-active, control-bg-disabled,
                 control-border, control-border-hover, control-border-focus
focus/selection  focus-ring, focus-ring-offset, selection-bg, selection-text
table            table-bg, table-stripe, table-hover, table-selected, table-header-bg,
                 table-header-text, table-border, table-totals-bg, table-sticky-bg
pos              pos-line, pos-totals-bg, pos-key-bg, pos-key-accent, pos-total-accent
charts           chart-1..6 (accent, high, medium, low, secondary-strong, white/grey)
elevation        shadow-xs..xl, ring
```

**Base-token values (PharmaTag hexes = bookmarkX values 1:1):**
- Dark: `--background-primary` #1e1e1e · `--background-secondary` #262626 · `--background-tertiary` #363636 · `--background-modifier-border` #3f3f3f · `--text-normal` #dadada · `--text-muted` #999999 · `--text-faint` #808080 · `--accent-color` #a882ff · `--accent-color-hover` #b99aff · `--priority-high/-medium/-low` #fb464c/#f0ee5a/#44cf6e
- Light: `--background-primary` #ffffff · `--background-secondary` #f5f5f5 · `--background-tertiary` #e8e8e8 · `--background-modifier-border` #e0e0e0 · `--text-normal` #1e1e1e · `--text-muted` #666666 · `--text-faint` #999999 · `--accent-color` #7c5cbf · `--accent-color-hover` #6a4da8 · `--priority-*` #e03e3e/#9a8f10/#36a854

`--color-error`/`--color-success` alias the priority trio; see the §3 sheets for the derived AA-passing text values (e.g. light `--priority-high-text` #b3261e, `--color-error` on light = #b3261e via `--color-danger-solid-strong`).

### 2.3 Spacing, radius, density

- **Spacing scale** (4px base, bookmarkX `--space-*` naming): `--space-xs` 4 · `--space-s` 8 · `--space-m` 12 · `--space-l` 16 · `--space-xl` 24 · `--space-2xl` 32 · `--space-3xl` 48 (PharmaTag keeps optional 20/40/64 for screens). Grids/forms use 4/8/12; screen-level 16/24; modals 24/32.
- **Density tier (POS/grids — D7):** rows `sm 28px · md 34px · lg 40px`; touch targets (qty bar, keypad) `44–48px`; cell padding `tight 4×6 · default 6×10 · loose 8×12`; a `data-density` attribute on `DataGrid`/`InvoiceLinesGrid` switches rows. Default: `md` in lists, `sm` in POS lines grid, `lg` on touch devices. (P04 confirmed: 28px invoice rows / 34px lists / 48px touch.)
- **Radius:** bookmarkX `--radius-*` scale (`--radius-xs` 2 · `--radius-s` 4 · `--radius-m` 8 · `--radius-l` 12 · `--radius-xl` 16; pill = 999). POS inputs/cards `radius-m`, dialogs `radius-l`/`xl`, badges pill.
- **Motion:** `--transition-fast` 100ms · `--transition-normal` 200ms (bookmarkX) plus PharmaTag `--dur-*` 100/150/200/300 ms; POS/scan feedback = 100–150 ms, no decorative full-screen animation; standard easing `cubic-bezier(.2,.8,.2,1)`; toasts 250 ms. Respect `prefers-reduced-motion` (collapse to 0/instant).
- **Z-index scale:** bookmarkX `--z-*` naming — `--z-base` 1 · `--z-dropdown` 10 · `--z-sticky` 20 · `--z-overlay` 100 · `--z-modal` 200 · `--z-toast` 300 (PharmaTag roles: app-bar/tab-bar → sticky/overlay, modal → modal, toast → toast).

### 2.4 Typography scale

| Token | Size/weight | Use |
|---|---|---|
| `--text-xs` | 11 / 400 | dense grid cells, table headers (POS lines) |
| `--text-sm` | 12 / 400–600 | grid body, form hints, badges |
| `--text-base` | 13 / 400 | default body (dense ERP; Arabic reads fine at 13–14) |
| `--text-md` | 14 / 400–500 | inputs, labels, buttons |
| `--text-lg` | 16 / 500 | section titles, field values |
| `--text-xl` | 18 / 600 | sub-screen headings, POS totals |
| `--text-2xl` | 20 / 600 | screen titles, grand-total value |
| `--text-3xl` | 24 / 700 | dashboard stat numbers, login heading |
| `--text-4xl` | 28 / 700 | POS grand total (display) |
| `--text-5xl` | 32–40 / 700 | hero/login marks |

- **Font stacks (self-hosted in `packages/ui`, Thmanyah family per P05 / `bookmarkX/docs/style-guide.md` §3):**
  - `--font-sans`: `'Thmanyah', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` (Thmanyah Sans 300–900 — UI, buttons, labels, nav)
  - `--font-display`: `'Thmanyah Serif Display','Thmanyah',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif` (headings, dashboards, wordmark, numerals in stat cards)
  - `--font-body`: `'Thmanyah Serif Text','Thmanyah',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif` (long-form body / reports)
  - `--font-mono`: `'IBM Plex Mono','JetBrains Mono',ui-monospace,SFMono-Regular,monospace` — **Latin digits only** (barcode fields, invoice numbers, qty/price columns → `font-variant-numeric: tabular-nums`).
- **Line-height:** body `1.6–1.7` (Arabic needs taller than Latin), headings `1.2–1.35`, dense grids `1.4`. `letter-spacing: 0` on all Arabic; optional `0.01em` on Latin headings only.
- **Numerals:** force `numberingSystem: 'latn'` (03 §3.3); money always `tabular-nums`, right-aligned in RTL columns.
- **Minimum body size on desktop:** 13px; print/report CSS uses its own fixed scale (see §5.4).

### 2.5 Elevation (dark-grey surfaces)

Naming: bookmarkX `--shadow-s/m/l` is canonical (P05); PharmaTag keeps the finer `shadow-xs..xl` scale for elevation layering (`--shadow-s` = `shadow-xs`/`shadow-sm`, `--shadow-m` = `shadow-md`, `--shadow-l` = `shadow-lg`/`shadow-xl`).

Dark surfaces don't separate by light-shadow the way white UIs do — separate by **luminance + hairline border + subtle purple-tinted shadow**:

- `shadow-xs` `0 1px 2px rgb(0 0 0 / .40)` — hairlines, sticky bars
- `shadow-sm` `0 2px 6px rgb(0 0 0 / .42)` — cards on surface
- `shadow-md` `0 6px 16px rgb(0 0 0 / .50)` — popovers, dropdowns
- `shadow-lg` `0 12px 32px rgb(0 0 0 / .55)` — modals
- `shadow-xl` `0 20px 60px rgb(0 0 0 / .60)` — full-screen overlays (POS sheet)
- `accent-glow` `0 0 0 3px rgb(168 130 255 / .35)` — focused/active interactive (dark); light theme `0 0 0 3px rgb(106 77 168 / .30)`.

### 2.6 Motion/duration

`--dur-fast 100ms · --dur-base 150ms · --dur-slow 200ms · --dur-slower 300ms`; `--ease-std cubic-bezier(.2,.8,.2,1)`. Rules: POS line add, scan flash, focus ring = `fast`; dropdown/panel reveal = `base`; modal = `slow`; nothing ≥ 300 ms on the sales screen. Keyboard-triggered actions get zero/`fast` — no animation debt between F9 and save.

---

## 3. Theme token sheets (fully enumerated)

### 3.1 Dark theme — `[data-theme="dark"]` (supported alternate, P02)

**Primitives (verbatim client spec):**
`bg-0 #1e1e1e · bg-1 #262626 · bg-2 #363636 · bg-3 #3f3f3f · text-0 #dadada · text-1 #999999 · text-2 #808080 · text-3 #ffffff · accent #a882ff · accent-hover #b99aff · high #fb464c · med #f0ee5a · low #44cf6e`

| Semantic token | Value | Notes |
|---|---|---|
| `--color-bg-app` | `30 30 30` (#1e1e1e) | canvas |
| `--color-bg-surface` | `38 38 38` (#262626) | cards, panels, table base |
| `--color-bg-raised` | `54 54 54` (#363636) | popovers, inputs on surface, table header |
| `--color-bg-overlay` | `63 63 63` (#3f3f3f) | top elevation, hover on raised |
| `--color-bg-input` | `30 30 30` (#1e1e1e) | inset form field |
| `--color-bg-well` | `26 26 26` (#1a1a1a) | derived; monitor/inset wells, qty bar track |
| `--color-bg-scrim` | `0 0 0 / 60%` | modal backdrop |
| `--color-text-primary` | `218 218 218` (#dadada) | AA/AAA on all four dark surfaces (11.9–7.5) |
| `--color-text-secondary` | `153 153 153` (#999999) | **on bg-app/bg-surface only** (5.85 / 5.31 AA) |
| `--color-text-secondary-strong` | `172 172 172` (#acacac) | derived; secondary on bg-raised/overlay (5.32–4.64 AA) |
| `--color-text-muted` | `128 128 128` (#808080) | large/non-essential/disabled-leaning only (fails small text) |
| `--color-text-muted-strong` | `158 158 158` (#9e9e9e) | derived; small muted up to bg-raised (4.51 AA) |
| `--color-text-disabled` | `110 110 110` (#6e6e6e) | derived; disabled controls (exempt) |
| `--color-text-placeholder` | `128 128 128` (#808080) | see §6 note |
| `--color-text-inverse` | `30 30 30` (#1e1e1e) | text on accent/priority solid fills |
| `--color-text-on-accent` | `30 30 30` (#1e1e1e) | 5.80 AA on #a882ff |
| `--color-accent` | `168 130 255` (#a882ff) | as small text: bg-app (5.80)/surface (5.26) only |
| `--color-accent-hover` | `185 154 255` (#b99aff) | text-safe on ALL dark surfaces (≥4.58 AA); hover for accent text on raised |
| `--color-accent-active` | `196 173 255` (#c4adff) | derived; pressed state (8.55 on app) |
| `--color-accent-soft` | `56 51 68` (#383344) | derived; 14% accent over bg-surface — selected chip/menu |
| `--color-accent-border` | `110 90 150` (#6e5a96) | derived; accent-tinted border |
| `--color-accent-contrast` | `30 30 30` (#1e1e1e) | text on accent fill |
| `--color-border` | `54 54 54` (#363636) | hairline on surface |
| `--color-border-strong` | `63 63 63` (#3f3f3f) | inputs, dividers |
| `--color-border-faint` | `46 46 46` (#2e2e2e) | derived; subtle grid lines |
| `--color-priority-high-text` | `251 70 76` (#fb464c) | **on bg-app only** (4.83 AA); see high-text-strong elsewhere |
| `--color-priority-high-text-strong` | `255 123 128` (#ff7b80) | derived; high text on bg-surface (6.05) / bg-raised (4.83) |
| `--color-priority-high-soft` | `64 42 43` (#402a2b) | derived; 12% red over surface — stock-flag bg |
| `--color-priority-high-solid` | `251 70 76` (#fb464c) | badge/banner fill |
| `--color-priority-high-on-solid` | `30 30 30` (#1e1e1e) | 4.83 AA on #fb464c |
| `--color-priority-medium-text` | `240 238 90` (#f0ee5a) | AA/AAA on all dark surfaces (≥8.57) |
| `--color-priority-medium-soft` | `62 62 44` (#3e3e2c) | derived; 12% amber over surface |
| `--color-priority-medium-solid` | `240 238 90` (#f0ee5a) | badge fill |
| `--color-priority-medium-on-solid` | `30 30 30` (#1e1e1e) | 13.56 AAA |
| `--color-priority-low-text` | `68 207 110` (#44cf6e) | AA/AAA on all dark surfaces (≥5.21) |
| `--color-priority-low-soft` | `42 58 47` (#2a3a2f) | derived; 12% green over surface |
| `--color-priority-low-solid` | `68 207 110` (#44cf6e) | badge fill |
| `--color-priority-low-on-solid` | `30 30 30` (#1e1e1e) | 8.25 AAA |
| `--color-success-* / warning-* / danger-*` | = low / medium / high group respectively | aliases |
| `--color-info-*` | = accent group | no blue in brand palette; info = purple |
| `--color-control-bg` | `38 38 38` (#262626) | default button/field |
| `--color-control-bg-hover` | `54 54 54` (#363636) | |
| `--color-control-bg-active` | `63 63 63` (#3f3f3f) | |
| `--color-control-bg-disabled` | `38 38 38` (#262626) | + opacity .5 handled by component |
| `--color-control-border` | `63 63 63` (#3f3f3f) | |
| `--color-control-border-focus` | `168 130 255` (#a882ff) | 5.80 AA on app |
| `--color-focus-ring` | `185 154 255` (#b99aff) | 6.58 AA on surface; offset `2px` into bg-app |
| `--color-selection-bg` | `168 130 255 / 35%` | text selection |
| `--color-table-bg` | `30 30 30` (#1e1e1e) | |
| `--color-table-stripe` | `38 38 38` (#262626) | zebra (given palette, clean) |
| `--color-table-hover` | `46 46 46` (#2e2e2e) | derived |
| `--color-table-selected` | `54 54 54` (#363636) | given palette |
| `--color-table-header-bg` | `38 38 38` (#262626) | |
| `--color-table-header-text` | `172 172 172` (#acacac) | secondary-strong |
| `--color-table-border` | `46 46 46` (#2e2e2e) | row hairlines |
| `--color-table-totals-bg` | `44 40 52` (#2c2834) | derived; 10% accent over app — totals strip |
| `--color-table-sticky-bg` | `30 30 30 / 92%` | frosted sticky inline-end column |
| `--color-pos-line` | `46 46 46` (#2e2e2e) | POS gridlines |
| `--color-pos-totals-bg` | `26 26 26` (#1a1a1a) | pinned totals strip |
| `--color-pos-key-bg` | `38 38 38` (#262626) | qty/expiry bar keys |
| `--color-pos-key-accent` | `51 47 60` (#332f3c) | derived; 10% accent over surface — active key |
| `--color-pos-total-accent` | `185 154 255` (#b99aff) | grand total figure |
| `--chart-1..6` | `#a882ff #44cf6e #f0ee5a #fb464c #acacac #dadada` | series palette |

**Dark derived-state recipes (used by components, listed so states are build-ready):**
- Button primary: fill `accent`, text `accent-contrast` (#1e1e1e), hover `accent-hover` (text stays #1e1e1e: 7.25 AAA), active `accent-active`, focus `accent-glow`.
- Button destructive: fill `priority-high-solid`, text `priority-high-on-solid`, hover lighten → derived `#ff6468` (text #1e1e1e), active `#ff8080`.
- Ghost/outline hover bg: `control-bg-hover`; disabled: `text-disabled` + `control-bg-disabled`.
- Zebra: `table-stripe` on `table-bg`; hover overlays `table-hover`; selected `table-selected` + `accent` left/start rule.
- Stock flags: `low` → `priority-low-soft` bg + `priority-low-text` (or `-text-strong`); near-expiry amber; expired `priority-high-soft` + `priority-high-text-strong`.

### 3.2 Light theme — `:root` (brand default, P02)

**Primitives (verbatim client spec):**
`bg-0 #ffffff · bg-1 #f5f5f5 · bg-2 #e8e8e8 · bg-3 #e0e0e0 · text-0 #1e1e1e · text-1 #666666 · text-2 #999999 · text-3 #ffffff · accent #7c5cbf · accent-hover #6a4da8 · high #e03e3e · med #9a8f10 · low #36a854`

| Semantic token | Value | Notes |
|---|---|---|
| `--color-bg-app` | `255 255 255` (#ffffff) | canvas |
| `--color-bg-surface` | `245 245 245` (#f5f5f5) | cards/panels |
| `--color-bg-raised` | `232 232 232` (#e8e8e8) | popovers, table header |
| `--color-bg-overlay` | `224 224 224` (#e0e0e0) | top elevation, hover on raised |
| `--color-bg-input` | `255 255 255` (#ffffff) | inset field |
| `--color-bg-well` | `248 248 248` (#f8f8f8) | derived; wells, qty bar track |
| `--color-bg-scrim` | `0 0 0 / 45%` | modal backdrop |
| `--color-text-primary` | `30 30 30` (#1e1e1e) | AAA on all light surfaces (≥12.63) |
| `--color-text-secondary` | `102 102 102` (#666666) | **on bg-app/surface/raised** (5.74–4.69 AA) |
| `--color-text-secondary-strong` | `92 92 92` (#5c5c5c) | derived; secondary on bg-overlay (5.07 AA) |
| `--color-text-muted` | `110 110 110` (#6e6e6e) | derived from #999999; #999999 fails (2.85); #6e6e6e passes on app/surface (5.10 / ~4.7) |
| `--color-text-muted-strong` | `92 92 92` (#5c5c5c) | small muted on e0e0e0 (5.07 AA) |
| `--color-text-disabled` | `153 153 153` (#999999) | brand hex kept; disabled controls (exempt) |
| `--color-text-placeholder` | `110 110 110` (#6e6e6e) | see §6 |
| `--color-text-inverse` | `255 255 255` (#ffffff) | on accent solid |
| `--color-text-on-accent` | `255 255 255` (#ffffff) | 5.07 AA on #7c5cbf |
| `--color-accent` | `124 92 191` (#7c5cbf) | small text on app/surface (5.07 / 4.65 AA) |
| `--color-accent-hover` | `106 77 168` (#6a4da8) | text-safe on ALL light surfaces (≥4.91 AA); hover for accent text on raised |
| `--color-accent-active` | `91 66 150` (#5b4296) | derived; pressed (7.88 on white) |
| `--color-accent-soft` | `239 235 247` (#efebf7) | derived; 12% accent over white — selected chip/menu |
| `--color-accent-border` | `186 175 220` (#baafdc) | derived; accent-tinted border |
| `--color-accent-contrast` | `255 255 255` (#ffffff) | text on accent fill |
| `--color-border` | `224 224 224` (#e0e0e0) | hairline |
| `--color-border-strong` | `208 208 208` (#d0d0d0) | derived; inputs, dividers |
| `--color-border-faint` | `232 232 232` (#e8e8e8) | subtle grid lines |
| `--color-priority-high-text` | `179 38 30` (#b3261e) | derived from #e03e3e (fails 4.26); #b3261e = 6.54 AA on white, 4.95 on e0e0e0 |
| `--color-priority-high-text-strong` | `179 38 30` (#b3261e) | same — single passing red for text |
| `--color-priority-high-soft` | `251 232 232` (#fbe8e8) | derived; 12% red over white — stock-flag bg |
| `--color-priority-high-solid` | `224 62 62` (#e03e3e) | brand fill kept; use white text ≥14px bold, or `-on-solid` #1e1e1e |
| `--color-priority-high-on-solid` | `255 255 255` (#ffffff) | 4.26 — passes as large/UI text (≥3:1), not small |
| `--color-priority-medium-text` | `122 106 0` (#7a6a00) | derived from #9a8f10 (fails 3.33); 5.40 AA on white |
| `--color-priority-medium-soft` | `243 242 226` (#f3f2e2) | derived; 12% olive over white |
| `--color-priority-medium-solid` | `154 143 16` (#9a8f10) | brand fill; text `on-solid` #1e1e1e (5.01 AA) |
| `--color-priority-medium-on-solid` | `30 30 30` (#1e1e1e) | |
| `--color-priority-low-text` | `47 125 79` (#2f7d4f) | derived from #36a854 (fails 3.05); 5.04 AA on white |
| `--color-priority-low-soft` | `231 245 234` (#e7f5ea) | derived; 12% green over white |
| `--color-priority-low-solid` | `54 168 84` (#36a854) | brand fill; text `on-solid` #1e1e1e (5.47 AA) |
| `--color-priority-low-on-solid` | `30 30 30` (#1e1e1e) | |
| `--color-success-* / warning-* / danger-*` | = low / medium / high | aliases |
| `--color-info-*` | = accent group | |
| `--color-control-bg` | `255 255 255` (#ffffff) | |
| `--color-control-bg-hover` | `245 245 245` (#f5f5f5) | |
| `--color-control-bg-active` | `232 232 232` (#e8e8e8) | |
| `--color-control-bg-disabled` | `245 245 245` (#f5f5f5) | |
| `--color-control-border` | `208 208 208` (#d0d0d0) | derived |
| `--color-control-border-focus` | `106 77 168` (#6a4da8) | 6.48 AA on white |
| `--color-focus-ring` | `106 77 168` (#6a4da8) | 6.48 AA on app; offset 2px into bg-app |
| `--color-selection-bg` | `124 92 191 / 25%` | |
| `--color-table-bg` | `255 255 255` (#ffffff) | |
| `--color-table-stripe` | `245 245 245` (#f5f5f5) | zebra |
| `--color-table-hover` | `242 242 242` (#f2f2f2) | derived |
| `--color-table-selected` | `232 232 232` (#e8e8e8) | |
| `--color-table-header-bg` | `245 245 245` (#f5f5f5) | |
| `--color-table-header-text` | `92 92 92` (#5c5c5c) | secondary-strong |
| `--color-table-border` | `232 232 232` (#e8e8e8) | |
| `--color-table-totals-bg` | `242 239 249` (#f2eff9) | derived; 10% accent over white |
| `--color-table-sticky-bg` | `255 255 255 / 94%` | frosted sticky column |
| `--color-pos-line` | `232 232 232` (#e8e8e8) | |
| `--color-pos-totals-bg` | `248 248 248` (#f8f8f8) | pinned totals strip |
| `--color-pos-key-bg` | `245 245 245` (#f5f5f5) | |
| `--color-pos-key-accent` | `239 235 247` (#efebf7) | active key |
| `--color-pos-total-accent` | `106 77 168` (#6a4da8) | grand total figure |
| `--chart-1..6` | `#7c5cbf #36a854 #9a8f10 #e03e3e #5c5c5c #1e1e1e` | series palette |

**Light derived-state recipes (component-ready):**
- Button primary: fill `accent` (#7c5cbf) + white text (5.07 AA), hover `accent-hover` (#6a4da8, 6.48), active `accent-active` (#5b4296), focus `accent-glow`.
- Button destructive: fill `priority-high-solid` #e03e3e — white text passes only as large; for normal-size buttons use `priority-high-text` #b3261e as fill with white text (4.26→ actually 6.54) — decision folded into component recipe: **destructive buttons use #b3261e fill in light theme** (`danger-solid-strong`). I'll add token alias `--color-danger-solid-strong` = #b3261e to the light sheet.

*(Add to light sheet, missing row above:)*
| `--color-danger-solid-strong` | `179 38 30` (#b3261e) | derived; destructive button fill w/ white text (6.54 AA) |

- Badges: `-soft` bg + `-text-strong` text; solid chips only for large/status (≥14px bold) or dark-text-on-solid combos above.
- Zebra `table-stripe` on `table-bg`; hover `table-hover`; selected `table-selected` + accent start rule.

---

## 4. Component-styling approach

### 4.1 CSS variables + Tailwind mapping

- Tokens live in `packages/ui/src/styles/tokens.css`; **light in `:root` (brand default per P02)**, dark under `[data-theme="dark"]`; all semantic colors stored as `R G B` triplets.
- Tailwind maps each semantic token to a utility name so markup reads `bg-app text-primary border` etc. (v4 `@theme inline` / v3 `extend`). Alpha via `<alpha-value>`: `bg-accent/20`.
- A tiny `TokenPanel` dev component (storybook/story route) renders the full sheet for audit.
- Components are shadcn-style (Radix + Tailwind, per 03 §5). Recipes (Button, Badge, Input, DataGrid, Card, Dialog, Toast, Tabs, Dropdown) reference semantic tokens exclusively. **No component imports a primitive hex, ever** (D1 enforcement; lint rule `no-primitive-colors`).

### 4.2 Theme switching (light default / dark alternate — P02)

1. `defaultTheme = 'light'` — **light is the brand default on BOTH web + desktop**; dark is the supported alternate (night-shift POS still reachable via the switch or `system`).
2. Settings: `system | light | dark`. In `system`, flip `data-theme` on a `matchMedia('(prefers-color-scheme: dark)')` listener (desktop Tauri uses the same listener; persisted to app config).
3. **Anti-flash:** inline `<script>` in `head` (both apps) reads persisted value and sets `document.documentElement.dataset.theme` before first paint; no FOUC, no async flash — important for the 1-PM day-close / login flow.
4. Persistence: web = `localStorage['pharmatag:theme']`; desktop = Tauri `app_config` via the same store abstraction (`packages/core` settings repo). One hook `useTheme()` in `packages/ui` wrapping both.
5. Components never read the theme; only CSS vars react. Toggling is O(1) style recalc — POS stays at 60fps.

### 4.3 RTL / LTR flipping strategy

- `dir="rtl"` + `lang="ar"` default; `dir="ltr"` + `lang="en"` in English mode. **Never** flip via CSS on the same DOM — switch the attribute (matches 03 §3.3).
- All layout uses logical properties: `ms-* me-* ps-* pe-* inset-inline-start/end start-0 end-0` (Tailwind logical utilities). No `left/right` in layout.
- Directional glyphs (chevrons, arrows, sort indicators, carousel) mirrored with a `[dir="rtl"] &:-rotate-180` utility class, not new assets.
- Sticky columns: row-number/action column pinned to **inline-end** (right edge in RTL) — `position: sticky; inset-inline-end: 0`; frosted via `table-sticky-bg`.
- Numeric/money columns stay LTR inside RTL cells (`dir="ltr"` span + `unicode-bidi: plaintext`); dates via `Intl.DateTimeFormat('ar-EG')`; charts (recharts) reverse the x-axis in RTL (03 §3.3).
- Scrollbars: RTL-aware; browsers handle edge alignment when layout is logical.

---

## 5. Key screen style guide

### 5.1 Login / activation (`/login`, `/activate`)

- Centered card (max-width 400px) on `bg-app`; subtle `accent` radial glow (10% opacity) behind card; `bg-surface` card, `border` hairline, `shadow-lg`.
- Vertical brand lockup (§1.3): mark (40–56px) → `فارما تاج` (Thmanyah Serif Display SemiBold 24) → `PharmaTag` muted caption.
- Fields: user, password, branch selector (listbox, RTL); "تذكر الفرع" optional. Primary button = full-width `accent` fill, white/dark text per recipe.
- **Day/date banner:** amber `priority-medium-soft` strip under the lockup when the day-close guard applies ("لا يمكن تقفيل اليوم الحالي الا بعد الواحدة ظهرا") — contextual, not decorative.
- Activation gate: same card, adds a license/key field, `warning` icon (amber) + `priority-high` error line on failure; disabled state grays the whole card (text-disabled).
- Permission-aware nav reveal: after auth, the rail renders only permitted modules (muted until granted).

### 5.2 POS invoice entry (`/pos`) — keyboard-first, totals bar, stock flags

- **Layout:** full-height workspace. Top `header bar` (invoice no, date, writer, branch, kind badge — saved/unsaved/copy states via `StatusChip`). Middle: `InvoiceLinesGrid` (dense, `data-density=sm`, tabular money, row hover `table-hover`). Bottom pinned: `TotalsStrip` (`pos-totals-bg`, top border `border-strong`) then `PaymentSplitBar` then `SaveBar`.
- **TotalsStrip:** subtotal / discount / VAT / **grand total** — grand total in `pos-total-accent`, Thmanyah Serif Display Bold 28–32, tabular-nums, inline-end aligned (right in RTL). 
- **QtyExpiryBar:** bottom sheet `pos-key-bg` keys, 44–48px touch targets, `pos-key-accent` on the active unit/expiry key; ↑/↓ keyboard selection of batch with live batch stock; expiry-must-be-chosen-first warning = amber `priority-medium-soft` chip; `+`/`−` steppers at `sm` row height but 48px hit area.
- **Stock flags (priority colors):** per-line inline-end status cell — `priority-low-soft`+`-low-text` for **low stock** (at/below minimum), `priority-medium` for **near-expiry** (≤90 days), `priority-high-soft`+`-high-text-strong` for **expired/blocked**; insufficient stock blocks save with a `priority-high-solid` banner (not a toast — must persist until resolved).
- Scan feedback: 100 ms `accent` border flash on the focused scan field; duplicate/unknown barcode → red flash + inline error.
- Save bar: `حفظ F9` primary, `الغاء الحفظ F12` ghost, `طباعة` outline, auto-print toggle; unsaved-invoice warning chip amber.

### 5.3 Drug search-as-you-type (`DrugSearchCombobox`)

- `bg-surface` dropdown, `shadow-md`, radius `lg`, max-height ~50vh scroll.
- Rows: primary = Arabic name (weight 500) + Latin name muted under it; columns inline-end: current stock (priority-colored), last sale price, monthly qty, 6th barcode chip.
- Keyboard: Enter adds, ↑/↓ moves (POS muscle memory); `/` opens global command palette.
- **Similar-name duplicate guard:** a row/bar in `priority-medium-soft` with `-medium-text` "الادوية المتشابهة: …" listing near matches to prevent dupes (drug pricing doc §2.1 behavior).
- Match highlighting: matched substring in `accent-hover` (dark) / `accent` (light).

### 5.4 Dense table / report styling (`DataGrid`, `ReportView`)

- `data-density=sm` default in POS/report grids: 28px rows, 11–12px text, `tabular-nums` money, `table-border` row hairlines, zebra `table-stripe`.
- Sticky: header row (bg `table-header-bg`, text `table-header-text`, `shadow-xs`) + inline-end action column (frosted `table-sticky-bg`).
- Totals/group subtotals: `table-totals-bg` strip pinned bottom; group subtotal rows get a 3px `accent` start-rule + bold weight.
- Filters bar above grid: compact inputs, `control-border` hairline; export menu (PDF/Excel/CSV/clipboard) icon-only, hover `control-bg-hover`.
- Print: separate fixed print stylesheet (`@page` A4/A5/80mm, black-on-white regardless of active theme, `print-color-adjust: exact` only for priority chips); the grid's theme never leaks into printed reports.

### 5.5 Sync-conflict notification / badge

- **App-bar chip (shell, 03 §5.1):** pending push count = `accent-soft` chip with accent text (count in `tabular-nums`); **offline** = `text-muted` chip with `dot`; **unresolved conflicts** = `priority-medium-soft` chip with count, escalating to `priority-high` when a conflict touches invoices/drawer (danger: silent money divergence).
- Banner under app bar when conflicts exist: `priority-medium-soft`/`-medium-text`, "توجد تعارضات بحاجة للمراجعة — N" + "مراجعة" button → `SyncConflictPanel`.
- `SyncConflictPanel`: rows show `my value` vs `their value` (both in tabular-nums), LWW-recommended row pre-highlighted `table-selected`; actions Keep mine (primary) / Keep theirs (outline) / Auto (ghost) with the "Auto" as the non-destructive default (03 §4.2).

### 5.6 Setup / activation / "plugin & install" surfaces

*`plan/08_app_architecture_plugins.md` **exists** (A08–A12; pilot plugins `pharmatag-eta`/`pharmatag-ledger`); its "plugin surfaces" = first-run wizard, activation gate, and integrations hub (see Open decision #1 → resolved).*

- **First-run wizard (`/setup`, FormFirstStart):** step card (max-width 560px) on `bg-app`, progress steps as numbered accent dots; fields = pharmacy name/address/phone, CR, tax no, currency/VAT defaults; final step shows `.phy` import option with per-file status chips (`OK` = `priority-low-soft`/`-low-text`, `UNKNOWN_LAYOUT` = `priority-medium`, failed = `priority-high`), `LongTaskProgress` bar at `pos-key-accent` fill.
- **Integrations hub (`/settings/integrations`):** responsive card grid — each card = icon + Arabic name + short description + status badge (`متصل` green, `غير متصل` gray, `يتطلب تفعيل/رخصة` amber) + enable toggle; disabled/unlicensed cards render at 50% opacity with `text-disabled`. ZATCA card shows submission-status via `StatusChip` (reports RPT-EI01).
- **Printers (`/settings/printers`):** per-purpose rows with a live "paper" preview swatch (A4/A5/80mm), each mapped to a printer + paper + copies; `border` cards on `bg-surface`.

---

## 6. Accessibility — measured, with adjustments

Verified ratios (WCAG 2.1, small text ≥4.5:1):

**Dark theme**

| Pair | Ratio | Verdict |
|---|---|---|
| #dadada on #1e1e1e / #262626 / #363636 / #3f3f3f | 11.93 / 10.83 / 8.64 / 7.53 | AA+AAA ✓ all |
| #ffffff on any dark surface | ≥10.53 | AAA ✓ |
| #999999 on #1e1e1e / #262626 | 5.85 / 5.31 | AA ✓ |
| #999999 on #363636 / #3f3f3f | 4.24 / 3.70 | ✗ **fails** |
| #808080 on #1e1e1e (best case) | 4.22 | ✗ **fails everywhere** |
| #a882ff on #1e1e1e / #262626 | 5.80 / 5.26 | AA ✓ |
| #a882ff on #363636 / #3f3f3f | 4.20 / 3.66 | ✗ **fails** |
| #b99aff on all dark surfaces | ≥4.58 | AA ✓ |
| #fb464c on #1e1e1e | 4.83 | AA ✓ (barely) |
| #fb464c on #262626 | 4.38 | ✗ **fails** |
| #f0ee5a, #44cf6e on all dark | ≥5.21 | AA ✓ (amber AAA) |
| #1e1e1e on #a882ff / #fb464c / #44cf6e | 5.80 / 4.83 / 8.25 | AA ✓ (text-on-fill) |
| #ffffff on #a882ff / #fb464c / #44cf6e | 2.88 / 3.45 / 2.02 | ✗ white-on-fill fails — **use dark text on bright fills** |

**Light theme**

| Pair | Ratio | Verdict |
|---|---|---|
| #1e1e1e on all light surfaces | ≥12.63 | AAA ✓ |
| #666666 on #ffffff / #f5f5f5 / #e8e8e8 | 5.74 / 5.27 / 4.69 | AA ✓ |
| #666666 on #e0e0e0 | 4.35 | ✗ **fails** |
| #999999 on #ffffff | 2.85 | ✗ **fails** — biggest light-theme problem |
| #7c5cbf on #ffffff / #f5f5f5 | 5.07 / 4.65 | AA ✓ |
| #7c5cbf on #e8e8e8 / #e0e0e0 | 4.14 / 3.84 | ✗ **fails** |
| #6a4da8 on all light surfaces | ≥4.91 | AA ✓ |
| #ffffff on #7c5cbf / #6a4da8 | 5.07 / 6.48 | AA ✓ (accent fill works in light) |
| #e03e3e / #9a8f10 / #36a854 on white | 4.26 / 3.33 / 3.05 | ✗ **all fail as small text** |

**Adjustments that keep brand feel (all additive — primitives untouched):**
1. **Dark secondary/muted:** route body text through `text-secondary-strong` #acacac on raised surfaces; keep #999999 on the two darkest layers. #808080 stays a primitive used only for disabled/placeholder/large text.
2. **Dark accent text:** on `bg-raised`/`bg-overlay` use `accent-hover` #b99aff (passes 5.25/4.58). #a882ff remains for fills and on dark-app/surface text.
3. **Dark red text:** #fb464c only on `bg-app`; elsewhere `priority-high-text-strong` #ff7b80. Fills keep dark text (#1e1e1e) — never white on bright fills.
4. **Light muted:** #999999 is demoted to disabled-only; content muted = #6e6e6e.
5. **Light priority as text:** use derived `#b3261e` / `#7a6a00` / `#2f7d4f`; the brand hexes remain for fills, chips (with dark text), and ≥24px figures (3:1 large-text/UI threshold).
6. **Focus rings:** `#b99aff` dark / `#6a4da8` light, both ≥5.9:1 against their surfaces — exceeds the 3:1 non-text requirement.
7. **Placeholder text** is exempted by WCAG 1.4.3's *"text that is part of an inactive user interface component"* reading for placeholders, but we still use `text-placeholder` ≥ `#808080`-adjacent and keep real labels above every field (no placeholder-only labels).
8. Keep a `data-density` + zoom/`text-size` accessibility setting; ensure the POS at `sm` density still meets `prefers-reduced-motion`.

Net effect: **the delivered palette passes AA/AAA after the derived-token layer**, and the raw brand hexes are preserved for large fills, logos, and brand surfaces.

---

## 7. Open decisions — all resolved 2026-08-16 (decision IDs in 00 master)

1. **"Plugin/install screen" meaning.** No `08_app_architecture_plugins.md` exists. Do you mean (a) first-run setup/activation wizard + `.phy` import, (b) a future Tauri plugin/extension UI, or (c) the integrations hub? This plan styles (a)+(c); confirm. — **✅ RESOLVED → A10/A11 (plan/08 exists):** plugin surfaces = first-run wizard + integrations hub; pilot plugins `pharmatag-eta` + `pharmatag-ledger` (bundle-all + signed enablement, no DRM).
2. **Logo mark + tagline.** Pick Option A/B/C (§1.1) and tagline #1–#4 (§1.4). Recommend A + tagline 1, "دقة. سرعة. تاج." for splash. — **✅ RESOLVED → P01:** Option A "Tag-Cross" + tagline #1 `صيدليتك، متوّجة بالدقة`; splash `دقة. سرعة. تاج.`
3. **Dark default vs follow-system.** Recommend dark-by-default with `system|dark|light` setting. Do you also want light-by-default on the web app, or is dark the single brand default on both platforms? (Recommend dark on both.) — **✅ RESOLVED → P02:** **light = brand default on BOTH platforms**; dark = supported alternate; `system | light | dark` switch architecture unchanged.
4. **Derived-token extensions.** The plan adds ~10 derived hexes per theme (accent-hover reuse, priority text-strong, soft tints, secondary/muted-strong) to hit WCAG. Approve as brand extensions, or keep strictly to the given hexes and accept failing small-text contrast on some surfaces? — **✅ RESOLVED → P03:** derived-WCAG tokens approved.
5. **Light destructive button fill.** Recommend #b3261e fill (passes with white text) in light theme instead of brand #e03e3e for normal-size buttons. OK? — **✅ RESOLVED → P03:** approved via the derived-token layer (token alias `--color-danger-solid-strong` = #b3261e).
6. **POS density default.** Recommend `sm` (28px) rows in the invoice lines grid, `md` (34px) in lists, `lg`/48px touch in qty bar. Is 28px rows acceptable for your users, or must rows be ≥32px for touch? — **✅ RESOLVED → P04:** sm 28px invoice rows / md 34px lists / lg 48px touch.
7. **Fonts.** Confirm IBM Plex Sans Arabic + Cairo (from 03 §3.3) as locked, and approve IBM Plex Sans (Latin) + IBM Plex Mono (digits) as the pairing. Any preference for Noto Kufi Arabic or Cairo-only display? — **✅ RESOLVED → P05:** **Thmanyah family** per `bookmarkX/docs/style-guide.md` §3 (UI Sans 300–900 / Serif Display headings / Serif Text body); fallback IBM Plex Sans Arabic / Noto Kufi. IBM Plex Mono retained for Latin digits.
8. **Focus-ring color.** Recommend `accent-hover` (#b99aff dark / #6a4da8 light) for the 3px focus ring, not `accent` — the hover value is the passing one on raised surfaces. OK? — **✅ RESOLVED → P06:** focus ring = accent-hover.
9. **Print theming.** Confirm printed reports/invoices are always black-on-white (fixed CSS) regardless of active app theme (this plan's choice), and that priority chips keep color via `print-color-adjust: exact`. — **✅ RESOLVED → P06:** print always black-on-white; chips keep color via `print-color-adjust: exact`.
10. **Bilingual labels on-screen.** 03 §3.3 proposes Arabic primary + English muted caption (training mode). Confirm this lives only behind a toggle, so the default POS stays Arabic-only clean. — **✅ RESOLVED → P06:** bilingual behind toggle; default POS Arabic-only.

---

## 8. Assumptions (stated explicitly)

1. `packages/ui` owns tokens/fonts (03 §1.2); Tailwind + shadcn-style component approach from 03 §5.
2. **Light is the default theme and the brand surface** for all screens (P02); dark is the supported alternate (night-shift POS), selectable via `system | light | dark`.
3. The client hex palette is non-negotiable and preserved as primitives; every WCAG fix is additive via derived semantic tokens.
4. No blue is added for `info` — info = accent purple (per palette).
5. Arabic is the layout's structural direction (RTL); English is a mirrored display mode, not a redesign.
6. The legacy `.phy`-era "themes/colors" settings (FFFColors, FormStyles) are not replicated as user-themable color schemes in P1 — the two hard themes replace them (03 §2.11 folds FormStyles/FFFColors into advanced settings).
7. Fonts are the **Thmanyah family** (self-hosted, offline desktop; no CDN) per P05 / `bookmarkX/docs/style-guide.md` §3.
8. Print output is theme-independent (always readable black-on-white A4/A5/80mm), per the legacy ModPrint contract (feature_reports_analytics §4).
9. Charts use the brand series palette (§2.5 `chart-1..6`), recharts, RTL-reversed where meaningful (03 §3.3).
10. "Plugin/install screen" **resolved (A10/A11):** first-run/activation + integrations hub; pilot plugins `pharmatag-eta` + `pharmatag-ledger` (plan/08 exists per 00 master sources).

---

### Summary for the user

- **Token architecture:** two layers — brand *primitives* (your exact hexes) + *semantic* tokens named per the bookmarkX style guide (P05: `--background-primary/-secondary/-tertiary`, `--text-normal/-muted/-faint`, `--accent-color/-hover`, `--priority-*`, `--color-error`/`--color-success`, `--space-*`/`--radius-*`/`--shadow-*`/`--transition-*`/`--z-*`) + a PharmaTag derived-WCAG layer, stored as CSS variables (RGB triplets), mapped 1:1 into Tailwind. Components touch only semantic tokens, so theme switching is a pure CSS swap with no re-render and no component forks. Density (POS rows 28/34/40px + 44–48px touch), spacing, radius, typography (Thmanyah Sans / Serif Display / Serif Text, self-hosted — P05), elevation, and ≤150ms motion are all tokenized.
- **Theme switch:** `data-theme` on `<html>`, **light default** (P02), `system|light|dark` via a pre-paint inline script + persisted store; RTL is structural (logical properties, sticky inline-end column, mirrored glyphs, reversed charts).
- **Contrast issues found in your palette (real, must be handled):**
  - Dark: `#999999` fails on `#363636`/`#3f3f3f` (4.24/3.70); `#808080` fails everywhere (≤4.22); `#a882ff` fails on the two raised greys (4.20/3.66); `#fb464c` fails off `#1e1e1e` (4.38 on `#262626`).
  - Light: `#999999` fails everywhere (≤2.85); `#7c5cbf` fails on `#e8e8e8`/`#e0e0e0`; `#666666` fails on `#e0e0e0`; **all three priority colors fail as small text** (4.26/3.33/3.05).
  - Fix strategy: keep every brand hex, add derived passing tokens (`text-secondary-strong` #acacac dark / #5c5c5c light, muted-strong, priority text-strong #ff7b80 dark / #b3261e·#7a6a00·#2f7d4f light, soft tints, dark-text-on-bright-fills) — palette passes AA after the derived layer.
- **Open questions:** the 10 in §7 are **resolved** per 00 master (P01–P06) — #1 plugin surfaces = A10/A11, #2 logo/tagline = P01, #3 theme = P02, #4 derived tokens = P03, #5 destructive fill = P03, #6 density = P04, #7 fonts = P05, #8–#10 = P06.