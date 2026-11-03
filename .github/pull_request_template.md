<!-- Pull requests normally target dev. A dev-to-main release requires explicit owner approval. -->

## Summary

<!-- What changed and why? Keep one coherent topic per pull request. -->

## Risk and rollback

<!-- What could fail on a TV, and exactly how is the change undone? -->

## Verification

**Tested on:** <!-- model, Android version -->

**Checks run:** <!-- commands and results -->

- [ ] This pull request targets `dev`, or it is an owner-approved release pull request to `main`.
- [ ] No secrets, IP addresses, Wi-Fi names, serials, device IDs, ADB keys, or private screenshots are included.
- [ ] Install, update, and rollback behavior is documented where applicable.

### If this adds or changes a TV list
- [ ] `examples/<brand>-<model>/debloat.txt`, header with model, Android version and firmware build
- [ ] Only packages I actually disabled and lived with; anything I had to re-enable is noted
- [ ] `examples/<brand>-<model>/tv.json` with the TV, OS, brand and notes; nothing changed outside my folder (the README tables are generated from it)
- [ ] Nothing in the list uninstalls

### If this touches the launcher
- [ ] Verified on a real TV, screenshot attached
- [ ] D-pad checked from every edge (Up, Down, Left, Right)
- [ ] No network, no background service, no new permission
- [ ] New strings in `values/strings.xml` and the other `values-*` folders
- [ ] Anything TV-specific is in `config.xml` or a theme, not in code

### If this adds or changes a theme
- [ ] `themes/<name>/config.json` and `themes/<name>/screenshot.jpg`: Home on a real TV with the theme, 1280×720 JPEG under 300 KB
- [ ] A row in `themes/README.md` showing the screenshot
- [ ] Artwork is original or licensed, with `CREDITS.md` when it is not MIT-licensed

### If this adds a theme key (a switch)
- [ ] A screenshot of the key on a real TV and its row in `docs/switches.md`

### If this adds an add-on
- [ ] `addons/<name>/screenshot.jpg`: the add-on on a real TV, 16:9 JPEG under 300 KB, shown in its row in `addons/README.md`
