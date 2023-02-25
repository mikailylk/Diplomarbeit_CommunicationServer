# Origin: https://github.com/Onixaz/picamera-h264-web-streaming
# Modified by: Mikail Yoelek

# libraries
import io
import picamera
import serial
import socket
import json
import serial_asyncio
import asyncio
import struct 
import subprocess
import os
import threading
import sys
import signal

import telemetrydata
from telemetrydata import TelemetryData,TelemetryDataEncoder

from communicationdata import CommData

from os import curdir, sep
from string import Template

from threading import Thread
from queue import Queue

from time import sleep, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from wsgiref.simple_server import make_server
from broadcast import BroadcastThread
from output import StreamingOutput

from ws4py.websocket import WebSocket
from ws4py.server.wsgirefserver import (
    WSGIServer,
    WebSocketWSGIHandler,
    WebSocketWSGIRequestHandler,
)
from ws4py.server.wsgiutils import WebSocketWSGIApplication

from datetime import datetime

###########################################
# CONFIGURATION
#WIDTH = 640
#HEIGHT = 480
#FRAMERATE = 25  # after 40 fps --> fov is partial (see also: 
# https://picamera.readthedocs.io/en/release-1.13/fov.html)

WIDTH = 1280
HEIGHT = 720
FRAMERATE = 25  # delay is getting bigger, when resolution and framerate is higher!!

HTTP_PORT = 8082
SMARTPHONE_PORT = 8088

PICO_PORT = 8086       # information for smartphone; for Raspberry Pi not relevant
WS_PORT = 8084


VFLIP = False
HFLIP = False

###########################################

#region streaming httphandler
class StreamingHttpHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for serving streaming video to a web client.
    """
    
    def do_HEAD(self):
        """
        Respond to HTTP HEAD requests.
        """
        self.do_GET()


    def do_GET(self):
        """
        Respond to HTTP GET requests.
        """
        #Serve index.html
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
            return
        elif self.path == '/index.html':
            content_type = 'text/html; charset=utf-8'
            tpl = Template(self.server.index_template)
            content = tpl.safe_substitute(dict(
                ADDRESS='%s:%d' % (self.request.getsockname()[0], WS_PORT)
                ))
        #Serve js
        elif self.path.startswith('/js/'):
            f = open(curdir + sep + self.path)
            
            self.send_response(200)
            self.send_header('Content-type',    'application/javascript')
            self.end_headers()
            self.wfile.write(bytes(f.read(),encoding='utf-8'))
            f.close()
            return
        #Serve css
        elif self.path.startswith('/css/'):
            f = open(curdir + sep + self.path)
            self.send_response(200)
            self.send_header('Content-type',    'text/css')
            self.end_headers()
            self.wfile.write(bytes(f.read(),encoding='utf-8'))
            f.close()
            return
            
        else:
            self.send_error(404, 'File not found')
            return
        content = content.encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(content))
        self.send_header('Last-Modified', self.date_time_string(time()))
        self.end_headers()
        if self.command == 'GET':
            self.wfile.write(content)



class StreamingHttpServer(HTTPServer):
    """
    HTTP server for serving streaming video to a web client.
    """
    
    def __init__(self):
        """
        Constructor for the StreamingHttpServer class.
        Initializes the HTTPServer class, sets the HTTP-PORT and 
        StreamingHttpHandler handler, and reads and saves the index.html 
        file into the instance's index_template variable.
        """
        super(StreamingHttpServer, self).__init__(
                    ('', HTTP_PORT), StreamingHttpHandler)
        with io.open('index.html', 'r') as f:
            self.index_template = f.read()


class StreamingWebSocket(WebSocket):
    def opened(self):
        """
        Method called when socket is opened and to print when new clients are connected.
        """
        print("New client connected", flush=True)
        # you can override various WebSocket class methods
        # to do more stuff with WebSockets other than streaming
  
#endregion      

#region UDP_ServerProtocol
# UDP protocol server class
class UDP_ServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue):
        """
        Constructor for the UDP_ServerProtocol class.
        Initializes the queue instance variable to put received data into queue.
        """
        self.queue = queue

    def connection_made(self, transport):
        """
        Method called when a connection is made to the transport.
        """
        self.transport = transport

    # get udp data from smartphone
    def datagram_received(self, data, addr):
        """
        Method called when a datagram (UDP packet: JSON) is received.
        Puts the data and address into the instance's queue.
        """
        # print(f'Received data from {addr}: {data.decode()}', flush=True)
        self.queue.put_nowait((data, addr))
#endregion

#region UART Protokol 
# UART Protokol Klasse
class Uart_Protocol(asyncio.Protocol):
    def __init__(self, queue, queue_handshake):
        """
        Constructor method for the Uart_Protocol class.
        Initializes the queue and queue_handshake instance variables.
        Sets the handshake instance variable to False.
        """
        self.queue = queue
        self.queue_handshake = queue_handshake
        self.handshake = False   #self.handshake = False

    def connection_made(self, transport):
        """
        Method called when a connection is made to the transport.
        """
        self.transport = transport

    # Receive UART data (ICU-protocol) from Teensy and put it into queue for 
    # further processing
    def data_received(self, data):
        """
        Method called when UART data is received.
        If the handshake is already made, decodes the data and puts it into the 
        instance's queue. If the received data is the handshake, sets the handshake 
        instance variable to True and puts a message in the instance's queue_handshake.
        """
        #decoded_data = data.decode(encoding='utf-8')
        print(f'Received data from UART port: {data}', flush=True)
        
        # check if handshake done 
        if self.handshake == True:
            # if handshake done, put received UART data into queue 
            # receive telemetry data
            
            # https://docs.python.org/3/library/struct.html
            # byte order, data type, and size of floats
            byte_order = '<'  # little-endian
            float_type = 'f'  # single-precision float
            float_size = 4  # float größe
            float_count = 8
            
            # decode float values
            floats = struct.unpack(byte_order + float_type * float_count, data)
            
            # put telemetry data into queue to send to smartphone via JSON
            self.queue.put_nowait(floats)
        
        # Check if Teensy is ready
        # if not ready, then wait for Teensy in "process_udp_data" and 
        # discard communication data received from smartphone
        if data == b'\xAA' and self.handshake == False:
            self.handshake == True
            self.queue_handshake.put_nowait(True)
            
#endregion    

#region Flow Control Enable Method
async def config_rtscts():      
    """
    This method sets up the hardware flow control signals, by 
    1. making the rpirtscts executable, 
    2. running the rpirtscts executable 
    3. and then instructing the serial port driver to use the RTS/CTS hardware 
       flow control signals. 
    """
    # make rpirtscts executable
    process = await asyncio.create_subprocess_shell("make", 
                                                    stdout=asyncio.subprocess.PIPE, 
                                                    stderr=asyncio.subprocess.PIPE, 
                                                    cwd="rpirtscts")
    stdout, stderr =  await process.communicate()
    print(stdout, flush=True)
    
    # Run rpirtscts executable (enable -> "on")
    process = await asyncio.create_subprocess_shell("sudo ./rpirtscts on", 
                                                    stdout=asyncio.subprocess.PIPE, 
                                                    stderr=asyncio.subprocess.PIPE, 
                                                    cwd="rpirtscts")
    stdout, stderr = await process.communicate()
    print(stdout, flush=True)
    
    # Instruct the serial port driver to use hardware flow control signals
    process = await asyncio.create_subprocess_shell("sudo stty -F /dev/ttyAMA0 crtscts", 
                                                    stdout=asyncio.subprocess.PIPE, 
                                                    stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await process.communicate()
    print(stdout, flush=True)   
#endregion             
                       
# converts the communication data (JSON) into ICU-protocol umwandeln (Bitoperations 
# and send via UART)
async def process_udp_data(queue_udp, queue_handshake_uart, uart_transport):
    """
    This method receives and processes datagram (UDP packet: 
    JSON communication data), performs bit operations (converting into ICU-Protocol) 
    and sends the data to the Teensy via UART. But first, it waits for the handshake 
    to be done and then continuously receives data from the UDP queue.
    """
    # wait for handshake and perform handshake
    wait_until_handshake = await queue_handshake_uart.get() 
    handshake = bytearray([0xAA])
    uart_transport.write(handshake)
    
    queue_udp.Queue.clear() #TODO: Check, if this addition works
    
    print('Handshake done', flush=True)
    
    while True:
        # discard received ip address and send the communication data to teensy
        data, _ = await queue_udp.get() 
        # print(f'Processing UDP data: {data.decode()}', flush=True)
        
        # convert received communication data (json) into ICU-protocol (Bitoperations)        
        received_CommData = json.loads(data, object_hook=CommData.to_object)
        
        # send data to Teensy via UART
        uart_transport.write(received_CommData.to_uart_data())
        
        # print('Processing UDP data done', flush=True)
    


# sends the received telemetry data (e.g. GPS, sensors, ...) to the smartphone
async def process_uart_recv_data(queue_udp, queue_uart, udp_transport):
    """
    This method receives telemetry data from Teensy via UART and sends it 
    to the connected smartphone via the UDP protocol. It waits until the 
    address is received of the smartphone, before it begins to receive data from the 
    UART queue.
    """
    # get the ip address of the smartphone once and discard received UDP 
    # data (the first time it doesn't work, because process_udp_data also 
    # access the same queue)
    _, addr = await queue_udp.get()   
    print('Smartphone connected', flush=True)
    
    while True:
        data = await queue_uart.get()   # receive telemetry data from Teensy 
                                        # continously
        # print(f'Processing UART data: {data}', flush=True)
        teldata = TelemetryData(data)
        teldataJSON = json.dumps(teldata, cls=TelemetryDataEncoder)
        udp_transport.sendto(teldataJSON, addr)    # send the telemetry data to 
        # smartphone via udp socket
        # print('Processing UART data done', flush=True)
    

        
async def main():
    """
    Main method to run web socket (camera frames), broadcast, UART and UDP-socket.
    """
    #region setup rtscts
    print('Setup: Flow Control', flush=True)
    await config_rtscts()
    print('Flow Control is active', flush=True)
    #endregion
    
    #region camera stuff
    #Camera and the configuration
    print('Initializing camera', flush=True)
    camera = picamera.PiCamera()
    camera.framerate = FRAMERATE
    camera.resolution = (WIDTH, HEIGHT)
    camera.vflip = VFLIP # flips image rightside up, as needed
    camera.hflip = HFLIP # flips image left-right, as needed
    await asyncio.sleep(1) # camera warm-up time

    #Custom output for h264 stream
    output = StreamingOutput()    

    #Websocket
    print('Initializing websockets server on port %d' % WS_PORT, flush=True)
    WebSocketWSGIHandler.http_version = '1.1'
    websocket_server = make_server(
            '', WS_PORT,
            server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=StreamingWebSocket))

    websocket_server.initialize_websockets_manager()
    websocket_thread = Thread(target=websocket_server.serve_forever)

    #Http
    print('Initializing HTTP server on port %d' % HTTP_PORT, flush=True)
    http_server = StreamingHttpServer()
    http_thread = Thread(target=http_server.serve_forever)
   
    #Broadcast
    print('Initializing broadcast thread', flush=True)
    broadcast_thread = BroadcastThread(camera, output, websocket_server)
        
    #endregion

    queue_udp = asyncio.Queue()
    queue_uart = asyncio.Queue()
    queue_uart_handshake = asyncio.Queue()
    
    loop = asyncio.get_running_loop()

    udp_transport, udp_protocol = await loop.create_datagram_endpoint(
        lambda: UDP_ServerProtocol(queue_udp),
        local_addr=('0.0.0.0', SMARTPHONE_PORT)
    )
    
    uart_transport, uart_protocol = await serial_asyncio.create_serial_connection(
        loop, 
        lambda: Uart_Protocol(queue_uart, queue_uart_handshake), 
        '/dev/ttyAMA0', baudrate=2000000, bytesize=8, parity="N", stopbits=1, 
        xonxoff=False, rtscts=True
    )
    
    task_udp = asyncio.create_task(process_udp_data(queue_udp, queue_uart_handshake, 
                                                    uart_transport))
    task_uart = asyncio.create_task(process_uart_recv_data(queue_udp, queue_uart, 
                                                           udp_transport))
    
    print('Starting websockets thread', flush=True)
    websocket_thread.start()
    print('Starting HTTP server thread', flush=True)
    http_thread.start()
    print('Starting recording and broadcastasting thread', flush=True)
    broadcast_thread.start()
    
    # handler for CTRL+C --> Close Application
    def signal_handler(*args):
        # safely stop threads/tasks
        print('Closing UART and UDP transports', flush=True)
        udp_transport.close()
        uart_transport.close()  
        
        task_uart.cancel()
        task_udp.cancel()  
          
        # stop thread first --> then stop camera recording
        print('Waiting for broadcast thread to finish', flush=True)
        broadcast_thread.stop_thread()  
        print('Stopping recording', flush=True)
        camera.stop_recording()
        
        # stop http and other sockets
        print('Shutting down HTTP server', flush=True)
        http_server.shutdown()
        print('Shutting down websockets server', flush=True)
        websocket_server.server_close()
        websocket_server.shutdown()

        print('Waiting for HTTP server thread to finish', flush=True)
        http_thread.join()
        print('Waiting for websockets thread to finish', flush=True)
        websocket_thread.join()
        
        print('Everything is closed', flush=True)
        
        # Prints the running threads (after closing all --> only MainThread)
        main_thread = threading.current_thread()
        for t in threading.enumerate():
            print('Running thread: ', t.getName(), flush=True)
            
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    await asyncio.gather(task_udp, task_uart)
           
if __name__ == '__main__':
    asyncio.run(main())