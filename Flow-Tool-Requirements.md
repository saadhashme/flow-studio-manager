# Flow Multi-Account Tool — What I Want Built

This document describes **what the tool should do**, not how to build it.
Architecture, language, libraries and UI framework are entirely the builder's choice.

---

## 1. My situation

I create podcast-style videos using **Google Flow** (`https://labs.google/fx/tools/flow`).

- I have **20 Google accounts** (10 paid/Pro, 10 free) — so effectively 20 Flow accounts.
- Google gives **50 Flow credits per account per day**.
- A **10-second clip costs 15 credits**, so one account is good for about 3 clips.
- A **2-minute video therefore needs 4+ accounts**.

Right now I switch accounts by opening a **different Chrome profile every time**. That
constant switching is the whole problem I want solved.

---

## 2. What I want

**One single application where I can do all my Flow work without ever leaving it.**

Core requirements:

1. **Windows desktop application (.exe)** that I can install and run on my laptop.

2. **The browser must be built into the app.** Flow's own interface should open *inside*
   the tool's window — I don't want to be sent out to a separate browser window. The app
   is where I work.

3. **All my Google accounts attached inside the app.** Each account stays logged in, so I
   log in once per account and never again.

4. **Each account's remaining Flow credits shown in the app**, so I can see at a glance
   who has credits left today.

5. **Account switching from inside the same interface.** When one account's 50 credits
   are finished, I select the next account from a list and keep making videos **in the
   same window** — no new windows, no Chrome profile hunting.

Nice to have (not required):

- Automatic switching to the next account when credits run out, instead of me selecting.
- A notification when an account runs out.
- Renaming accounts and setting their order, so the rotation follows my preference.
- Marking accounts as paid or free, and keeping free ones out of the rotation by default.

---

## 3. How I work (context for design decisions)

- Everything runs on one laptop, on my home WiFi, on my own IP. **I do not want proxies.**
- I prefer **one account active at a time** — that matches how I already work with
  separate Chrome profiles, and I'd rather not have 10 sessions live at once.
- The tool should never generate videos by itself. I write the prompts and press the
  buttons in Flow; the tool only organizes accounts and shows me credits.
- I am not a programmer. Setup should be simple: install, add accounts, log in, use.

---

## 4. Known obstacle from earlier attempts (information, not instructions)

Solve this however you think best — I am only telling you what already happened so the
same wall isn't hit blindly:

- When Flow was loaded inside an **embedded browser view** (an Electron `BrowserView`),
  Google refused the login with: *"Couldn't sign you in — This browser or app may not be
  secure."* Spoofing the user-agent did not help (it reported as normal Chrome and was
  still blocked).
- Credits are **not visible on the page** by default. They appear inside the Google
  account popup menu as text like *"50 Google Flow credits / Credits refresh daily"*, and
  that text disappears from the page when the menu is closed.
- The page also shows other numbers followed by the word "credits" (for example the
  generation cost, "10 credits"), so naively reading the first number on the page gives
  the wrong value.

If your approach solves the embedded-browser sign-in problem, that is exactly what I
want. If it genuinely cannot be solved, tell me plainly and propose the closest
alternative rather than shipping something that can't log in.

---

## 5. How I'll judge whether it works

1. I can add all my accounts and log into each one **inside the app**.
2. After restarting the app, every account is **still logged in**.
3. I can see each account's **credit number**, and it updates as I use credits — without
   me clicking around to reveal it.
4. When one account runs out, I can move to the next account and **continue working in
   the same window**.
5. Making a 2-minute video (4 accounts' worth of clips) does not require me to open
   Chrome profiles even once.

---

## Appendix — my original request, in my own words

> "Me podcast videos bnata hon flow ai se, mere pas 20 google accounts hen means 20 flow
> ai, but google 50 credits deta hai hr account me daily. To me jb videos bnata hon 10-10
> seconds ke, to mujhe 2 min video bnane k lye 4 accounts change krne prte hen, q k 10
> seconds ke video 15 credits leti hai. To me ye chahta hon k tum mujhe aesa tool bna kr
> do jis me flow ai ka interface ho aur sare google accounts us me attach hon, and flow k
> credits bhe show ho re hon, and mujhe bar bar different apni chrome profiles pr ja kr
> account change krne na pren — just single interface me. Jb 50 credits khtam ho jae aik
> account k to me 2nd account ki selection kr lon, but videos same interface me he bnaon."
