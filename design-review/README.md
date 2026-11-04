# MiSi visual review

The before and after images were captured from the local running application with its existing workspace data; keep them within the authorised local environment. Desktop images use 1440 × 900, tablet images 1024 × 768, and mobile images 390 × 844. The selected lead captures show a saved research item; the customer and opportunity-list images show the actual empty states in this workspace. No customer-detail image is included because no buyer account was recorded in the current workspace.

`after/search-interaction-desktop.png` captures the real command palette. The visual-review test can be rerun with `MISI_DESIGN_STAGE=after` using the frontend's reusable Playwright configuration. A separate opt-in browser test exercises populated customer and action screens against an isolated synthetic demo; it does not add data to the live workspace.
