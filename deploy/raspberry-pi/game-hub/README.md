# Private game hub

This folder prepares a legal RetroArch library hosted by the Raspberry Pi. RetroArch itself runs on the TV;
the Pi stores only controller profiles, playlists and games you own or that are explicitly open-source/homebrew.

## TV setup

1. Install the current Android build from [Libretro's official Android guide](https://docs.libretro.com/guides/install-android/).
   The Play Store build is old; keep Play Protect enabled and use **Install anyway** only for an APK downloaded
   directly from Libretro when Android presents that option.
2. Pair the Bluetooth controller to the **TV**, not the Pi, to avoid network latency:
   **Settings → Remotes & accessories → Add accessory**.
3. In RetroArch, leave **Settings → Input → Autoconfig** enabled. Test D-pad, both sticks, A/B/X/Y, shoulders,
   Start and Select before saving a per-controller remap.
4. Store only legal content under the Pi's `/mnt/storage/clean-tv/games/` tree. Never add commercial ROMs from
   games you do not own. Good zero-ROM starters are RetroArch's built-in 2048 and Cave Story/Doukutsu content,
   plus projects explicitly released as homebrew by their authors.

`retroarch.cfg` contains conservative TV defaults. Copy it only after the app is installed and its existing
configuration has been backed up. Device-specific remaps belong in `controller-profiles/`; do not guess mappings
without the real controller connected.

## Verified TCL setup

The Android TV 11 target was physically verified with Libretro's stable 32-bit `RetroArch_ra32.apk` version
1.22.2. The downloaded APK had SHA-256
`9e964f53089a302401a6d5b1451d7ce5539f39b85eb0a305d8d77e6edcbf803f`; Android's APK verifier reported the
Libretro release certificate SHA-256
`d7a5eab30902c9b2775af6fb4eac2d294a64634fb47dd1382bc3ac5bf669982e`. Check both values again whenever the
version changes rather than assuming a future file is identical.

The official updater installed and launched the public-domain 2048 contentless core successfully. ADB-injected
and network-remote D-pad events did not behave as a RetroArch game controller on this TV. Use a physical Bluetooth
controller paired directly to the TV; the phone remote's **Game Hub** shortcut launches RetroArch but is not a
replacement gamepad.

## Storage layout

```text
/mnt/storage/clean-tv/games/
├── homebrew/             # openly licensed games
├── owned-roms/           # private dumps from games you own
├── playlists/            # generated RetroArch playlists
└── controller-profiles/  # per-device remaps after physical testing
```

The folders are private and are not published by Caddy. Add a read-only authenticated Samba share only if the TV
file manager needs one; copying a small curated set to the TV is generally more reliable than playing over Wi-Fi.
