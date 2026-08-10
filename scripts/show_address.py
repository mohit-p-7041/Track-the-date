"""Print the address staff should type into an iPad.

Finds the laptop's address on the shop WiFi. Called by start.bat so nobody has
to run ipconfig and read through adapter output.
"""

from __future__ import annotations

import socket

PORT = 8000


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


if __name__ == "__main__":
    ip = lan_ip()
    print()
    print("   On this laptop:   http://localhost:%d" % PORT)
    if ip:
        print("   On an iPad:       http://%s:%d" % (ip, PORT))
        print()
        print("   Bookmark that on each iPad and add it to the home screen.")
        print("   If it stops working, the address may have changed — reserve")
        print("   it on the router to stop that happening.")
    else:
        print()
        print("   Could not find a network address. The laptop may be offline,")
        print("   or on a network that blocks this. iPads will not be able to")
        print("   connect until it is on the shop WiFi.")
    print()
