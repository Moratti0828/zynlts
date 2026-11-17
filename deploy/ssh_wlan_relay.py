"""Windows per-connection campus-WLAN relay. Does not change global routes."""
import msvcrt
import os
import socket
import struct
import sys
import threading

host, port, local_ip, interface = sys.argv[1:5]
msvcrt.setmode(0, os.O_BINARY)
msvcrt.setmode(1, os.O_BINARY)
connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connection.settimeout(20)
connection.setsockopt(socket.IPPROTO_IP, 31, struct.pack("!I", int(interface)))
connection.bind((local_ip, 0))
connection.connect((host, int(port)))
connection.settimeout(None)


def upstream():
    try:
        while True:
            chunk = os.read(0, 65536)
            if not chunk:
                break
            connection.sendall(chunk)
    finally:
        try:
            connection.shutdown(socket.SHUT_WR)
        except OSError:
            pass


threading.Thread(target=upstream, daemon=True).start()
try:
    while True:
        chunk = connection.recv(65536)
        if not chunk:
            break
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
finally:
    connection.close()
