#!/usr/bin/env python3
import socket
import time


def simple_netcat(host, port, content, sleep):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    s.sendall(content.encode())
    time.sleep(sleep)
    s.shutdown(socket.SHUT_WR)
    response_ascii = ''
    while True:
        data = s.recv(128)
        if not data:
            break
        response_ascii += data.decode('ascii')
        # print(repr(data))
    s.close()
    return response_ascii


response = simple_netcat("192.168.100.73", 3490, "#:Gstat#", 0.5)
print(response)
if response == '5#':
    print("yes")
else:
    print("no")
