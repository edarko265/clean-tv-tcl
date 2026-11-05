# Phone remote

[Back to the README](../README.md)

This fork includes a private web remote that runs on your Mac or an always-on Raspberry Pi. Your phone opens the controls in Safari,
Chrome or Firefox; the host then talks to the TV through Android TV Remote Protocol v2, the encrypted pairing
protocol used by Android TV's own Remote Service. It needs no Google account, cloud relay, analytics, ADB,
USB debugging or app installed on the TV.

## Start it

Keep the Mac, phone and TV on the same trusted Wi-Fi network, then run from this repository:

```bash
TV_HOST=192.168.1.50 tools/phone-remote.sh
```

The first run asks the TV to display a pairing code. Type that code in the Mac terminal. The bridge stores its
client certificate, private key and a random browser token under ignored `work/phone-remote/`, with owner-only
permissions. It then prints an address resembling:

```text
http://192.168.1.50:8765/r/a-long-random-token/
```

Open that exact address on the phone. On iPhone, Safari's **Share → Add to Home Screen** makes it behave like a
small remote app with the bundled Clean TV icon. Stop the bridge with Ctrl-C; its browser port closes immediately.
The pairing certificate can be reused later. Delete `work/phone-remote/` to forget the pairing and browser link.

The remote provides a D-pad, swipe touchpad, OK, Back, Home, power, volume, playback, channel and TV controls,
a number pad, text entry and shortcuts to the six dock apps. A Pi host can also expose a private list of homelab
links such as Jellyfin, Home Assistant and a photo frame without putting LAN addresses in Git. App shortcuts use public deep links because
launching package IDs through Remote Service is unreliable on some current Play Store builds.

## Private voice dictation

When the Pi deployment is given a local Wyoming speech-to-text endpoint, the text card shows **Dictate locally**.
Tap once to begin and again to stop. The browser captures at most 30 seconds of mono PCM audio and sends it over
the private HTTPS connection to the Pi. The Pi's local Whisper-compatible service returns text to the edit box;
it does not save the audio or send it to a cloud AI provider. Dictation never sends text to the TV automatically:
review it, then choose **Send text** or **Send + Enter**.

Microphone access requires a secure browser context. For the Pi deployment, use tailnet-only HTTPS rather than
opening the bridge to the internet. The direct `http://` LAN address still works for ordinary remote buttons and
typing, but browsers intentionally withhold microphone access there.

## Type or paste on the TV

1. Open a search, username or other editable field on the TV so its cursor is active.
2. Type in the phone remote's **Type or paste on TV** box. You can also long-press the box and use the phone's
   normal **Paste** action. The dedicated Paste button uses the browser clipboard when that permission is
   available and otherwise focuses the box for long-press paste.
3. Choose **Send text**, or **Send + Enter** to submit the field immediately. Text can be up to 1,000 characters.

Space, Delete, Clear and Enter are available as individual remote keys. The always-on control connection leaves
Remote IME disabled so it does not suppress the TV's normal on-screen keyboard. An IME-capable connection opens
only for an explicit text send, writes the text in small chunks, and disconnects again. The phone retains the text
after queuing it so an app that ignores the first attempt does not make you type it again.

Android Remote IME can only write into an editable field that is already focused; it cannot draw text over a video
or arbitrary screen. Some protected password fields and DRM streaming apps deliberately reject remote text. Use
the physical remote's on-screen keyboard for those fields.

## Always-on Raspberry Pi host

The same bridge can run as a hardened systemd service on an always-on Raspberry Pi, so the Mac can sleep. The
installer and service are in [`deploy/raspberry-pi/`](../deploy/raspberry-pi/). Copy the existing pairing files
directly over SSH to avoid pairing again; never commit them. The service runs without root, is restricted to LAN
addresses and stores its private state outside the repository. Its optional HTTPS origin, Wyoming endpoint and
homelab link file are runtime configuration, not public repository data.

The remote generates `onboarding.svg` from its random bearer URL at startup. Open **Add this remote to another
private phone** to scan it. Treat that QR as a password: it contains the private browser token. A Tailscale Serve
route provides a publicly trusted certificate while remaining reachable only by devices in the tailnet.

## Security model

- Android TV pairing and commands use TLS on the TV's Remote Service ports (normally 6467 for pairing and 6466
  for control). Network ADB remains off.
- The web server accepts private/link-local clients only and uses a 256-bit random bearer path. It sends no
  CORS permission, refuses framing, applies a strict content policy and rate-limits commands.
- The server exists only while the command is running. Do not forward port 8765 on the router or share its
  complete random address.
- The page has no external JavaScript, fonts, pictures, analytics or account. The bridge makes no cloud request.
- The direct Python runtime dependency is pinned
  [`androidtvremote2==0.3.2`](https://github.com/tronikos/androidtvremote2), and its five transitive packages
  are pinned too. QR generation uses pinned `qrcode==8.2` and renders SVG without Pillow. PyPI publishes provenance
  tying androidtvremote2 to the maintainer's GitHub Actions workflow; its upstream licence is Apache-2.0.
- Wyoming has no authentication by design, so the service must stay bound to loopback. The hardened systemd unit
  permits only loopback/private destinations and never publishes the Wyoming port.

On TCL sets the Remote Service can become unavailable in standby. If the TV offers **Settings → System → Power
and energy → Screenless service**, enabling it may keep network remote wake available; leaving it off saves the
most standby power.

## Troubleshooting

- No pairing code: confirm the TV's Android TV Remote Service is enabled and the phone/Mac are on the same LAN.
- The bridge cannot connect after a firmware update: delete `work/phone-remote/client-*.pem` and pair again.
- Phone cannot open the printed address: allow incoming connections if macOS Firewall asks, and disable client
  isolation/guest Wi-Fi for these three devices. Never solve this by forwarding the port to the internet.
- Netflix ignores navigation: that is a known Remote Service limitation on some builds; the physical remote
  remains available.
- TV keyboard does not appear: update/restart the Pi bridge so its normal connection has Remote IME disabled, then
  leave the field and select it again with the physical remote. Phone typing temporarily takes the field only while
  a send is in progress.
- Text does not appear: first use the physical D-pad or phone touchpad to focus a text field on the TV. Keep the
  text in the phone box and retry once. Protected fields and some apps do not accept Android Remote IME input.
- Dictation button is hidden: the host was not started with `--wyoming-whisper`. If it appears but the browser
  refuses the microphone, open the tailnet HTTPS URL rather than the direct HTTP address.
