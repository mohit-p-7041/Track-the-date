# HTTPS, and the certificates onto the iPads

Iteration 2 item 2. Day 2, at the shop laptop. About ten minutes plus two per iPad.

This exists for one reason: **Safari will not open a camera over plain http from a network
address.** Everything else in the app already works over http. Aisle scanning (item 3) does not,
and cannot be made to without this.

**No application code changes.** `start.bat` already switches by itself. What follows was checked
rather than assumed — see "What was verified" at the bottom.

---

## 1. On the shop laptop

Install mkcert once (it needs Chocolatey, or grab the .exe from the mkcert releases page):

```
choco install mkcert
mkcert -install
```

`mkcert -install` puts a local certificate authority into the Windows trust store. That is what
makes the laptop itself trust what comes next.

Find the laptop's address, then make the certificate for it:

```
ipconfig
mkcert -key-file certs\key.pem -cert-file certs\cert.pem <laptop-ip>
```

Use the IPv4 address on the shop WiFi adapter — the `192.168.x.x` or `10.x.x.x` one, not
`127.0.0.1`.

`certs\` is gitignored, so the certificate never leaves the laptop. That is correct: it is
specific to this machine's address and is not something to copy around.

Close and reopen `start.bat`. It should now say `https://<ip>:8443` instead of
`http://<ip>:8000`. If it still says http, the two files are not both in `certs\` under exactly
those names.

## 2. The firewall, once

Windows will likely prompt on the first HTTPS start. Allow it on **Private** networks. If no
prompt appears and iPads cannot connect, check `docs/LAPTOP-NOTES.md` — the firewall rule for
8000 is already recorded there and 8443 needs the same treatment.

## 3. Reserve the address on the router

Do this before touching the iPads, not after.

The laptop gets its address by DHCP, so it can change between sessions — and every iPad bookmark
and every certificate is tied to that number. Reserve it against the laptop's MAC address in the
router admin page.

Skipping this means the bookmarks break on some random Saturday and the certificate has to be
reissued for the new address.

## 4. Each iPad

The certificate is only trusted once the mkcert root is installed on the device. Without it
Safari refuses the connection.

1. Get `rootCA.pem` off the laptop. `mkcert -CAROOT` prints the folder it lives in. Email it to
   yourself, or put it on a USB stick, or serve it — whatever gets it onto the iPad.
2. Open it on the iPad. It downloads as a profile rather than opening.
3. **Settings → General → VPN & Device Management → Downloaded Profile → Install.** Enter the
   iPad passcode.
4. **Settings → General → About → Certificate Trust Settings → toggle mkcert on.** This step is
   separate and easy to miss; installing the profile alone is not enough.
5. Open `https://<ip>:8443` in Safari. Sign in. Add it to the home screen.

## 5. Check it worked

Open a product on the iPad. **The Camera button appears.**

That button already exists and hides itself where a camera cannot be opened, so it appearing is
the proof — not the padlock, not the absence of a warning. If it is missing, the certificate is
not trusted and step 4's second half is the usual reason.

Then actually take a photo with it. A button that appears and fails on tap is a worse outcome
than one that never appeared.

---

## What was verified, and what was not

**Verified on the dev machine:**

- The app serves correctly over HTTPS with the exact uvicorn flags `start.bat` passes
  (`--ssl-certfile` / `--ssl-keyfile`). Negotiated TLS 1.3; sign-in, home, settings and static
  assets all returned normally over TLS, from the LAN address rather than localhost.
- `scripts/show_address.py` takes the `scheme` and `port` arguments `start.bat` hands it, and
  prints the https form correctly. A wrong signature here would throw at every startup.
- `start.bat`'s condition reads correctly: both files must exist, and it sets port 8443 and the
  https scheme together.
- The session cookie is `HttpOnly` but deliberately **not** `Secure`. That is right — the same
  cookie has to work over plain http, which is what the shop runs until this is done and what
  the laptop uses on localhost. Adding `Secure` would sign everyone out of the http mode.
- A browser meeting this certificate **without the root installed refuses the connection
  outright**. That is the exact failure mode step 4 prevents, and it is why the root install is
  not an optional tidiness step.

**Not verified, and not verifiable off the shop hardware:**

- mkcert on Windows, and whether `mkcert -install` needs an elevated prompt on that laptop.
- The iPad profile install and the Certificate Trust Settings toggle.
- That the Camera button appears on a real iPad, which is the actual acceptance criterion.
  Browsers only expose `navigator.mediaDevices` in a secure context and `app/static/js/photo.js`
  gates on exactly that, so the logic is not in doubt — but the certificate being trusted on the
  device is, and that is the part that has to be checked in person.
- Whether tapping through a certificate warning on iOS would be enough. **Do not rely on it.**
  Install the root.
