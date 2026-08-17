---
title: Report Desk Generator
emoji: 📄
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Turns a radon monitor's data file into a finished report
---

# Report Desk — report generator

The engine behind [Report Desk](https://report-desk-beige.vercel.app). It takes
the data file a radon monitor prints and a photo of the house, and returns a
finished seven-page PDF report.

Not a demo you click. It is an endpoint the app calls:

- `GET /health` — is it awake
- `POST /generate` — the monitor PDF, the house photo, and the firm's branding
  in, the finished report and every hourly reading out

Requests need a shared secret, so this is not an open service.

Source: https://github.com/wolfvswhale/report-desk
