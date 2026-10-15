# DESIGN.md - Dashboard Anti-Slop Directive
# Target: All Coding Agents | Project: Canvas Dashboards

This document contains strict visual, structural, and platform-specific constraints for generating and refactoring HTML-based Canvas dashboards. Every UI change, dashboard creation, or refactoring task must adhere to these rules. Do not default to generic, cluttered LLM templates.

---

## 1. Zero AI Slop Ban List (The "Never-Do" Rules)
You must proactively prune and ban these common LLM design hallucinations:

| Banned Element | Why It is Banned | Approved Alternative |
|---|---|---|
| **Inter / Roboto Fonts** | Overused, makes dashboards look like generic templates. | Use characterful pairing (e.g., Geist Sans, DM Sans, or system-serif for headers). |
| **Purple/Lavender Gradients** | The visual signature of low-effort AI UI. | Use flat, solid backgrounds. Use opacity or 1px borders for depth. |
| **Card-in-Card Nesting** | Creates visual clutter, excessive padding, and wasted space. | Use flat bento-style grids with thin borderless dividers. |
| **Useless Status Labels** | "Ready" or "Active" badges on every single element. | Only display status indicators when an item is in an error or critical state. |
| **Decorative Gridlines** | Background wire-frame grids that serve no functional purpose. | Keep gridlines strictly for actual charting/graphing areas. |
| **Decorative Icons** | Placing a generic icon next to every single metric card header. | Use plain text hierarchy. Icons must only represent actionable buttons. |

---

## 2. Canvas Environment & Technical Constraints
All dashboards must be built to run natively within the platform's Canvas environment.

* **Native Sandbox Execution:** The Canvas platform renders UI inside a sandboxed iframe. All dashboards must be self-contained, using native HTML5, modern CSS, and vanilla JavaScript (or via reliable, CDN-delivered ES modules).
* **Interactive Iteration:** UI elements must support dynamic rendering and iterative state updates. State should be managed seamlessly inside the client-side JS context.
* **Testability (dashboard.html):** For local verification and immediate platform rendering, you must emit the standalone HTML file as a user-facing artifact named `dashboard.html`. When doing so, use write_to_file with:
  `ArtifactMetadata: { UserFacing: true, Summary: "Interactive Evaluation Dashboard", RequestFeedback: false }`
  This ensures the file immediately opens and renders directly in the agent harness preview pane.
* **Production Data Only:** Never hardcode dummy or mock "lorem ipsum" data in the production rendering phase. The dashboard must process and render the actual, real-world data provided by the user session. Synthetic data is permitted only in the generated local test file.

---

## 3. Light and Dark Theme Specifications
The dashboard must natively support both a clean light mode and a high-contrast, modern dark mode.

* **Toggle Element:** The theme switcher must be a single, textless, minimalist button containing only an icon (e.g., a simple sun icon for light mode, moon icon for dark mode).
* **Color Schemes:**
  * **Light Mode:** 
    * Background: #FAFAF9 (Warm off-white)
    * Cards & Surfaces: #FFFFFF
    * Borders: #E7E5E4 (1px solid, 6px to 8px border-radius)
    * Text Primary: #1C1917
    * Text Secondary: #787774
  * **Dark Mode:**
    * Background: #0D0E11 (Deep charcoal, no pure pitch-black)
    * Cards & Surfaces: #16171D
    * Borders: #292A30 (1px solid, 6px to 8px border-radius)
    * Text Primary: #ECE8E2
    * Text Secondary: #9A9895

---

## 4. Modern Dashboard Layout & Element Rules
All dashboards must balance high information density with modern, ultra-clean design patterns. Use simple, direct, and to-the-point titles for all UI components.

* **Text Displays:** Keep explanatory headers short and to the point. No conversational AI text blocks in the UI. Let the data speak for itself.
* **Tables:** Tabular data must use monospaced fonts (e.g., Geist Mono or IBM Plex Mono) for clean, aligned reading. Use thin horizontal dividers instead of hard vertical borders.
* **3D Visualization Constraints:**
  * Only implement interactive 3D elements if they directly benefit the understanding of the underlying data.
  * Do not use the word "Physics" anywhere in the visible UI text or component titles. Use clean titles like "Interactive Relationship Node Map" or "Structural Data Diagram."
  * Keep any node/edge calculations clean and fast to prevent iframe performance lag.

---

## 5. Dynamic Data Visualization & Color Palette
While the dashboard container elements (cards, headers, background) must remain highly structured and minimalist, the data visualizations (charts, graphs, matrices, 3D molecular/network graphs) must be lively, vibrant, and highly legible. Do not render charts in grayscale. 

Use the following semantic and functional color palettes for data representation to make visualizations pop against light or dark backgrounds:

### Data Visualization Color Palette

| Color Role | Hex Code | Visual Application |
|---|---|---|
| **Vibrant Teal** | #0D9488 | Primary data series, healthy nodes, structural bonds, baseline metrics. |
| **Energetic Amber** | #D97706 | Secondary data series, warnings, dynamic connections, medium intensity. |
| **Vivid Indigo** | #4F46E5 | Comparison series, distinct molecular groups, specialized network nodes. |
| **Functional Emerald** | #059669 | Success metrics, active/positive data, stable system states. |
| **Deep Rose** | #E11D48 | Negative trends, high-priority anomalies, critical cluster highlights. |

### Visualization Guidelines
* **Matrices and Heatmaps:** Use a high-contrast gradient scale (e.g., from a soft, desaturated background color transitioning into a deep, saturated **Vivid Indigo** or **Vibrant Teal**) to make structural density and concentrations instantly visible.
* **Network & Molecule Graphs:** Nodes should use distinct colors from the palette above to represent different categories or states. Connection lines (edges) should be semi-transparent versions of the node colors to draw clean paths without turning into a solid mass of lines.
* **Sparsity & Contrast:** Keep chart background canvas transparent so they inherit the light or dark surface colors dynamically. Gridlines inside the charts should be faint (e.g., `#E7E5E4` in light mode, `#292A30` in dark mode) to ensure the colorful data elements remain the absolute focal point.

---

## 6. Verification Checklist
Before completing a task, verify the generated dashboard against this checklist:
1. Does the dashboard output dynamically to a standalone `dashboard.html` artifact with correct metadata?
2. Is the theme toggle a single, minimalist, textless icon button?
3. Have all redundant ornamental UI elements, decorative gridlines, and purple-lavender gradients been stripped?
4. Are the data visualizations (charts, graphs, matrices, 3D elements) colorful, lively, and highly readable, avoiding flat grayscales?
5. Is the dashboard displaying the actual, processed user data rather than static fallback placeholders?

