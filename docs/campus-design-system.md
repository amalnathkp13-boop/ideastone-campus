# Campus visual system

Student Dashboard supplies the navy sidebar, blue actions, pale canvas and white
surfaces. Academics supplies the common heading scale, table treatment, borders,
radius and shadow. Both references render their headings in bundled Roboto; that
font now also covers body text and controls, replacing individual Inter/Segoe skins.

The shared file is `ideastone_campus/static/src/scss/design_system.scss`, registered
in both frontend and backend bundles. Every ERP addon depends on this base addon.
It covers student/parent portals, faculty and owner workspaces, native Odoo record
views and dialogs, AI/LMS screens, login, and faculty/HOD/COE question-paper roots.
Role navigation, content, data, permissions and workflows remain module owned.

| Role | Size | Weight | Color |
| --- | --- | --- | --- |
| Page heading (H1) | 31px; 28px below 768px | 760 | `#0e3151` |
| Section heading (H2 / panel heading) | 17px | 760 | `#102d49` |
| Item heading (H3) | 15px | 650 | `#102d49` |
| H4 / H5 / H6 | 14 / 13 / 12px | 650 | `#102d49` |
| Banner heading | 21px | 760 | White |
| Body / paragraph | 14 / 13px | 400 | Navy; muted descriptions `#617b96` |
| Table heading / cell | 12px | 750 / 400 | `#526f8f` / navy |
| Definition label / value | 12px | 400 / 600 | Muted / navy |
| Button / primary button / status chip | 12 / 12 / 11px | 650 / 750 / 700 | Semantic palette |
| Subnavigation title / tab | 13 / 12px | 700 / 400 (650 active) | Navy / `#425d78` |
| KPI number | 27px | 760 | Navy |

Canvas is `#f4f7fb`; cards are white with a 15px radius, `#dfe8f2` border and
`0 5px 18px rgba(19,48,78,.035)` shadow. Banners use the Academics
`#103958` to `#1c5b91` gradient. Primary actions use `#1769d2`; selected sidebar
items retain Dashboard's `#1668df`. Focus outlines remain visible. Reduced motion
preferences disable decorative transitions.

Success, pending, error, forwarded and informational states retain their meaning
through common green, amber, red, purple and blue foreground/background pairs.
Charts retain categorical colors so multiple series stay distinguishable.
FontAwesome/Odoo glyph fonts are excluded from text-font overrides.

The existing student, parent, faculty and owner browser suites call
`docs/qa/campus-theme.cjs` on their screenshots/navigation checkpoints. It checks
computed font family, heading sizes/weights/colors, theme loading and icon fonts.
Responsive layout checks in those suites remain enabled. New screens should use
semantic heading elements and the existing panel/button/status classes, rather
than introducing another local palette.
