# Flow Studio Manager

Desktop application for Google Flow AI creators with multi-account rotation, persistent logins, and real-time credit tracking.

---

## Key Features

1. **Integrated Browser Studio**:
   - Google Flow runs directly inside the tool's main window.
   - No jumping to external browser windows or hunting through separate Chrome profiles.

2. **20+ Persistent Accounts**:
   - Each Google account runs in an isolated persistent session partition (`persist:flow_account_<id>`).
   - Log in once; sessions remain active across application restarts indefinitely.

3. **Stealth & Anti-Detection Engine**:
   - Built to overcome Google's *"This browser or app may not be secure"* block.
   - Chromium automation flags (`AutomationControlled`) disabled.
   - `navigator.webdriver` redefined, Client Hints synchronized with genuine Google Chrome Windows headers.
   - Dedicated high-trust Google Sign-in modal available for 2FA/auth checkpoints.

4. **Live Credit Tracker & Auto-Switch**:
   - Real-time credit monitoring via Google Flow API response interceptor and flyout DOM scanner.
   - Accurately captures account credits (`50 / 50`) while ignoring generation cost buttons (e.g. "10 credits", "15 credits").
   - **Auto-Switch**: Automatically rotates to the next available account when credits fall below 15 (cost of a 10s video clip).
   - Keyboard Shortcut: `Alt + N` switches to the next ready account instantly.

5. **One-Click Chrome Profile Import**:
   - Automatically detects Google accounts from your local Google Chrome installation.
   - Import all 20+ profiles into the manager with a single click.

---

## Keyboard Shortcuts & Controls

| Shortcut / Button | Action |
|---|---|
| `Alt + N` | Switch immediately to the next ready account (≥ 15 credits) |
| `↻` (Reload) | Reload the current Google Flow session |
| `⌂` (Home) | Navigate back to Google Flow home (`https://flow.google.com/`) |
| `+ Add` | Add a new Google account manually |
| `📥 Import from Chrome` | Bulk-import existing Chrome browser profiles |

---

## How to Run

### Development Mode:
```bash
npm start
```

### Build Standalone Windows Executable (.exe):
```bash
npm run dist
```
The packaged standalone `.exe` installer and portable binary will be generated inside the `dist/` directory.
