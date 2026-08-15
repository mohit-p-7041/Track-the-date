# The iPads and the scanner phone

**Do `docs/WINDOWS-SETUP.md` first**, all of it. Every device below gets bookmarked to the
laptop's address, so the address has to have stopped moving before you start. Doing it the other
way round means doing the device half twice.

About ten minutes per device, most of it waiting.

You need two things written down from the laptop's startup window:

```
On the iPads:     https://tecoma.local:8443     <- the name
By address:       https://192.168.1.240:8443    <- the number
```

**iPads use the name. The Android phone uses the number.** Android cannot look up `.local`
addresses; iOS can. The certificate is issued for both, so either is equally valid — this is the
only reason there are two.

---

## Part 1 — trust the certificate (every device, once)

Skip this only if the laptop is running on plain `http://...:8000`, in which case there is no
certificate to trust and no camera either.

The laptop's certificate was issued by a small authority that mkcert created **on that laptop**.
No device has heard of it, so every device refuses the connection until it is told to trust it.
Safari refuses outright, with a message that does not explain any of this.

### Get the file onto the device

The file is `rootCA.pem`, and `mkcert -CAROOT` prints the folder it lives in — on Windows,
`%LOCALAPPDATA%\mkcert`.

Email it to yourself and open it on each device if that is easy. If it isn't, hand it out from
the laptop itself. In a **second** terminal window, leaving the app running in the first:

```powershell
copy "$env:LOCALAPPDATA\mkcert\rootCA.pem" "$env:LOCALAPPDATA\mkcert\rootCA.crt"
python -m http.server 8000 --directory "$env:LOCALAPPDATA\mkcert"
```

- The first line makes a copy with a `.crt` extension. Android's certificate installer often
  won't see a `.pem` file in its picker; iOS accepts either. Making both costs nothing.
- The second serves that folder over plain HTTP on port 8000 — which is free, because the app is
  on 8443, and already open on the firewall from `setup.bat`. Plain HTTP is exactly right here:
  this is the one file a device is allowed to fetch before it trusts anything.

On each device, open `http://192.168.1.240:8000/` and tap the file you need. **Press Ctrl+C in
that terminal when every device is done** — there is no reason to leave a file server running.

---

## Part 2 — an iPad

### 2.1 Trust the certificate

1. Open `http://192.168.1.240:8000/rootCA.pem` in Safari. It says **Profile Downloaded** rather
   than opening anything.
2. **Settings → General → VPN & Device Management → Downloaded Profile → Install.** Enter the
   iPad's passcode. Install again on the warning screen.
3. **Settings → General → About → Certificate Trust Settings → turn mkcert ON.**

**Step 3 is separate from step 2 and is the one everybody misses.** Installing the profile puts
the certificate on the iPad; this switch is what makes it trusted. Without it you get exactly the
same failure as doing nothing.

### 2.2 Open the app and put it on the home screen

1. Safari → `https://tecoma.local:8443`. You should get the sign-in keypad with a normal padlock.
   If Safari says it cannot establish a secure connection, go back to 2.1 step 3.
2. Sign in with your name and PIN, so the icon opens straight into the app later.
3. **Share button (the box with the arrow) → Add to Home Screen → Add.**

The icon is the green coffee cup, labelled **Track the Date**. Tapping it opens the app full
screen with no Safari address bar — it behaves like an app, which is the point.

> The icon and its name come from the app itself. If you added it to the home screen before
> today's update and got a blurry screenshot instead, remove it and add it again.

### 2.3 Prove it works before you walk away

- Tap the green **+** in the bottom-right corner. The barcode field takes the cursor.
- Open any product from **Products**. **The Camera button is there.** That button hides itself
  wherever a camera cannot be opened, so it appearing *is* the proof the certificate is trusted.
- Take a photo with it. A button that appears and then fails is worse than one that never
  appeared.
- Scan something with the camera from the Scan screen.

The session lasts thirty days, so staff will not be re-entering PINs all weekend. Signing out is
on the name at the top right.

---

## Part 3 — the Android phone with the scanner

### 3.1 Read this first: RFID or barcode?

**This app matches products by their printed barcode — 6 to 18 digits, the number under the
stripes.** That rule is enforced in two places and is not negotiable.

If your device has a **UHF/RFID reader**, that side of it is no use here. An RFID tag returns a
hex EPC like `E20034120131`, which is not a barcode, matches no product, and would be refused as
soon as it hit a letter. Nothing in a servo carries an RFID tag anyway — the stock has printed
barcodes on it.

So: **use the device's barcode engine.** Handhelds that do both (Chainway, Zebra, Sunmi and the
rest) ship two separate apps, one per radio — you want the barcode/scan settings one, not the
RFID demo one. A Bluetooth ring or pistol scanner paired to an ordinary phone is the same story
and works exactly the same way.

If RFID tagging is something the shop actually wants later, that is a different job — tags on
every item, and a different kind of lookup. Park it; it is not this.

### 3.2 Put the scanner in keyboard mode

The app has no scanner integration and deliberately never will. It has **a text box**. Anything
that can type digits and press Enter works with it — the counter's USB gun, this phone, or
somebody's fingers.

In the device's scanner settings app, set:

| Setting | To | Called, variously |
|---|---|---|
| Output mode | Keyboard | "Keyboard emulation", "HID", "Keyboard wedge", "Text injection" |
| Suffix / terminator | Enter | "CR", "0x0D", "Enter key", "Line feed" |
| Prefix | none | "AIM identifier", "Code ID" |

Enter is what submits the form, so a scanner without it fills the box and stops. If you can't
find the prefix setting, leave it — the app strips a leading `]C1`-style identifier by itself.

**Test it in a notes app before going near the app.** Scan a bottle of milk: you want the digits
to appear *and the cursor to jump to a new line*. Digits but no new line means the suffix is
wrong. Nothing at all means it is still in intent or broadcast mode, not keyboard mode.

### 3.3 Trust the certificate

Android will not install a certificate unless the phone has a screen lock. Set a PIN or pattern
first if it hasn't got one.

1. Chrome → `http://192.168.1.240:8000/rootCA.crt` (the `.crt`, not the `.pem`). It lands in
   Downloads.
2. **Settings → Security & privacy → More security settings → Encryption & credentials → Install
   a certificate → CA certificate → Install anyway → pick `rootCA.crt`.**
   The path differs by manufacturer — search Settings for "certificate" if it isn't there.
3. Android will warn that a third party may monitor the network, and may keep a notification up
   about it. That is expected and is the same warning it gives for any private authority. It is
   describing the laptop in the back office.

**If the phone fights you over this**, it is not worth an hour: tap through Chrome's warning page
instead (**Advanced → Proceed**). The scanning path works fine that way. The only thing you lose
is the camera, and this phone has a real scanner — it doesn't need one.

### 3.4 Open the app and put it on the home screen

1. Chrome → `https://192.168.1.240:8443`. **The number, not `tecoma.local`** — Android cannot
   resolve `.local` names, and the page will simply not load if you use it.
2. Sign in.
3. **⋮ menu → Add to Home screen.**

### 3.5 Prove it works

1. Tap the home screen icon. Tap the green **+**.
2. **Tap the barcode box once** so the cursor is in it.
3. Scan something. The page should move straight to the expiry date step.
4. Enter a date, Save. It should say *Saved*, with the name and the date.
5. Scan the same thing again — it should say **Already tracked**, with the date it expires. That
   is the duplicate check, and seeing it is how you know the phone is going through exactly the
   same path as the counter.

If a scan does nothing at all, the cursor has come out of the box: tap it and scan again. If that
turns out to be constant rather than occasional, say so — it is a small fix in the app, not
something to live with.

---

## Part 4 — the USB gun at the counter

Nothing to set up. It is a keyboard as far as Windows is concerned: plug it in, open
`https://localhost:8443` on the laptop, go to Scan, and the cursor is already in the box. Scan,
type the date, Enter, scan the next one. No mouse anywhere in that path.

If it types letters or nothing, the gun is in the wrong mode — the same table as 3.2 applies, and
its manual will have a barcode you scan to set keyboard mode with an Enter suffix.

---

## When something is wrong

| What you see | What it is |
|---|---|
| Safari: "cannot establish a secure connection" | Certificate Trust Settings switch, part 2.1 step 3 |
| The page won't load at all on the iPad | Wrong address, or the laptop isn't running. Try the number instead of the name |
| The page won't load on the Android phone | You used `tecoma.local`. Use the number |
| Nothing loads on any device, laptop is fine | Firewall or network profile — `docs/WINDOWS-SETUP.md`, the table at the end |
| The Camera button isn't on the product screen | That device doesn't trust the certificate, or you're on an `http://` address |
| The scanner types digits but nothing happens | No Enter suffix — 3.2 |
| The scanner does nothing | Not in keyboard mode, or the cursor isn't in the box |
| It says "Already tracked" and you expected it to save | It is working. That barcode already has that date on it |
| Signed out unexpectedly | The account was taken off the sign-in list in Settings, or thirty days passed |

---

## What was verified, and what was not

**Verified:** the app serves over HTTPS with these certificates; the icon and the manifest that
make the home screen button are present, correctly sized and fetchable without signing in (the
state a device is in when it is first set up); the scan path treats a typed barcode, a gun's
barcode and a camera's barcode as the same thing, so a keyboard-mode scanner cannot take a
different route through the app than the counter does.

**Not verified, and not verifiable from here:** every step on the iPad and the phone. The profile
install, the trust toggle, Add to Home Screen, the CA install on Android, and any particular
scanner's settings app. The order and the reasoning are right; the exact menu names move between
iOS and Android versions and between manufacturers.

**Worth watching on the first session:** whether the barcode box keeps the cursor after a save on
Android. On the iPad and the laptop it does. If it doesn't there, it is a two-line fix in the app
rather than something staff should have to remember.
