# Raspberry Pi phone-remote host

The Pi can keep the private remote available when the Mac sleeps. The service in this folder runs as a dedicated
unprivileged user, can write only its private state folder, and is denied internet addresses at the systemd level.
The TV and Pi remain on the same trusted LAN. The phone can use the LAN address or a tailnet-only HTTPS route.

## Install

Stage this folder together with `tools/phone_remote.py`, `tools/phone-remote/` and
`tools/requirements-phone-remote.txt` on the Pi, then run:

```bash
sudo ./install.sh <tv-ip> [public-base-url] [wyoming-host:port]
```

Pair once in the foreground or securely copy the already-paired `client-cert.pem`, `client-key.pem` and
`browser-token` into `/var/lib/clean-tv-remote/`. They must be owned by `clean-tv-remote`, with the state folder
mode `0700` and private files mode `0600`. Then:

```bash
sudo systemctl start clean-tv-remote
sudo systemctl status clean-tv-remote
```

The optional public base URL is the HTTPS origin encoded in the onboarding QR; use a Tailscale Serve address, not
an internet-exposed reverse proxy. The optional Wyoming endpoint enables explicit local dictation. A private
`/var/lib/clean-tv-remote/service-links.json` list can add TV shortcuts without committing hostnames or addresses:

```json
[
  {"id":"jellyfin","label":"Jellyfin","url":"org.jellyfin.androidtv"},
  {"id":"jellyfin-install","label":"Install Jellyfin","url":"market://details?id=org.jellyfin.androidtv"}
]
```

Keep it owned by `clean-tv-remote`, mode `0600`. The phone URL uses the same private browser token. Never forward
port 8765 on the router. VNC is not required by the service and should also stay LAN-only.

For tailnet-only HTTPS, point Tailscale Serve at the loopback bridge, using any unused HTTPS port:

```bash
sudo tailscale serve --bg --https=8766 http://127.0.0.1:8765
```

## Capacity and future hosting

The bridge itself is small. Media libraries, Sonarr downloads, backups and photo/video originals should live on
an externally powered USB 3 SSD rather than the Pi's microSD card. Run Jellyfin and Sonarr on the Pi, with the TV
only acting as a client. Sonarr's admin UI should bind to loopback and be published only through authenticated
tailnet HTTPS; disable anonymous analytics and do not configure illegal indexers or downloads.

The [`game-hub/`](game-hub/) folder contains legal RetroArch/controller defaults. The public and ignored private
theme libraries can be synchronized with `tools/sync-pi-library.sh`; include `/mnt/storage/clean-tv` in encrypted
backups. Keep personal media, API keys, pairing certificates, controller identifiers and bearer QR codes outside Git.

## Jellyfin TV onboarding

Keep accounts on the Pi server; do not create an unrelated account inside the TV client. After adding the Pi's
Jellyfin server address, **No account** means only that this TV has not saved a login yet. Choose **Manual login →
Quick Connect** on the TV. In an already authenticated Jellyfin phone or web client, open **Settings → Quick
Connect**, enter the TV's six-character code and approve it. The TV client can request Quick Connect but cannot
authorize another device.

Prefer Quick Connect or the existing password-protected user over a passwordless living-room account. Media remains
on the Pi under the server's configured read-only movie and show mounts; the TV is only a playback client.
