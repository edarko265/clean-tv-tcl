# Security policy

Clean TV TCL uses ADB and can change enabled packages and the Home application on a television. Treat security and recoverability as product requirements.

## Supported versions

Security fixes are applied to the current `main` branch. The `dev` branch is pre-release and may change without notice. Historical commits and local forks are not supported.

## Report a vulnerability privately

Do not open a public issue, discussion, or pull request for a suspected vulnerability.

1. Open the repository's **Security** tab and choose **Report a vulnerability**: [private vulnerability reporting](https://github.com/edarko265/clean-tv-tcl/security/advisories/new).
2. If GitHub private reporting is unavailable, email [hello@araxda.com](mailto:hello@araxda.com) with `Clean TV TCL Security` in the subject.

Include the affected commit, component, impact, reproduction steps, and any suggested mitigation. Remove device identifiers, credentials, account information, IP addresses, Wi-Fi names, and ADB keys from the report.

You should receive an acknowledgement within five business days. A confirmed issue will be assessed, fixed on a private branch, and disclosed after users have had a reasonable opportunity to update. Credit is offered unless anonymity is requested.

## Security boundaries

Reports are especially useful when they involve:

- a tool executing against a device or path other than the explicit target;
- incomplete backup or restore behavior;
- unsafe package classification or bypass of the protected-package guard;
- launcher network access, data exposure, or unintended intent handling;
- dependency or build-chain compromise;
- secrets or private device data entering logs, commits, screenshots, or artifacts.

ADB is inherently privileged. Users must enable it deliberately, authorize only a trusted computer, work on a trusted network, and disable/revoke it after maintenance. Port 5555 is plaintext on many devices.

## Supply-chain policy

- Build the launcher from source; do not commit or redistribute prebuilt APKs.
- Pin CI actions to immutable commit SHAs.
- Review dependency changes separately from feature changes.
- Do not bundle third-party APKs.
- Verify the origin, signature, hash, and security notices of any optional sideload before installation.
- A project with a known signing-key or release-chain incident remains opt-in and blocked by default until verification is documented.

## Safe disclosure

Do not test against devices you do not own or have explicit permission to administer. Do not publish working exploits, device identifiers, or private household information before a coordinated fix is available.
