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
