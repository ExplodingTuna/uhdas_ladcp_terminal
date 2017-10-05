#!/usr/bin/env python
"""
Publish the ADCP speedlog numbers on the web.

This relies on the messages published by DAS_speedlog via zmq.
"""

import sys
import time
import subprocess

import warnings
# warnings.simplefilter('error')

import numpy as np
from matplotlib.backends.backend_webagg_core import (
    FigureManagerWebAgg)  # just for the path to the jquery.js file
from tornado import websocket, web, ioloop
import json
import zmq
from zmq.eventloop import ioloop as zmq_ioloop
from zmq.eventloop.zmqstream import ZMQStream

from pycurrents.system import Bunch

html_template = """
<!DOCTYPE html>
<html>
<head>
  <title>tornado WebSocket example</title>
  <script src="_static/jquery/js/jquery-1.7.1.min.js"></script>

  <style>
  body {
    background: #000000; /* #802020; */
    color: #C05050;
  }
  table {
    table-layout: fixed;
    font-family: sans-serif;
    font-weight: bold;
    font-size: 34pt;
    color: #FF3030;
    }
    th {
        text-align: center;
        padding: 0.1em;
        /* background: #EEEEEE;
        color: #888888;
        */
        color: #C02020;
        background: #303030;
        padding-left: 0.3em;
        padding-right: 0.3em;
        padding-bottom: 0.15em;
        padding-top: 0.15em;
    }
    td {
        font-family: monospace;
        text-align: right;
        padding: 0.3em;
        background: #080840;
        border-color: #8080F0;

    }
  </style>
</head>
<body>
  <div class="container">
    <h1>ADCP Speedlog</h1>
    <hr>
         WebSocket status : <span id="message"></span>
       <hr>
      <div class="row">
        <div class="span4">
          <table>
            <tr>
              <th>Avg</th><th>Forward</th><th>Starb'rd</th>
            </tr>
            <tr id="row1">
              <th> now </th><td id="f0"> NA </td>
                          <td id="s0"> NA </td>
            </tr>
            <tr id="row2">
              <th>1 min</th><td id="f1"> NA </td>
                            <td id="s1"> NA </td>
            </tr>
            <tr id="row3">
              <th>5 min</th><td  id="f2"> NA </td>
                            <td id="s2"> NA </td>
            </tr>
          </table>
        </div>
      </div>

    <hr>
  </div>
  <script>
  var retry = null;

  function load_and_run() {
      try {
          var ws = new WebSocket('%(ws_url)s');
      }
      catch(err){
          if (retry == null){
              retry = setTimeout(load_and_run, 2000);
              return;
          }
      }
      if (retry != null){
          clearTimeout();
          retry = null;
      }
    var $message = $('#message');

    ws.onopen = function(){
      $message.attr("class", 'label label-success');
      $message.text('open');
      if (retry != null){
          clearTimeout(retry);
          retry = null;
      }
    };
    ws.onmessage = function(ev){
      $message.attr("class", 'label label-info');
      $message.text('received message');

      var datadict = JSON.parse(ev.data);
      for (var key in datadict){
          $('#' + key).text(datadict[key]);
      };

    };
    ws.onclose = function(ev){
      $message.attr("class", 'label label-important');
      $message.text('closed');
      idlist = ['s0', 's1', 's2', 'f0', 'f1', 'f2'];
      for (var i=0; i<idlist.length; i++){
      $('#' + idlist[i]).text('NA');
      }
      if (retry == null){
          retry = setTimeout(load_and_run, 2000);
      }
    };
    ws.onerror = function(ev){
      $message.attr("class", 'label label-warning');
      $message.text('error occurred');
    };
};
load_and_run();
  </script>
</body>
</html>
"""

class SpeedDisplay(web.Application):

    class IndexHandler(web.RequestHandler):
        ''' index http normal handler'''
        def get(self):
            html = html_template % self.application.html_subdict
            self.write(html)

    class SocketHandler(websocket.WebSocketHandler):
        ''' websocket handler '''

        def check_origin(self, origin):  # This is necessary!
            return True

        def open(self):
            ''' ran once an open ws connection is made'''
            cl = self.application.cl
            if self not in cl:
                cl.append(self)

        def on_close(self):
            ''' on close event, triggered once a connection is closed'''
            cl = self.application.cl
            if self in cl:
                cl.remove(self)

    def __init__(self, addr='localhost', port=38081):
        super(SpeedDisplay, self).__init__([
            (r'/_static/(.*)',
             web.StaticFileHandler,
             {'path': FigureManagerWebAgg.get_static_file_path()}),

            (r'/', self.IndexHandler),
            (r'/ws', self.SocketHandler),  # {"driver" : driver}),
        ])
        self.cl = []  # list of websockets, one per connection
        self.addr = addr
        self.port = int(port)
        ws_url = "ws://%s:%d/ws" % (self.addr, self.port)
        self.html_subdict = dict(ws_url=ws_url)

class Averager(object):
    def __init__(self, nbuf=1000, secs=(0, 60, 300)):
        self.nbuf = nbuf
        self.nbuf2 = 2 * nbuf
        self.icur = 0  # next location to fill
        self.secs = secs
        self.buf = np.ma.masked_all((self.nbuf2, 3), dtype=float)
                                    # time, forward, stbd
        self.t0 = time.time()

    def __call__(self, fs):
        now = time.time() - self.t0
        self.buf[self.icur, 1:] = fs
        self.buf[self.icur, 0] = now
        self.icur += 1
        speeds = np.ma.masked_all((2 * len(self.secs)), dtype=float)
        for i, sec in enumerate(self.secs):
            i2 = i * 2
            if sec == 0:
                speeds[i2:i2+2] = fs
            else:
                j = np.searchsorted(self.buf[:self.icur, 0], now - sec)
                if j == 0 or j == self.icur:
                    continue  # values remain masked
                interval = self.buf[j:self.icur, 1:]
                # Require at least 50% coverage; could be config param
                if interval[:, 0].count() < 0.5 * interval[:, 0].size:
                    continue  # values remain masked
                speeds[i2:i2+2] = interval.mean(axis=0)

        if self.icur == self.nbuf2:
            self.buf[:self.nbuf] = self.buf[self.nbuf:]
            self.buf[self.nbuf:] = np.ma.masked
            self.icur = self.nbuf

        return speeds

class SpeedAverage(object):
    def __init__(self, application, config):
        self.application = application
        self.config = config
        self.averager = Averager()
        self.idlist = ['f0', 's0', 'f1', 's1', 'f2', 's2']
        self.last_msg_time = 0

    def change_all(self, speeds):
        speeds = speeds.filled(np.nan)
        speedstrings = []
        for s in speeds:
            sstr = '%6.2f' % s if not np.isnan(s) else 'NA'
            speedstrings.append(sstr)

        values = zip(self.idlist, speedstrings)
        valdict = dict(values)
        cl = self.application.cl
        for sock in cl:
            sock.write_message(valdict)

    def __call__(self, msg):
        self.last_msg_time = time.time()
        parts = msg[0].decode('ascii').split(',')
        water = parts[1:3]
        bottom = parts[4:6]
        # Ignore the bottom-track for now.
        if water[0]:
            fs = np.ma.array([float(water[0]), float(water[1])], dtype=float)
        else:
            fs = np.ma.masked_all((2,), dtype=float)
        speeds = self.averager(fs)
        self.change_all(speeds)

    def check_timeout(self):
        if time.time() - self.last_msg_time < config.timeout:
            return
        speeds = self.averager(np.ma.masked_all((2,), dtype=float))
        self.change_all(speeds)



if __name__ == '__main__':

    # The following will be factored out soon...
    eth0 = subprocess.check_output("/sbin/ifconfig eth0", shell=True).decode('ascii')

    ip = None
    for line in eth0.split('\n'):
        line = line.strip()
        if line.startswith("inet addr:"):
            ip = line[10:].split()[0]
            break
    if ip is None:
        print("Failed to find host address.")
        sys.exit(-1)

    ####

    # We will also change the following to read from sensor_cfg.py.
    speedlog_addr = 'tcp://localhost:38020'

    config = Bunch(http_addr=ip,
                   http_port=38082,
                   speedlog_addr=speedlog_addr,
                   timeout=10,  # seconds; check for incoming VDVBW
                   )

    zmq_ioloop.install()
    io_loop = ioloop.IOLoop.instance()

    app = SpeedDisplay(config.http_addr, config.http_port)

    speed_average = SpeedAverage(app, config)

    context = zmq.Context()

    spd = context.socket(zmq.SUB)
    spd.connect(config.speedlog_addr)
    spd.setsockopt_string(zmq.SUBSCRIBE, u"$VDVBW")

    stream = ZMQStream(spd, io_loop=io_loop)
    stream.on_recv(speed_average)
    app.listen(app.port, app.addr)
    timecheck = ioloop.PeriodicCallback(speed_average.check_timeout,
                                        1000 * config.timeout)
    timecheck.start()

    io_loop.start()

