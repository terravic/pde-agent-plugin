# Cookie and Local Storage Notice

> **DRAFT -- REQUIRES LEGAL REVIEW**  
> This document is a template generated for technical review and does not constitute legal advice. Replace all bracketed placeholders (`[PLACEHOLDER]`) and obtain formal review by qualified legal counsel before publication or operational reliance.

**Operator:** `[ORGANIZATION_NAME]`  
**Contact Email:** `[PRIVACY_CONTACT_EMAIL]`  
**Effective Date:** `[EFFECTIVE_DATE]`

---

## 1. No HTTP Cookies or Third-Party Tracking

- `pkde-agent-plugin`, its local HTTP/SSE dashboard server (`127.0.0.1:8765`), standalone `dashboard.html`, and all 14 static HTML viewers set **zero HTTP cookies** (`Set-Cookie` is never sent).
- Zero third-party analytics, advertising scripts, tracking pixels, social widgets, external web fonts (`fonts.googleapis.com`), or third-party CDNs are loaded by `dashboard.html` or any static viewer.

## 2. Browser Local Storage Usage

The standalone dashboard (`dashboard.html`) uses one strictly functional `localStorage` entry solely to preserve the user's interface theme selection across page reloads:

| Storage Mechanism | Key Name | Purpose | Category | Expiration |
|---|---|---|---|---|
| `window.localStorage` | `pkde-theme-mode` | Stores selected theme preference (`light`, `dark`, or `system`). Never stores authentication tokens, session secrets, or personal data. | Strictly Necessary / UI Preference | Persistent until cleared by user in browser settings |

## 3. Managing Local Storage

Users may clear `pkde-theme-mode` at any time via browser developer tools or browser site-data settings without affecting any underlying scientific artifacts or CLI functionality.
