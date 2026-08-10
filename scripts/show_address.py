"""Print the address staff should type into an iPad.

Called by start.bat so nobody has to run ipconfig and read adapter output.

    python scripts/show_address.py                 # http on 8000
    python scripts/show_address.py https 8443      # once certificates exist
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


def main() -> None:
    scheme = sys.argv[1] if len(sys.argv) > 1 else "http"
    port = sys.argv[2] if len(sys.argv) > 2 else "8000"
    ip = lan_ip()

    print()
    print(f"   On this laptop:   {scheme}://localhost:{port}")

    if ip:
        print(f"   On an iPad:       {scheme}://{ip}:{port}")
    else:
        print()
        print("   No network address found. The laptop may be offline or on a")
        print("   network that blocks this. iPads cannot connect until it is")
        print("   on the shop WiFi.")

    print()
    if scheme == "http":
        print("   Running without certificates. Everything works except the")
        print("   iPad camera — Safari will not open a camera over http from a")
        print("   network address. Set up mkcert when you need aisle scanning.")
    else:
        print("   Bookmark that on each iPad and add it to the home screen.")
        print("   If it stops working the address may have changed — reserve")
        print("   it on the router to stop that happening.")
    print()


if __name__ == "__main__":
    main()
