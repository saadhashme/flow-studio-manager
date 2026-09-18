# PostPilot v1

Windows desktop tool that holds your 4 social accounts (each in its own real
Chrome with its own proxy), receives finished videos from the agent via a
Telegram bot, and auto-uploads them to TikTok / YouTube / Instagram / Facebook.

**Important workflow:** the agent sends you every video on **WhatsApp for
approval first**. Only approved videos are forwarded to the Telegram inbox, so
the tool only ever posts content you already approved.

---

## 1. Requirements (Windows laptop)

- Windows 10/11 (64-bit)
- Python 3.11 or newer — https://www.python.org/downloads/ (tick **"Add python.exe to PATH"** during install)
- Google Chrome installed (the tool drives your real Chrome; it does not work with Chromium-only setups)

## 2. Build

1. Copy the `PostPilot` source folder to the laptop.
2. Double-click **`build.bat`**. It installs dependencies, syntax-checks, and builds.
3. Result: `dist\PostPilot\PostPilot.exe` (one-dir build — keep the whole `dist\PostPilot` folder together).
4. Run `PostPilot.exe`.

> Re-running `build.bat` after editing code rebuilds everything.

## 3. Create the Telegram inbox bot (one time)

1. On your phone, open Telegram and chat with **@BotFather**.
2. Send `/newbot`, follow the prompts (name + username). BotFather gives you a **bot token** like `123456:ABC-DEF...`.
3. Start a chat with your new bot (tap the link BotFather gives, press **Start**) — or add the bot to a private group. The agent will send videos to this chat.
4. Get the **chat id**: message `@userinfobot` on Telegram, or send a message to your bot then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and read `chat.id`.
5. In PostPilot → **Settings** tab: paste the bot token and chat id → **Save**. Then press **Start inbox**.
6. **Give the same bot token + chat id to the agent** (once). The agent's `agent_send.py` uses them to deliver videos.

## 4. Add proxies + log in (one time per account)

1. Open the **Accounts** tab. You will see 4 slots: Facebook (The Wealth Code Page), Instagram, YouTube, TikTok.
2. For each slot: check the platform dropdown and display name, then enter the proxy:
   - **Type**: http / https / socks5 (match what your proxy provider gave you)
   - **Host**, **Port**, **Username**, **Password** (leave user/pass empty if your proxy is IP-whitelisted)
3. Click **Save accounts**.
4. Click **"Open browser"** on a slot. A real Chrome window opens embedded in the tool, routed through that account's proxy.
5. **Log in manually** to the site in that embedded browser (Facebook/Instagram/YouTube/TikTok). The session is saved in that account's Chrome profile (`~/PostPilot/profiles/<id>/`) — you only log in once; closing and reopening keeps you logged in.
6. Repeat for the other 3 accounts. The ● indicator turns green while a browser is open.

> Facebook slot: log in with the account that owns/manages the **The Wealth Code** page. When uploading, the tool opens the Page composer.

## 5. How posting works

1. The agent sends an approved video to your Telegram bot. The tool's inbox (Settings → Start inbox) picks it up via long-polling and downloads it to `~/PostPilot/inbox/`.
2. Each message's caption carries a JSON manifest, e.g.
   `{"targets":["tiktok","youtube"],"title":"...","caption":"...","hashtags":["#a"]}`.
   If the caption isn't JSON, the whole caption becomes the post text and all 4 accounts are targeted.
3. The **Upload Queue** tab lists the video with per-account checkboxes and status:
   `pending → uploading → done` (or `failed` + error text).
4. Per account you can: **Post now**, **Schedule** (pick date/time), or **Skip**.
5. Uploads run through each account's own proxied Chrome via CDP. On failure a screenshot is saved to `logs/` for diagnosis.

## 6. Agent-side sending (for the agent, not the laptop)

On the agent's Linux machine:

```bash
pip install requests
python3 agent_send.py --video final.mp4 --bot-token <TOKEN> --chat-id <CHAT_ID> \
  --targets tiktok,youtube,instagram,facebook \
  --title "Video title" --caption "Post text here" --hashtags "#wealth,#money"
```

Videos are sent as **documents** (no recompression). Max **50MB** (Telegram Bot API limit).

---

## Troubleshooting

**Proxy authentication fails / pages don't load in embedded Chrome**
- Double-check type/host/port/user/pass in the Accounts tab (trailing spaces are a classic).
- Some providers need `https` type vs `http` — try both.
- IP-whitelisted proxies: leave username/password empty AND make sure your laptop's IP is whitelisted in the provider dashboard.
- The tool authenticates proxies via CDP Fetch (`browser/cdp.py::set_proxy_auth`). If a site shows a proxy login popup anyway, close the browser and reopen it.

**"Browser not open for \<platform\>" when posting**
- The queue needs that account's browser open (green ●). Click "Open browser" on the slot first, then Post now.

**Upload fails / stuck on a step**
- Sites change their page structure. Open `logs/` — the failure screenshot shows exactly where it stopped.
- Selectors live at the top of each `uploaders/<platform>.py` in the `SELECTORS` dict — fix them there, re-run `build.bat`.
- Make sure you're still logged in (open the browser, check). Sessions can expire; just log in again in the embedded browser.

**Telegram file > 50MB rejected**
- This is a Telegram Bot API hard limit. Compress the video (lower bitrate / 720p) or split it before sending. The tool reports oversize files in the log instead of downloading them.

**Inbox not receiving**
- Settings → check bot token & chat id → Save → Stop inbox → Start inbox.
- Make sure the bot has actually received a `/start` (for DMs) or is a member of the group.

**Chrome window doesn't embed / blank area**
- The tool needs a real installed `chrome.exe`. Reinstall Chrome from google.com/chrome if unsure.
- Try closing the browser and clicking "Open browser" again.

**Don't share screenshots of the Settings tab** — it contains your bot token.

---

## Project layout

```
PostPilot/
  main.py            entry point
  app/               PySide6 UI (tabs: accounts, queue, settings, log)
  browser/           Chrome launcher (WinAPI embed) + CDP client + proxy auth
  accounts/          config.json persistence (no hardcoded credentials)
  inbox/             Telegram long-poller + manifest parser
  uploaders/         one module per platform (tiktok/youtube/instagram/facebook)
  scheduler/         background post-now/schedule/skip engine
  logs/              failure screenshots (created at runtime)
  agent_send.py      agent-side sender (Linux)
  build.bat          PyInstaller build
  requirements.txt
```
