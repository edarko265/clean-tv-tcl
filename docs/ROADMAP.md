# Roadmap

This roadmap records direction, not a promise of dates. Device safety, restore testing, licensing, and performance gates take precedence over feature count.

## Principles

1. The TV remains useful if every optional feature is removed.
2. The launcher stays offline, small, and free of analytics.
3. Live data runs in a separately permissioned add-on or companion service.
4. Device changes are reversible and tested in small batches.
5. Artwork is original, public domain, or correctly licensed and credited.
6. `main` changes only after owner approval.

## Phase 0 — Safe baseline

- [x] Import upstream CleanYourTV history on `dev`.
- [x] Add upstream remote and document synchronization policy.
- [x] Add project README, governance, security, support, contribution, ownership, and dependency-update standards.
- [ ] Protect `main` in GitHub settings and make `dev` the default integration branch.
- [x] Run the complete test suite and launcher build on the imported baseline.
- [ ] Probe the TCL Android TV 11 model and firmware without changing it.
- [ ] Create and verify a private local backup.
- [ ] Produce a TCL-specific package classification and restore plan.

## Phase 1 — TCL cleanup and launcher

- [ ] Confirm USB devices and whether networking uses a USB Ethernet adapter.
- [ ] Identify Home, TV input, remote, Bluetooth, keyboard, Play services, casting, voice, update, and streaming packages.
- [ ] Ask the owner which streaming, casting, voice, mirroring, and update features to keep.
- [ ] Disable only approved telemetry, ad, content-row, and unused packages in small batches.
- [ ] Verify HDMI, tuner/live TV, sound, networking, remote keys, CEC, and streaming after every batch.
- [ ] Build the launcher locally and verify SDK compatibility and APK installation.
- [ ] Make the launcher Home without removing the stock launcher safety path.
- [ ] Reboot, test restore, and close ADB.

## Phase 2 — Theme system and Araxda pack

- [ ] Ship `araxda-cyber`: violet chip/circuit engineering visual language based on Araxda's public palette.
- [ ] Capture the required real-TV screenshot and verify readability at viewing distance.
- [ ] Add an on-TV theme chooser that selects local, installed theme packs without network access.
- [ ] Add theme metadata: title, author, license, preview, maturity, and resource cost.
- [ ] Add accessibility checks for contrast, focus visibility, motion reduction, and color vision.

Planned offline families:

| Family | Direction | Asset rule |
|---|---|---|
| AI Lab | robotics, agent swarms, neural systems, realistic engineering simulation | original technical art; no scraped GitHub media |
| Terminal | monochrome CRT, amber terminal, green phosphor, retro workstation | code-drawn or original |
| Cinema | genre palettes for horror, blockbuster, noir, and sci-fi | no film posters, characters, logos, or copied trade dress |
| Football | pitch, floodlights, tactical board, match-day variants | club-neutral unless assets are licensed |
| Tactical | extraction operations, maps, radio grids, equipment cases | original; no Call of Duty names or assets |
| Africa / Ghana | textile geometry, landscapes, architecture, gold/green/red accents | respectful direction with creator credit |
| Malta | limestone, harbour, luzzu-inspired colour, fortifications | original or licensed photography |
| Liquid Glass | restrained translucent surfaces and spectral highlights | GPU/memory budget tested |
| Wasteland | weathered industrial landscape and survival UI | original, non-franchise art |
| Zombie Survival | abandoned infrastructure and emergency-operation graphics | original; no gore-first imagery |

## Phase 3 — Opt-in live experiences

Live modes never receive launcher privileges. Each one is a separate app or LAN companion service with its own permissions, data sources, cache, privacy notice, and uninstall path.

- [ ] GitHub AI explorer using the official API, a user-provided token when required, rate-limit handling, and a transparent ranking method.
- [ ] Robotics/project showcase with curated repository metadata and license-aware media.
- [ ] Movie discovery using a licensed metadata provider; do not scrape or present copyrighted artwork without permission.
- [ ] Football fixtures through a licensed or user-configured feed.
- [ ] Local dashboard card for home-server health and media availability.

“Trending” must state the source, time window, refresh time, cache age, and ranking method. Sponsored placement is not allowed.

## Phase 4 — Optional media clients

### SmartTube

- [ ] Track the maintainer's disclosed build-environment and signing-key incident.
- [ ] Require an official source/release, new signing fingerprint, cryptographic hash, and independent malware scan before any install option is enabled.
- [ ] Present permissions and account-access implications to the owner.
- [ ] Keep installation manual and opt-in; never bundle an APK.

### Sonarr

- [x] Document a Pi deployment with tailnet-only admin access, external storage, backups, and legal-use guidance.
- [x] Integrate only through Jellyfin/the phone companion; Sonarr runs on the Pi, never on the TV.
- [x] Keep GPL-3.0 Sonarr code and binaries outside this MIT repository.

## Phase 5 — Games and living-room experiences

Candidates will be evaluated after the launcher and restore workflow are stable:

- local game streaming from an owned PC;
- open-source emulators for legally dumped games;
- controller-friendly open-source Android games;
- party games controlled from phones;
- ambient dashboards, photo frames, weather, calendars, and home automation.

Every candidate must pass controller mapping, Bluetooth stability, thermal/memory, network latency, privacy, licensing, and easy-removal checks on the actual TCL hardware.

Completed on the Pi and TV: an owner-only legal-content tree, conservative RetroArch guidance, the verified stable
32-bit Android build, a phone-remote launch shortcut, and a successful public-domain 2048 launch. Real controller
mapping and gameplay remain gated only on pairing and physically testing a Bluetooth gamepad with the TV.

## Release gate

A feature moves from `dev` to `main` only when:

- automated tests and lint pass;
- security and license review is complete;
- documentation includes install, update, and rollback;
- device-facing behavior is tested on the real TCL television;
- screenshots contain no private information;
- the owner explicitly approves the merge.
