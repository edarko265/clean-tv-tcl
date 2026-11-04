# Phone remote and backlight bridge

[Back to the README](../README.md)

This fork includes a private web remote that runs on your Mac. Your phone opens the controls in Safari,
Chrome or Firefox; the Mac then talks to the TV through Android TV Remote Protocol v2, the encrypted pairing
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
small remote app. Stop the bridge with Ctrl-C; its browser port closes immediately. The pairing certificate can
be reused later. Delete `work/phone-remote/` to forget the pairing and browser link.

The remote provides D-pad, OK, Back, Home, power, volume, playback, text entry and shortcuts to the six dock
apps. App shortcuts use public deep links because launching package IDs through Remote Service is unreliable on
some current Play Store builds.

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
  are pinned too. PyPI publishes provenance tying androidtvremote2 to the maintainer's GitHub Actions workflow;
  its upstream licence is Apache-2.0.

On TCL sets the Remote Service can become unavailable in standby. If the TV offers **Settings → System → Power
and energy → Screenless service**, enabling it may keep network remote wake available; leaving it off saves the
most standby power.

## Backlight control

A strip that uses USB only for power cannot receive colours or animation commands. The TV cannot make that kind
of strip follow the picture in software. Do not power a long or bright addressable strip directly from the TV's
USB port: use the strip manufacturer's correctly rated supply and fuse.

The bridge supports a local [WLED](https://kno.wled.ge/) controller when the strip has a controllable data input:

```bash
TV_HOST=192.168.1.50 tools/phone-remote.sh --wled http://wled.local
```

The phone then gets colour, brightness and power controls. **Follow the active TV app** changes the backlight to
an app colour (Araxda violet on Home, red for Netflix/YouTube, cyan for Disney+, purple for Max, blue for Prime
Video and green for Spotify). This is app-aware ambient lighting, not per-frame image sampling.

True frame-by-frame sync needs an addressable controller plus one of these sources:

- an HDMI 2.0/2.1 capture-and-split path feeding HyperHDR/Hyperion, sized for the required resolution, HDR and
  refresh rate; or
- a camera/light sensor aimed at the screen, with lower fidelity but no HDMI/DRM compatibility problem.

Android screen capture is not a dependable source because Netflix and other DRM apps deliberately return a
black protected video layer. Before buying anything, identify the strip's connector/controller and its voltage;
USB power alone does not reveal whether it is 5 V addressable, analog RGB, or a fixed-colour strip.

## Troubleshooting

- No pairing code: confirm the TV's Android TV Remote Service is enabled and the phone/Mac are on the same LAN.
- The bridge cannot connect after a firmware update: delete `work/phone-remote/client-*.pem` and pair again.
- Phone cannot open the printed address: allow incoming connections if macOS Firewall asks, and disable client
  isolation/guest Wi-Fi for these three devices. Never solve this by forwarding the port to the internet.
- Netflix ignores navigation: that is a known Remote Service limitation on some builds; the physical remote
  remains available.
