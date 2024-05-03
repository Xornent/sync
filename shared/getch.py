
# ./shared/getch.py:
#   get char implementation.
# 
# license: gplv3. <https://www.gnu.org/licenses>
# contact: yang-z <xornent at outlook dot com>

class getch():
    
    def __init__(self):
        try:
            self.impl = self.getch_windows()
        except ImportError:
            self.impl = self.getch_unix()

    def get_value(self):
        return self.impl

    def getch_unix(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def getch_windows(self):
        import msvcrt
        return msvcrt.getch()