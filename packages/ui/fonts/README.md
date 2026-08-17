# Thmanyah fonts — drop-in directory (plan/09 P05)

PharmaTag self-hosts the **Thmanyah** family (UI Sans 300–900, Serif Display
headings, Serif Text body) plus **IBM Plex Mono** for Latin digits. The files
are proprietary/licensed and are **not committed** to this repo.

Drop the licensed WOFF2 files into this directory under the exact filenames
declared in `../styles/fonts.css`:

- `ThmanyahSans-300.woff2` … `ThmanyahSans-900.woff2`
- `ThmanyahSerifDisplay-600.woff2`
- `ThmanyahSerifText-400.woff2`, `ThmanyahSerifText-700.woff2`
- `IBMPlexMono-400.woff2`, `IBMPlexMono-600.woff2` (OFL — bundled with the app)

Until the files are present, every stack falls back to the plan/09 chain
`'Thmanyah', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
(see `tokens.css` `--pt-font-*`), so the shell renders correctly regardless.