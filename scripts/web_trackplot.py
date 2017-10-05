#!/usr/bin/env python
"""
Quick first attempt at monitoring autopilot with a map.

"""
from __future__ import print_function, division, unicode_literals

import sys
import os
import io
import json
import argparse
import subprocess

try:
    import tornado
except ImportError:
    raise RuntimeError("This example requires tornado.")
import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.websocket

import zmq
from zmq.eventloop import ioloop as zmq_ioloop
from zmq.eventloop.zmqstream import ZMQStream

import numpy as np

from matplotlib.backends.backend_webagg_core import (
    FigureManagerWebAgg, new_figure_manager_given_figure,
    NavigationToolbar2WebAgg)
from matplotlib.figure import Figure

from pycurrents.plot.maptools import mapper

from pycurrents.system import Bunch


# the following knocks out everything but the file type selection widget.
# NavigationToolbar2WebAgg.toolitems = []
# It's probably not needed, given that we knock out the whole toolbar
# on the JS side.

# The following is the content of the web page.  You would normally
# generate this using some sort of template facility in your web
# framework, but here we just use Python string formatting.
html_content = """
<html>
  <head>
    <!-- TODO: There should be a way to include all of the required javascript
               and CSS so matplotlib can add to the set in the future if it
               needs to. -->
    <link rel="stylesheet" href="_static/css/page.css" type="text/css">
    <link rel="stylesheet" href="_static/css/boilerplate.css" type="text/css" />
    <link rel="stylesheet" href="_static/css/fbm.css" type="text/css" />
    <link rel="stylesheet" href="_static/jquery/css/themes/base/jquery-ui.min.css" >
    <script src="_static/jquery/js/jquery-1.7.1.min.js"></script>
    <script src="_static/jquery/js/jquery-ui.min.js"></script>
    <script src="mpl.js"></script>

    <script>

    // Knock out the toolbar:
    mpl.figure.prototype._init_toolbar = function() {}

    // And mouse events:  (but that also disables the resizing)
    // (Maybe just make it full-screen from the start.)
    mpl.figure.prototype.mouse_event = function(event, name) {}


      /* This is a callback that is called when the user saves
         (downloads) a file.  Its purpose is really to map from a
         figure and file format to a url in the application. */
      function ondownload(figure, format) {
        window.open('download.' + format, '_blank');
      };

      $(document).ready(
        function() {
          /* It is up to the application to provide a websocket that the figure
             will use to communicate to the server.  This websocket object can
             also be a "fake" websocket that underneath multiplexes messages
             from multiple figures, if necessary. */
          var websocket_type = mpl.get_websocket_type();
          var websocket = new websocket_type("%(ws_uri)sws");

          // mpl.figure creates a new figure on the webpage.
          var fig = new mpl.figure(
              // A unique numeric identifier for the figure
              %(fig_id)s,
              // A websocket object (or something that behaves like one)
              websocket,
              // A function called when a file type is selected for download
              ondownload,
              // The HTML element in which to place the figure
              $('div#figure'));
        }
      );
    </script>

    <title>matplotlib</title>
  </head>

  <body>
    <div id="figure">
    </div>
  </body>
</html>
"""


class MyApplication(tornado.web.Application):
    class MainPage(tornado.web.RequestHandler):
        """
        Serves the main HTML page.
        """

        def get(self):
            manager = self.application.manager
            ws_uri = "ws://{req.host}/".format(req=self.request)
            content = html_content % {
                "ws_uri": ws_uri, "fig_id": manager.num}
            self.write(content)

    class MplJs(tornado.web.RequestHandler):
        """
        Serves the generated matplotlib javascript file.  The content
        is dynamically generated based on which toolbar functions the
        user has defined.  Call `FigureManagerWebAgg` to get its
        content.
        """

        def get(self):
            self.set_header('Content-Type', 'application/javascript')
            js_content = FigureManagerWebAgg.get_javascript()

            self.write(js_content)


    class WebSocket(tornado.websocket.WebSocketHandler):
        """
        A websocket for interactive communication between the plot in
        the browser and the server.

        In addition to the methods required by tornado, it is required to
        have two callback methods:

            - ``send_json(json_content)`` is called by matplotlib when
              it needs to send json to the browser.  `json_content` is
              a JSON tree (Python dictionary), and it is the responsibility
              of this implementation to encode it as a string to send over
              the socket.

            - ``send_binary(blob)`` is called to send binary image data
              to the browser.
        """
        supports_binary = True

        def open(self):
            # Register the websocket with the FigureManager.
            manager = self.application.manager
            manager.add_web_socket(self)
            if hasattr(self, 'set_nodelay'):
                self.set_nodelay(True)

        def on_close(self):
            # When the socket is closed, deregister the websocket with
            # the FigureManager.
            manager = self.application.manager
            manager.remove_web_socket(self)

        def on_message(self, message):
            # The 'supports_binary' message is relevant to the
            # websocket itself.  The other messages get passed along
            # to matplotlib as-is.

            # Every message has a "type" and a "figure_id".
            message = json.loads(message)
            if message['type'] == 'supports_binary':
                self.supports_binary = message['value']
            else:
                manager = self.application.manager
                manager.handle_json(message)

        def send_json(self, content):
            self.write_message(json.dumps(content))

        def send_binary(self, blob):
            if self.supports_binary:
                self.write_message(blob, binary=True)
            else:
                data_uri = "data:image/png;base64,{0}".format(
                    blob.encode('base64').replace('\n', ''))
                self.write_message(data_uri)

    def __init__(self, figure, manager):
        self.figure = figure
        self.manager = manager

        super(MyApplication, self).__init__([
            # Static files for the CSS and JS
            (r'/_static/(.*)',
             tornado.web.StaticFileHandler,
             {'path': FigureManagerWebAgg.get_static_file_path()}),

            # The page that contains all of the pieces
            ('/', self.MainPage),

            ('/mpl.js', self.MplJs),

            # Sends images and events to the browser, and receives
            # events from the browser
            ('/ws', self.WebSocket),

        ])

class Plotter(object):
    def __init__(self, mapfile, config):
        self.figure = Figure()
        self.nbuf = config.nbuf
        self.buf = np.ma.zeros((self.nbuf, 2), dtype=float)
        self.buf[:] = np.ma.masked
        self.i = 0

        self.thresh = config.thresh
        self.boxsize = config.boxsize

        regions = Bunch().from_pyfile(mapfile).regions
        self.polys = []
        for region in regions:
            poly = region.poly
            poly.append(poly[0])
            self.polys.append(np.array(poly))

        domain = np.vstack(tuple(self.polys))
        domainmin = domain.min(axis=0)
        domainmax = domain.max(axis=0)

        self.xlim = np.array([domainmin[0], domainmax[0]])
        self.ylim = np.array([domainmin[1], domainmax[1]])

        self.init_axes()

    def init_axes(self):
        self.figure.clf()
        self.ax = self.figure.add_subplot(1,1,1)

        self.m = mapper(self.xlim, self.ylim,
                        round_to=0.1,
                        aspect=0.85,
                        ax=self.ax)
        self.m.grid()
        self.m.topo()
        for poly in self.polys:
            self.m.mplot(poly[:, 0], poly[:, 1], color='Fuchsia',
                         linewidth=1.5, alpha=0.7)
        self.line, = self.ax.plot([], [], 'r.')


    def offset(self, x, y):
        midx = self.xlim.mean()
        midy = self.ylim.mean()
        dist = np.hypot(x-midx, y-midy)
        return dist

    def recenter(self, x, y):
            self.xlim = self.boxsize * np.array([-0.5, 0.5]) + x
            self.ylim = self.boxsize * np.array([-0.5, 0.5]) + y

    def __call__(self, msg):
        print(msg)
        t, x, y = [float(x) for x in msg[0].split()]
        if self.i == self.nbuf:
            self.buf[:self.i-1] = self.buf[1:self.i]
            self.i -= 1
        self.buf[self.i] = (x, y)
        self.i += 1
        if (self.xlim is None or
                    self.offset(x, y) > self.thresh * self.boxsize / 2 or
                    np.diff(self.ylim) > 1.5 * self.boxsize):
            self.recenter(x, y)
            self.init_axes()

        self.line.set_data(self.m(*self.buf.T))
        self.figure.canvas.draw_idle()


if __name__ == "__main__":


    parser = argparse.ArgumentParser(
                description="Web trackplot for DAS_autopilot")

    parser.add_argument('--mapdir',
                        help='directory with python file containing regions')

    parser.add_argument('--mapfile',
                        help='name of python file containing regions')

    parser.add_argument('--autopilot_addr',
                        help='zmq address to which autopilot is publishing')

    parser.add_argument('--web_ip',
                        help='IP address for serving to web')

    parser.add_argument('--web_port', default=38080, type=int,
                        help='http port for serving on web')

    parser.add_argument('--boxsize', default=2, type=float,
                        help='approximate map size in degrees')

    parser.add_argument('--thresh', default=0.7, type=float,
                        help='fraction of map radius at which to recenter')

    parser.add_argument('--nbuf', default=1000, type=int,
                        help='number of points to keep in history')

    opts = parser.parse_args()

    if (opts.mapdir is None or opts.mapfile is None or
            opts.autopilot_addr is None):
        apconfig = Bunch().from_pyfile('/home/adcp/config/autopilot_cfg.py')
        if opts.mapfile is None:
            opts.mapfile = apconfig.map
        if opts.mapdir is None:
            opts.mapdir = '/home/adcp/config/pilot_maps'
        if opts.autopilot_addr is None:
            opts.autopilot_addr = apconfig.config.pub_addr

    if opts.web_ip is None:
        eth0 = subprocess.check_output("ifconfig eth0", shell=True).decode('ascii')
        ip = None
        for line in eth0.split('\n'):
            line = line.strip()
            if line.startswith("inet addr:"):
                ip = line[10:].split()[0]
                break
        if ip is None:
            print("Failed to find host address.")
            sys.exit(-1)
        opts.web_ip =  ip


    config = Bunch(opts.__dict__)

    mapfile=os.path.join(opts.mapdir, opts.mapfile)

    print("mapfile is", mapfile)

    print("opts:\n", opts)

    # These probably have to be placed before any of the tornado
    # or other zmq calls below.
    zmq_ioloop.install()
    io_loop = tornado.ioloop.IOLoop.instance()


    p = Plotter(mapfile, config)
    # p.init_axes() # needs initial position...
    manager = new_figure_manager_given_figure(id(p.figure),
                                              p.figure)
    application = MyApplication(p.figure, manager)

    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(opts.web_port, opts.web_ip)

    print("http://%s:%s/" % (opts.web_ip, opts.web_port))
    print("Press Ctrl+C to quit")


    context = zmq.Context()

    gpsnav = context.socket(zmq.SUB)
    gpsnav.connect(config.autopilot_addr)
    gpsnav.setsockopt_string(zmq.SUBSCRIBE, u"")


    stream = ZMQStream(gpsnav, io_loop=io_loop)
    stream.on_recv(p)

    io_loop.start()
