"""Print the address staff should type into an iPad or the scanner phone.

    python scripts/show_address.py                 # whatever this laptop is set up for
    python scripts/show_address.py https 8443      # or ask for a specific one

`start.bat` no longer calls this - scripts/serve.py prints the same addresses
as it starts. It stays because "what do I type on this new iPad?" is a question
someone asks with the app already running, and nobody should have to read
`ipconfig` output to answer it.
"""

from __future__ import annotations

import socket
import sys


def lan_ip() -> str | None:
    """The address this machine has on the local network.

    Opens a UDP socket toward a public address and asks the OS which local
    interface it would use. Nothing is actually sent, and it works with no
    internet connection — we only need the routing decision.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None
    finally:
        s.close()


def local_name() -> str:
    """This machine's mDNS name — the address that survives its IP changing.

    Windows answers `<computername>.local` on the network by itself and iOS
    resolves it natively, so an iPad bookmarked by name keeps working through a
    DHCP reshuffle that would have broken one bookmarked by number. It is
    printed *alongside* the IP rather than instead of it because Android does
    not resolve `.local` — the scanner phone still needs the number. Both are
    on the certificate for that reason. See docs/WINDOWS-SETUP.md.
    """
    return socket.gethostname().split(".")[0].lower() + ".local"


def main() -> None:
    if len(sys.argv) > 1:
        scheme = sys.argv[1]
        port = sys.argv[2] if len(sys.argv) > 2 else "8000"
    else:
        # Imported here rather than at the top: serve.py imports this module,
        # and a module-level import back would be a cycle.
        from scripts.serve import choose

        scheme, port_number = choose()
        port = str(port_number)

    ip = lan_ip()

    print()
    print(f"   On this laptop:   {scheme}://localhost:{port}")

    if ip:
        print(f"   On the iPads:     {scheme}://{local_name()}:{port}")
        print(f"   By address:       {scheme}://{ip}:{port}")
        print()
        print("   The Android scanner phone cannot resolve the name. Give it")
        print("   the address.")
    else:
        print()
        print("   No network address found. The laptop may be offline or on a")
        print("   network that blocks this. iPads cannot connect until it is")
        print("   on the shop WiFi.")

    print()
    if scheme == "http":
        print("   Running without certificates. Everything works except the")
        print("   iPad camera — Safari will not open a camera over http from a")
        print("   network address. Run setup.bat with mkcert installed to fix.")
    else:
        print("   Bookmark that on each iPad and add it to the home screen.")
        print("   If it stops working the address may have changed — reserve")
        print("   it on the router to stop that happening.")
    print()


if __name__ == "__main__":
    import os
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    os.chdir(Path(__file__).resolve().parent.parent)
    main()
