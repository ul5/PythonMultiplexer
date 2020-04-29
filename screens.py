#!/usr/bin/env python3

import sys
import array
import fcntl
import termios
import os
import tty

active_color = 41
other_color = 43

def write(s):
    stream = sys.stdout
    stream.write(s)
    stream.flush()

def escape_seq(s):
    write(f"\x1B[{s}")

def set_pos(x,  y):
    escape_seq(f"{y};{x}H")

def get_stdout_size():
    try:
        buf = array.array('h', [0, 0, 0, 0])
        fcntl.ioctl(0, termios.TIOCGWINSZ, buf, True)
        return buf[0], buf[1]
    except:
        return 0, 0

class Screen():
    def __init__(self, title = None, sub = None, callback = None):
        self.title = title
        self.subtitle = sub
        self.active = False
        self.content = ""
        self.buffer = []
        self.input = ""
        self.callback = callback
        self.onclose = None
        self.x = 0
        self.y = 0

    def _append(self, text, input=False):
        if input: # Only one char...
            if text[0] == '\x7F' and len(self.input) > 0:
                self.input = self.input[:-1]
                for i in range(len(self.buffer)):
                    index = len(self.buffer ) - 1 - i
                    if self.buffer[index][1]:
                        self.buffer = self.buffer[:index] + self.buffer[index+1:]
                        break
            elif text[0] != '\x7F':
                self.buffer += [(a, True) for a in text]
                self.input += text
        else:
            self.buffer += [(a, False) for a in text]

        if input and (len(text) > 0 and (text[0] == '\x0A' or text[0] == '\x0D' or text[0] == '\x09')):
            if self.callback:
                self.callback(self.input)
            self.input = ""

    def close(self):
        if self.onclose:
            self.onclose()

    def _render(self, height):
        a = "".join([a for a,x in self.buffer]).split("\n")[-height:]
        escape_seq("0m")
        for i, s in enumerate(a):
            set_pos(0, i + 1)
            write(f"{s}\n")
        self.x = len(s)
        self.y = i
    
    def _position(self):
        set_pos(self.x + 1, self.y + 1)

class Window():
    def __init__(self):
        self.screens = []
        self.ctrla = False
        self.height, self.width = get_stdout_size()
        self.set_raw_mode()
        self.notification = "Notification place"
        self.taking_input = False
        self.input_buffer = ""

    def set_raw_mode(self):
        newattr = termios.tcgetattr(0)
        newattr[tty.LFLAG] = newattr[tty.LFLAG] & ~(termios.ECHO | termios.ICANON | termios.IEXTEN |  termios.ISIG)
        termios.tcsetattr(0, termios.TCSANOW, newattr)
    
    def restore_mode(self):
        newattr = termios.tcgetattr(1)
        newattr[tty.LFLAG] = newattr[tty.LFLAG] | (termios.ECHO | termios.ICANON | termios.IEXTEN |  termios.ISIG)
        termios.tcsetattr(1, termios.TCSANOW, newattr)

    def input(self, prefix=""):
        self.input_prefix = prefix
        self.input_buffer = ""
        self.taking_input = True
        self.run()

    def _render_status(self):
        length = 0
        start = 0
        for i, s in enumerate(self.screens):
            if s.active:
                start = i - 5 if i > 5 else 0
                if s.subtitle:
                    write(f'\x1B[{active_color}m')
                    set_pos(0, self.height - 1)
                    write(f"{s.subtitle}")
        
        if self.notification:
            set_pos(self.width - len(self.notification) + 1, self.height - 1)
            write(f'\x1B[{active_color}m')
            write(self.notification)
        
        set_pos(0, self.height)

        for s in self.screens[start:]:
            title_length = len(s.title) + 3
            if length + title_length >= self.width:
                break

            if s.active:
                write(f'\x1B[{active_color}m')
            else:
                write(f'\x1B[{other_color}m')

            write(" ")
            write(s.title)
            write(" ")

            write(f'\x1B[{other_color}m')
            write("|")
            length += title_length
        write("." * (self.width - length))

    def render(self):
        set_pos(0, 0)
        escape_seq("0m")
        escape_seq('2J') # Clear screen
        escape_seq('?25l') # Hide cursor
        for s in self.screens:
            if s.active:
                s._render(self.height - 2)
                break
        escape_seq("40m")
        escape_seq("30m")
        self._render_status()
        escape_seq("1m")
        for s in self.screens:
            if s.active:
                s._position()
                break

        escape_seq("40m")
        escape_seq("31m")
        if self.taking_input:
            set_pos((self.width - len(self.input_prefix)) // 2, self.height // 2 - 1)
            write(self.input_prefix)
            set_pos((self.width - len(self.input_buffer)) // 2, self.height // 2)
            write(self.input_buffer)

        escape_seq('?25h') # Show cursor
        escape_seq('?1l')

        self.height, self.width = get_stdout_size()

    def print(self, index, text):
        self.screens[index % len(self.screens)]._append(f"{text}\n")
        self.render()

    def run(self):
        a = os.dup(0)
        f = os.fdopen(a, 'rb')
        self.render()
        self.render()

        while True:
            self.render()
            a = f.read(1)[0]

            if self.ctrla and not self.taking_input:
                self.ctrla = False

                if a == 98: # b
                    for i, s in enumerate(self.screens):
                        if s.active:
                            s.active = False
                            self.screens[(i - 1) % len(self.screens)].active = True
                            break
                elif a == 99: # c
                    for i, s in enumerate(self.screens):
                        if s.active:
                            s.active = False
                            self.screens[(i + 1) % len(self.screens)].active = True
                            break
                elif a == 100: # d
                    print("Dumping buffer...")
                    for i, s in enumerate(self.screens):
                        if s.active:
                            with open(f"screen_{i}.log", "w") as f1:
                                for e in self.screens[i].buffer:
                                    if not e[1]:
                                        f1.write(e[0])
                            break
                elif a == 101: # e
                    for i, s in enumerate(self.screens):
                        if s.active:
                            self.screens[i].buffer.clear()
                            self.screens[i].input = ""
                            break
                elif a == 110: # n
                    s = Screen()
                    self.add_screen(s)
                    if self.onadd:
                        self.onadd(s)

                continue            

            if a == 0x01: # Ctrl+A
                self.ctrla = True
                continue
            elif a == 0x03: # Ctrl+C
                return
            elif a == 0x04: # Ctrl+D
                for i, s in enumerate(self.screens[1:]):
                    if s.active:
                        self.close_screen(s)
                        s.close()
                        # self.screens[(i-1) % len(self.screens)].active = True
                        break
                continue

            ### append to current screen input
            if self.taking_input:
                if a == 0x0A or a == 0x0D:
                    self.taking_input = False
                    return
                elif a == 0x7F:
                    self.input_buffer = self.input_buffer[:-1]
                else:
                    self.input_buffer += chr(a)
                self.render()
            else:
                for s in self.screens:
                    if s.active:
                        s._append(chr(a), True)
                

    def add_screen(self, screen):
        screen.title = f"#{len(self.screens) + 1}" if not screen.title or screen.title.strip() == '' else screen.title
        self.screens.append(screen)
        self.render()
        for s in self.screens:
            if s.active:
                return
        self.screens[0].active = True

    def close_screen(self, screen):
        self.screens = [s for s in self.screens if s != screen]
        for s in self.screens:
            if s.active:
                self.render()
                return
        self.screens[0].active = True
        self.render()


if __name__ == "__main__":
    window = Window()

    window.add_screen(Screen())
    window.add_screen(Screen())

    try:
        window.run()
    except KeyboardInterrupt:
        escape_seq("0m") # No color
        escape_seq('2J') # Clear screen
        exit(0)