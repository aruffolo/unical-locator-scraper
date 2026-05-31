---
summary: "macOS signing, bundle ID, and TCC safety notes."
read_when:
  - Debugging macOS Screen Recording, Accessibility, automation, or TCC permission behavior.
  - Changing macOS app signing, entitlements, bundle identifiers, packaging, notarization, or release scripts.
  - Investigating a macOS app that behaves differently when launched from Xcode, terminal, Finder, or a signed bundle.
---
# macOS Signing And TCC

Use this only for macOS app permission, signing, packaging, and release work.

## TCC

- TCC permissions attach to the responsible process and app identity.
- For screenshot or UI automation, prefer `$peekaboo`; it owns Screen Recording, Accessibility, and permission-check workflow.
- If permissions are missing, report the exact missing grant instead of changing signing or bundle identity as a shortcut.

## Signing Safety

- Do not re-sign, ad-hoc sign, or change bundle ID as a debug workaround without explicit user approval.
- Treat bundle ID, entitlements, team ID, hardened runtime, notarization, and Sparkle/appcast identity as one connected release surface.
- Prefer reading project release scripts and local docs before changing signing behavior.
- For release artifacts, verify with the project’s established checks first; common tools include `codesign --verify`, `spctl`, and `stapler`.
