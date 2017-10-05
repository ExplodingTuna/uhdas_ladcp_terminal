from __future__ import print_function
from future import standard_library
standard_library.install_hooks()

from six.moves.tkinter import *
from PIL import Image, ImageTk
import Pmw
import os, stat, time

#
# an image viewer (from viewer.py in the Python Imaging Library)
#
# EF 2004/02/22 prevent crash on startup if file does not exist.
#  Note: still needs work.  load_file should cancel the run loop
#   if it is running, and then restart it.  At one time the event
#   cancelling mechanism had a memory leak, so it may be best
#   to simply set a flag so that run does not continue, then wait.
#   A mechanism is needed so that if a file goes away, the image
#   goes away also, or is replaced by a default (e.g. a message).

def modtime(file):
    return os.stat(file)[stat.ST_MTIME]

_fmt = "%Y/%m/%d %H:%M:%S"
def timestring(t):
    return time.strftime(_fmt, time.localtime(t))


class UI(Label):

    def __init__(self, master, file = None, **kw):
        Label.__init__(*(self, master), **kw)
        if file:
            self.showimage(file)

    def showimage(self, file):
        self.image = ImageTk.PhotoImage(Image.open(file))
        self.configure(image = self.image)



class ImageMonitor(Pmw.LabeledWidget):
    def __init__(self, master, file = None, interval = 5000, **kw):
        # To have a label, 'labelpos' must be specified at initialization.
        kw['labelpos'] = 'n'
        Pmw.LabeledWidget.__init__(self, master, **kw)
        self.win = UI(self.interior()) # No initial file display.
        self.win.pack()
        self.interval = interval
        self.modtime = 0
        self.configure()
        if file:
            self.load_file(file)

    def load_file(self, file):
        self.file = file
        self.run()

    def run(self):
        try:
            mt = modtime(self.file)
            if mt >= self.modtime:            # >= ensures existing file will
                self.modtime = mt              #    be displayed on startup
                self.win.showimage(self.file)
                s = "%s %s" % (self.file, timestring(mt))
                self.configure(label_text = s)
        except SystemExit:
            raise
        except:
            pass
        self.after(self.interval, self.run)


#
# script interface

if __name__ == "__main__":

    import sys

    if not sys.argv[1:]:
        print("Syntax: python plotview.py imagefile")
        sys.exit(1)

    filename = sys.argv[1]

    root = Tk()
    root.title(filename)
    picture = ImageMonitor(root, file = filename)
    picture.pack()

    root.mainloop()
