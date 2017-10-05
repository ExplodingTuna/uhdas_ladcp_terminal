'''
2001/04/03 EF
Basic serial port data structures and routines.
'''
from __future__ import print_function
from future.builtins import range
from future.builtins import object



import termios, sys, os, tty, time, struct, select

from uhdas.serial import sp_lock

baud_table = {300       :  termios.B300,
              600       :  termios.B600,
              1200      :  termios.B1200,
              2400      :  termios.B2400,
              4800      :  termios.B4800,
              9600      :  termios.B9600,
              19200     :  termios.B19200,
              38400     :  termios.B38400,
              57600     :  termios.B57600,
              115200    :  termios.B115200}

[iflag, oflag, cflag, lflag, ispeed, ospeed, cc] = list(range(7))
flag_names = ['input', 'output', 'control', 'local', 'ispeed', 'ospeed', 'c_cc']

port_flags     = {'echo':              (lflag, termios.ECHO),
                  'canonical':         (lflag, termios.ICANON),
                  'send-CRLF':         (oflag, termios.OPOST),
                  'ignore-break':      (cflag, termios.IGNBRK),
                  'input-parity':      (iflag, termios.INPCK),
                  'mark-bad-par':      (iflag, termios.PARMRK),
                  'input-strip-CR':    (iflag, termios.IGNCR),
                  'input-7-bits':      (iflag, termios.ISTRIP),
                  'break-SIGINT':      (iflag, termios.BRKINT),
                  'xon-xoff-input':    (iflag, termios.IXON),
                  'xon-xoff-output':   (iflag, termios.IXOFF),
                  '-send-CRLF':        (oflag, termios.ONLCR),
                 # '-convert-tabs':     (oflag, termios.OXTABS),
                 # '-discard-C-D':      (oflag, termios.ONOEOT),
                  'connect-local':     (cflag, termios.CLOCAL),
                  'hangup-on-close':   (cflag, termios.HUPCL),
                  'enable-input':      (cflag, termios.CREAD),
                  '2-stop-bits':       (cflag, termios.CSTOPB),
                  'enable-parity-io':  (cflag, termios.PARENB),
                  'odd-parity':        (cflag, termios.PARODD),
                  '7-bits':            (cflag, termios.CS7),
                  '8-bits':            (cflag, termios.CS8),
                  #'CTS-output':        (cflag, termios.CCTS_OFLOW),
                  #'RTS-input':         (cflag, termios.CRTS_IFLOW),
                  'obey-INTR-etc':     (lflag, termios.ISIG),
                  }

class serial_port(object):
    def __init__(self, device = '/dev/ttyS0',
                       mode = 'r+b',
                       baud = 9600):
        self.__device = device
        print(device)
        self.__mode = mode
        self.__baud = baud
        self.stream = None
        self.fd = None
        self.is_open = 0
        self.old_tios = None

    def open_port(self, save=True):
        if self.is_open:
            return
        sp_lock.lock_port(self.__device)  # Raises exception if locked.
        self.stream = open(self.__device, self.__mode, 0) # unbuffered
        self.fd = self.stream.fileno()
        if save:
            self.old_tios = termios.tcgetattr(self.fd)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        tty.setraw(self.fd)
        self.is_open = 1    # This *must* be set before calling
        self.set_cc()       #    any function that calls open_port.
        self.set_baud(self.__baud)

    def close_port(self, restore=True):
        if not self.is_open:
            return
        if restore and self.old_tios is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_tios)
        self.stream.close()
        self.fd = None
        sp_lock.unlock_port(self.__device)
        self.is_open = 0

    def set_baud(self, baud):
        self.__baud = baud;
        self.open_port()
        tios = termios.tcgetattr(self.fd)
        if tios[ospeed] == baud_table[baud]:
            return
        tios[ospeed] = baud_table[baud] # Output speed
        tios[ispeed] = termios.B0    # Input speed (B0 => match output)
        termios.tcsetattr(self.fd, termios.TCSAFLUSH, tios)
        time.sleep(0.5) # some ports need this delay


    def get_baud(self):
        return self.__baud

    def set_device(self, device):
        if self.is_open:
            self.close_port()
        self.__device = device
        self.open_port()

    def get_device(self):
        return self.__device

    def read_flags(self):
        self.open_port()
        tios = termios.tcgetattr(self.fd)
        flags = []
        lines = []
        values = []
        yn = ['no', 'yes']
        keys = list(port_flags.keys())
        for key in keys:
            flag, mask = port_flags[key]
            flags.append(flag)
            value = ((tios[flag] & mask) != 0)
            values.append(value)
            lines.append('%20s : %s' % (key, yn[value]))
        # Later we can add mechanisms for putting them in a better order.
        return '\n'.join(lines), keys, values

    def set_flag(self, flagname, on_off):
        self.open_port()
        flag, mask = port_flags[flagname]
        tios = termios.tcgetattr(self.fd)
        if on_off:
            tios[flag] = tios[flag] | mask
        else:
            tios[flag] = tios[flag] & ~mask
        termios.tcsetattr(self.fd, termios.TCSANOW, tios)

    def set_cc(self, vmin = 0, vtime = 1):  # vtime is in 1/10ths of second
        self.open_port()
        tios = termios.tcgetattr(self.fd)
        tios[cc][termios.VMIN] = vmin
        tios[cc][termios.VTIME] = vtime
        termios.tcsetattr(self.fd, termios.TCSANOW, tios)

    def send_break(self, quarters = 0): # 0 is 0.25 to 0.5 s
        self.open_port()
        termios.tcsendbreak(self.fd, quarters)  # 2 should ensure at least 0.5 s

class writer(object):
    ''' Given a serial_port object, write various file types.
    '''
    def __init__(self, port, format = 'line', gap = 1):
        write_table = {'line':self.line_write,
                       'dosline':self.dosline_write,
                       'ens':self.ensemble_write,
                       'nbraw':self.nbraw_write,
                       'osraw':self.osraw_write}
        self.write = write_table[format]
        self.port = port  # serial_port instance
        self.gap = gap

    def line_write(self, sourcefile):
        while 1:
            line = sourcefile.readline()
            if line == '':
                break
            print(line)
            self.port.stream.write(line)
            self.port.stream.flush()
            time.sleep(self.gap)

    def dosline_write(self, sourcefile):
        while 1:
            line = sourcefile.readline()
            if line == '':
                break
            #print line,
            self.port.stream.write(line.rstrip() + '\r\n')
            self.port.stream.flush()
            time.sleep(self.gap)


    def ensemble_write(self, sourcefile):
        finished = None
        while not finished:
            for ichunk in range(8):
                chunk = sourcefile.read(128)
                if len(chunk) != 128:
                    finished = 1
                    break
                self.port.stream.write(chunk)
                self.port.stream.flush()
            time.sleep(self.gap)


    def osraw_write(self, sourcefile):
        while 1:
            chunk1 = sourcefile.read(4)
            if len(chunk1) != 4:
                break
            nbytes = struct.unpack('<xxH', chunk1)[0]
            chunk2 = sourcefile.read(nbytes - 2);
            block = chunk1 + chunk2
            #self.stream.write(block)
            #self.stream.flush()
            os.write(self.port.fd, block)
            print('%d  %d' % (nbytes, len(block)))
            time.sleep(self.gap)

    def nbraw_write(self, sourcefile):
        while 1:
            chunk1 = sourcefile.read(2)
            if len(chunk1) != 2:
                break
            nbytes = struct.unpack('>H', chunk1)[0]
            chunk2 = sourcefile.read(nbytes);
            block = chunk1 + chunk2
            #self.port.stream.write(block)
            #self.port.stream.flush()
            os.write(self.port.fd, block)
            print('%d  %d' % (nbytes, len(block)))
            time.sleep(self.gap)

    def sendfiles(self, filenames):
        if isinstance(filenames, str):
            filenames = (filenames,)
        for filename in filenames:
            with open(filename, 'rb') as fid:
                self.write(fid)



class terminal(serial_port):
    def __init__(self, device = '/dev/ttyS0',
                       baud = 9600):
        serial_port.__init__(self, device = device,
                                   baud = baud,
                                   mode = 'r+');

    def connect(self):
        self.open_port()
        while 1:
            rd, wr, er = select.select([sys.stdin, self.stream],
                                       [], [], 10)
            if sys.stdin in rd:
                kbdline = sys.stdin.readline()
                if kbdline.startswith('$Q'):
                    break
                if kbdline.startswith('$B'):
                    print("SEND BREAK\n")
                    self.send_break(0)
                    print("SENT\n")
                else:
                #print len(kbdline)
                    self.stream.write(kbdline)
            if self.stream in rd:
                serline = self.stream.readline()
                #print len(serline)
                print(serline, end=' ')
        self.close_port()
