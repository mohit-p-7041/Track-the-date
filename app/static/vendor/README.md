# Vendored assets

Third-party files, committed to the repository on purpose.

**No CDN links.** The shop laptop must work with the internet down — that is a locked decision in
`CLAUDE.md`, not a preference. Anything the browser needs is served from here.

Nothing in this folder is edited. The files are exactly what was downloaded, so their checksums
can be verified against the source at any time.

---

## zxing-0.21.3.min.js

Barcode decoding from the camera, for aisle scanning on an iPad. SPEC §8 names ZXing-js.

| | |
|---|---|
| Package | `@zxing/library` |
| Version | **0.21.3** |
| File | `umd/index.min.js` |
| Source | `https://unpkg.com/@zxing/library@0.21.3/umd/index.min.js` |
| Retrieved | 11 August 2026 |
| Size | 336,008 bytes |
| SHA-256 | `d7cc8f69dd70bdcf3ac00c9ae572bf2acb9f4132ba379c72df842e4db918652d` |
| Licence | Apache-2.0 — full text in `zxing-0.21.3.LICENSE` |

Verify it is unmodified with:

```bash
shasum -a 256 app/static/vendor/zxing-0.21.3.min.js
```

### Why 0.21.3 and not the latest

**0.22 and later ship ES modules only — there is no UMD bundle.** Consuming those without a
bundler means the browser fetching hundreds of individual files per page, and a bundler is
exactly what "no build step" rules out. 0.21.3 is the last release with a single vendorable file.

If this ever needs updating, check whether a UMD build has returned before bumping the number.
Upgrading to 0.22+ is not a version bump; it is a decision to add a build step, which is a
locked decision to revisit deliberately.

### How it is loaded

Not with a `<script>` tag. `app/static/js/scanner.js` injects it on the first tap of the camera
button, so the counter path — the gun, used hundreds of times a week — never downloads these
336 KB at all. The aisle path pays for it once and the browser caches it after that.
