# Spherecast UI/UX Guidelines

**Version:** 1.0.0  
**Product:** Spherecast – The AI Supply Chain Manager for Omni-Channel CPG Brands  
**Core Philosophy:** "From Chaos to Clarity." Our UI must transform complex supply chain data (POs, TOs, inventory, raw materials) into actionable, execution-ready insights. The interface should prioritize *exception management* over manual data entry.

---

## 1. Design Principles
1. **Trust & Transparency:** AI recommendations (e.g., forecasting, PO allocations) must always show the "why" with easily accessible underlying data.
2. **Efficiency First:** "Focus on exceptions, not spreadsheets." The layout must surface flagged issues immediately and enable one-click approvals.
3. **Conversational yet Structured:** Seamlessly blend standard SaaS data views (tables, charts) with natural language AI interactions (the "AI Colleague").
4. **Data Density with Clarity:** Supply chain managers need to see a lot of data (SKUs, locations, co-mans). Use intelligent whitespace, collapsible rows, and drill-downs to prevent cognitive overload.

---

## 2. Color System

Our color palette reflects trust, modern AI capabilities, and actionable data alerts.

### Primary Colors
* **Spherecast Navy (`#0F172A`):** Used for primary text, sidebars, and structural elements. Conveys enterprise reliability.
* **Electric Cobalt (`#2563EB`):** Primary action color (Primary buttons, active states, links). 
* **AI Indigo (`#6366F1`):** Used exclusively for AI-generated insights, baseline forecasts, and the "AI Colleague" chat features.

### Semantic Colors (Crucial for Supply Chain)
* **Success/In-Stock (`#10B981`):** Optimal inventory levels, confirmed POs, positive supply updates.
* **Warning/Risk (`#F59E0B`):** Projected stockouts, co-man delays, or shelf-life risks. Requires user attention.
* **Danger/Critical (`#EF4444`):** Immediate supply exceptions, missed dates, or active stockouts.

### Neutrals (Backgrounds & Borders)
* **Background (`#F8FAFC`):** Main app background. Soft and easy on the eyes for long sessions.
* **Surface (`#FFFFFF`):** Cards, modals, and table backgrounds.
* **Borders (`#E2E8F0`):** Subtle dividers between data rows and dashboard widgets.

---

## 3. Typography

We use a clean, highly legible sans-serif typeface optimized for data-heavy interfaces.

* **Primary Font:** `Inter` (Fallback: system-ui, -apple-system, sans-serif)
* **Monospace Font:** `JetBrains Mono` or `Fira Code` (Used for SKUs, order IDs, and raw data outputs).

### Hierarchy
* **Display / Header 1:** 24px, Semi-Bold, Spherecast Navy (e.g., "Dashboard", "Inventory Needs")
* **Header 2:** 18px, Medium (e.g., Widget Titles, "Supplier Updates")
* **Body (Default):** 14px, Regular, Slate 700 (`#334155`) (Standard table data, chat responses)
* **Metadata / Labels:** 12px, Medium, Slate 500 (`#64748B`) (Column headers, timestamps)

---

## 4. Layout System

Spherecast utilizes a **Full-Width App Layout** to maximize horizontal space for data tables and supply-chain mapping.

* **Global Sidebar (Left):** 240px fixed width. Contains navigation (Dashboard, Forecasts, POs/TOs, AI Chat, Settings). Collapsible to 64px for deep-work mode.
* **Top Bar:** Contains Global Search (Search by SKU, Co-man, or plain English query), User Profile, and urgent Notification center (Supplier exceptions).
* **Main Content Area:** Max-width restricted only on large displays (e.g., 1600px) to maintain readable line lengths, but fluid for tables.
* **Grid System:** 12-column fluid grid with 24px gutters.

---

## 5. Core UI Components

### Buttons
* **Primary:** Cobalt Blue background, White text. Used for main actions ("Book Demo", "Approve Plan", "Generate Forecast").
* **Secondary:** White background, Cobalt border. Used for secondary actions ("Edit Parameters", "View Details").
* **AI Action:** Indigo background with a subtle sparkle/AI icon. Used for triggering AI-specific workflows ("Simulate What-If", "Ask AI Colleague").

### Data Tables (The Core of Spherecast)
* **Sticky Headers:** Essential for scrolling through hundreds of SKUs.
* **Drill-Down Rows:** Users must be able to click an expand icon (`>`) on a product family to reveal location-specific or SKU-specific data.
* **Inline Editing:** Human overrides on AI baseline forecasts should happen directly in the table cell, highlighting the cell with an Indigo border to show it diverges from the AI baseline.

### Exception Cards
Used when the AI reads supplier updates and flags an issue.
* **Layout:** Alert icon + Context (e.g., "Co-man delayed by 3 days") + Impact (e.g., "Causes stockout in Node B") + **Action Buttons** ("Approve Alternative PO", "Ignore").

---

## 6. AI-Specific Patterns

Spherecast's differentiator is turning manual execution into autonomous AI execution.

### The "AI Colleague" Chat
* **Placement:** Can be opened as a sliding drawer from the right side (400px width) so the user does not lose context of the data table they are currently viewing.
* **Interaction:** Plain English inputs (e.g., *"What happens if demand drops by 15%?"*).
* **Outputs:** Responses must include rich-text and inline charts/tables, not just plain text.

### One-Click Approvals
* Whenever Agnes (the AI engine) recommends a fix for a supply exception, the UI must present it as a **Diff View**:
    * *Current State:* [Red/Warning styling]
    * *Proposed State:* [Green/Success styling]
    * *Action:* A single "Approve and Sync to ERP" button.

### What-If Simulators
* Slider controls or numeric inputs that instantly update a localized preview chart (e.g., "Inventory Levels vs. Time") without permanently overwriting the consensus baseline until saved.

---

## 7. Data Visualization

* **Forecasting Charts:** Line charts combining historical data (solid line) with AI Baseline Forecast (dashed Indigo line) and Consensus/Human Override (solid Cobalt line). Include shading for confidence intervals.
* **Supply Chain Mapping:** Use node-based graphs (Network diagrams) to visualize the flow from Raw Material Supplier → Co-Man → Warehouse → Channel.
* **Tooltips:** Hovering over any data point on a chart must reveal the exact numbers and the underlying factors contributing to that calculation.

---

## 8. Accessibility & Interaction (A11y)

* **Contrast:** All text and critical UI elements must meet WCAG 2.1 AA standards (minimum 4.5:1 contrast ratio).
* **Keyboard Navigation:** Power users (supply chain managers) rely heavily on keyboards. Full tab-index support, arrow-key navigation in tables, and shortcuts (e.g., `Cmd + K` for global search/AI prompt).
* **Loading States:** Use skeleton loaders instead of spinners for data tables to prevent layout shift and maintain the illusion of speed, even when crunching complex sandbox simulations.