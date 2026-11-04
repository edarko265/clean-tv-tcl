# Raspberry Pi phone-remote host

The Pi can keep the private remote available when the Mac sleeps. The service in this folder runs as a dedicated
unprivileged user, can write only its private state folder, and is denied internet addresses at the systemd level.
The TV, Pi and phone must remain on the same trusted LAN.

## Install

Stage this folder together with `tools/phone_remote.py`, `tools/phone-remote/` and
`tools/requirements-phone-remote.txt` on the Pi, then run:

```bash
sudo ./install.sh <tv-ip>
```

Pair once in the foreground or securely copy the already-paired `client-cert.pem`, `client-key.pem` and
`browser-token` into `/var/lib/clean-tv-remote/`. They must be owned by `clean-tv-remote`, with the state folder
mode `0700` and private files mode `0600`. Then:

```bash
sudo systemctl start clean-tv-remote
sudo systemctl status clean-tv-remote
```

The phone URL uses the Pi's LAN address and the same private browser token. Never publish the port on the router.
VNC is not required by the service and should also stay LAN-only.

## Capacity and future hosting

The bridge itself is small. Media libraries, Sonarr downloads, backups and photo/video originals should live on
an externally powered USB 3 SSD rather than the Pi's microSD card. A good next stack is Jellyfin plus Sonarr on
the Pi, with the TV only acting as a client. Keep personal media, API keys and pairing certificates outside Git.
