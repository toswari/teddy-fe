# UI Coding Guidance for VideoLogoDetection

This document provides concrete guidelines for the front-end implementation of the VideoLogoDetection POC. It is written for coding agents who will implement the UI.

## 1. General Principles

- **Audience & Use Case**: Single-analyst forensic tool used on desktop/laptop, not mobile-first. Optimize for 1280–1920px width.
- **Look & Feel**: Modern, clean, light (non–dark mode) UI. Subtle, functional styling rather than flashy or “AI demo” aesthetics.
- **Consistency Over Novelty**: Prefer a small, consistent set of patterns (layout, typography, buttons) reused across screens.
- **Clarity First**: Prioritize information hierarchy, readability, and clear state indication (loading, error, success, in-progress).

## 2. Layout & Page Structure

- **Page Shell**
  - Fixed top header with application name: `VideoLogoDetection` and a small subtitle (e.g., "Forensic Video Analysis POC").
  - Left-side navigation (or a simple top-level tab bar) for primary sections:
    - Projects (project list and "continue" entry point)
    - Videos (scoped to active project)
    - Analysis / Mission Control (scoped to active project)
    - Reports (scoped to active project)
  - Main content area with a max-width container and consistent padding (e.g., `px-6 py-6`).

- **Layout Rules**
  - Use a **12-column grid** for complex layouts (especially the Mission Control dashboard) but keep sections simple (1–3 columns).
  - Use a vertical rhythm based on multiples of 4 or 8px (e.g., `gap-4`, `gap-6`, `py-4`, `py-6`).
  - Keep forms and tables left-aligned; avoid centering large blocks of text or controls.

## 3. Color, Typography & Spacing

- **Color Palette (Light Theme)**
  - Background: very light gray or off-white (e.g., `#F7FAFC`).
  - Surface cards: white (`#FFFFFF`) with subtle border (`#E2E8F0`) and soft shadow.
  - Primary accent: a single blue tone (e.g., `#2563EB`) for primary buttons, active states.
  - Secondary accent: a desaturated gray-blue (e.g., `#64748B`) for secondary actions and subtitles.
  - Status colors (sparingly):
    - Success: `#16A34A`
    - Warning: `#F59E0B`
    - Error: `#DC2626`

- **Typography**
  - Use a single sans-serif font family (e.g., system stack via Tailwind's default `font-sans`).
  - Heading scale:
    - Page title: `text-2xl font-semibold`
    - Section title: `text-xl font-semibold`
    - Subsection / card title: `text-lg font-medium`
  - Body text: `text-sm` or `text-base` with `leading-relaxed`.

- **Spacing**
  - Default outer page padding: `px-6 py-6`.
  - Card padding: `p-4` or `p-5`.
  - Vertical spacing between sections: `mt-6` or `mt-8`.

## 4. Tailwind CSS Usage Rules

The goal is to keep Tailwind usage maintainable and avoid long, AI-looking class chains.

- **Externalize Styling Where Practical**
  - All **custom styling beyond simple utility combinations** MUST be centralized in an external Tailwind CSS file (e.g., `ui.css` or `app.css`).
  - When you see the same utility pattern repeated across multiple components, extract it into a semantic class using `@apply`.
    - Example (conceptual):
      - Semantic class `.vd-card` that applies repeated card utilities.
      - Semantic class `.vd-primary-button` for the main button style.

- **Allowed Inline Utility Classes**
  - Structural layout: `flex`, `grid`, `items-center`, `justify-between`, `gap-*`, `w-*`, `h-*`.
  - Basic spacing: `p-*`, `m-*`, `px-*`, `py-*`, `mt-*`, `mb-*`.
  - Simple text styles: `text-sm`, `text-base`, `font-medium`, `font-semibold`, `text-gray-*`, `text-blue-*`.
  - Borders and backgrounds: `bg-*`, `border`, `border-*`, `rounded-*`, `shadow-sm`.

- **What to Move into CSS (`@apply`)**
  - Any button, card, tag/pill, or badge style repeated more than twice.
  - Complex stateful styles (hover, focus, disabled) should be captured in named classes.
  - Layout primitives used throughout (e.g., common card headers, panel shells).

- **Forbidden / Discouraged Patterns**
  - Overly long utility chains that reduce readability (more than ~10 classes on a single element).
  - Random gradients, glassmorphism, neon colors, or “futuristic AI” visuals.
  - Mixing conflicting utilities (e.g., multiple `px-*` or `bg-*` on the same element).

## 5. Component Design Guidance

Focus on a small, reusable set of components. Examples:

- **Top Navigation / Header**
  - Left: app name + version badge (e.g., `v0.x POC`).
  - Right: non-interactive environment label (e.g., "Local POC") and a simple icon for help / docs.

- **Sidebar / Section Navigation**
  - Use a vertical list of nav items with clear active state (bold text + left border or background highlight).
  - No icons are required; if used, keep them minimal and consistent.

- **Projects List & Continue Panel**
  - On the Projects view, show a "Recent Projects" card with the last few projects (name, last opened, key stats).
  - Provide a prominent "Continue last project" action in the header or Projects page if a recent project exists.
  - Clearly indicate the currently active project name in the header or a breadcrumb when the user is on Videos, Analysis, or Reports.

- **Cards & Panels**
  - Use cards for grouping related information (project info, video metadata, cost summary).
  - Each card:
    - Title row (title + optional small subtitle).
    - Content area with consistent padding and spacing.

- **Tables & Lists**
  - Use simple, clean tables for lists of projects, videos, and inference runs.
  - Avoid zebra-striping unless necessary; a subtle hover highlight is preferred.

- **Buttons**
  - Primary: filled, blue background, white text.
  - Secondary: outline or subtle neutral background.
  - Destructive: red text or red outline, used sparingly.

- **Forms**
  - Label each input clearly above the field.
  - Align fields vertically for most forms; use two-column layout only for wide screens and related fields.
  - Show helper text and validation messages directly below fields.

## 6. Mission Control / Dashboard Specifics

- **Layout**
  - Left: video player and timeline.
  - Right: detection list, model comparison controls, and cost panel stacked vertically.

- **Visualizations**
  - Timeline heatmap: simple horizontal strip with colored segments; avoid 3D or flashy charts.
  - Efficiency Matrix: a basic bar chart or simple table is sufficient. Keep colors aligned with the main palette.

- **Real-Time Feedback**
  - Use subtle loading indicators (spinners or skeletons) in-line with content.
  - Avoid full-screen loading overlays unless absolutely necessary.

## 7. Copy & Microcopy

- Use domain-appropriate, concise labels (e.g., "Run Analysis", "Estimate Cost", "Export Report").
- Avoid generic placeholder text like "Lorem ipsum" or "AI-generated" boilerplate; use meaningful examples tied to forensic video analysis.
- Messages should be neutral and professional, not playful or overly conversational.

## 8. What Makes It *Not* Look AI-Generated

- Consistent spacing, typography, and color usage across all pages.
- Limited number of component types, each clearly defined and reused.
- No random gradients, glassmorphism, or overly ornate backgrounds.
- No excessive icons or stock AI imagery; focus on data and controls.
- Domain-specific language and labels grounded in the VideoLogoDetection POC.

---

Coding agents MUST follow this guidance when implementing or modifying the UI. Any new component or layout should:

1. Reuse existing semantic classes where possible.
2. Keep Tailwind utility usage short and focused.
3. Preserve the light, modern, professional aesthetic described above.
