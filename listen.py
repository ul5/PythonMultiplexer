#!/usr/bin/env python3

import screens
import socket
import threading
import time

running = True
threads = []


def follow_client(screen, client, addr, window):
    screen._append("Enjoy your reverse shell: \n")

    def callback(d):
        client.sendall(d.encode())
        screen.subtitle = f"{addr} << {d}"

    screen.callback = lambda d: callback(d)
    screen.onclose = lambda : client.close()
    screen.subtitle = f"{addr}"
    
    client.settimeout(10)
    window.notification = f"{addr} @ {screen.title}"
    window.print(0, f"Connected to Client {addr} on screen {screen.title}")

    while running:
        try:
            data = client.recv(1024)
            if data == b'':
                break
            screen._append(data.decode())
            window.render()
        except socket.timeout:
            pass
        except ConnectionResetError:
            break
        except OSError:
            break

    window.print(0, f"Disconnected from Client {addr}")
    client.close()
    window.close_screen(screen)

def accept_loop(w, s):
    w.print(0, "Started accept loop")
    s.settimeout(1)
    while running:
        try:
            client, addr = s.accept()
            screen = screens.Screen()
            w.add_screen(screen)

            t1 = threading.Thread(target = lambda: follow_client(screen, client, addr, w))
            t1.start()
            threads.append(t1)
        except socket.timeout:
            pass
    w.print(0, "Closing down...")

def set_title(window, screen):
    window.input("Input the address:")
    a = window.input_buffer
    a = a.split(":")
    addr = a[0]
    port = int(a[1]) if len(a) > 1 else 80
    print(a)
    t = (addr, port)
    screen._append(f"Connecting to {t}\n")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(t)
    except:
        screen._append("NOT CONNECTED!")

    t1 = threading.Thread(target = lambda: follow_client(screen, s, addr, window))
    t1.start()
    threads.append(t1)

    window.render()

if __name__ == "__main__":
    window = screens.Window()
    window.onadd = lambda s: set_title(window, s)
    window.add_screen(screens.Screen("Main"))

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('0.0.0.0', 1337))
    s.listen(10)

    t = threading.Thread(target = lambda: accept_loop(window, s))
    t.start()

    window.run()
    window.restore_mode()
    
    running = False
    t.join()
    for t in threads:
        t.join()
    s.close()