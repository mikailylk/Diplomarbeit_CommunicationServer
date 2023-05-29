# Origin: https://github.com/Onixaz/picamera-h264-web-streaming
# Modified by: Mikail Yoelek

# libraries
import picamera         # for setup picamera
import json             # for serializing, deserializing data
import serial_asyncio   # for creating async serial connection
import asyncio          
import threading        
import sys              # for exiting program with exit number
import signal           # for keyboard interrupts
import config           # config for camera, ports, ...
import time

from telemetrydata import TelemetryData,TelemetryDataEncoder
from http_server import StreamingHttpHandler, StreamingHttpServer, StreamingWebSocket
from communicationdata import CommData
from communicationtransports import UDP_ServerProtocol, Uart_Protocol

from threading import Thread

from wsgiref.simple_server import make_server

from broadcast import BroadcastThread
from output import StreamingOutput

from ws4py.server.wsgirefserver import (
    WSGIServer,
    WebSocketWSGIHandler,
    WebSocketWSGIRequestHandler,
)

from ws4py.server.wsgiutils import WebSocketWSGIApplication


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
                       
# converts the communication data (JSON) into ICU-protocol (Bitoperations 
# and send via UART)
async def process_udp_data(queue_udp, queue_recent_udp_connection, queue_handshake_uart, 
                           uart_transport):
    """
    This method receives and processes datagram (UDP packet: 
    JSON communication data), performs bit operations (converting into ICU-Protocol) 
    and sends the data to the Teensy via UART. But first, it waits for the handshake 
    to be done and then continuously receives data from the UDP queue.
    """
    # wait for handshake and perform handshake
    print('Waiting for Handshake', flush=True)
    
    wait_until_handshake = await queue_handshake_uart.get() 
    handshake = bytearray([0xAA])
    uart_transport.write(handshake)

    # TODO: find another workaround for clearing queue_udp
    
    print('Handshake done', flush=True)
    
    # # TESTING PURPOSES
    # import struct
    # # DELETE PREVIOUS LINE
    
    recently_connected_device = None
    
    while True:
        data, address = await queue_udp.get() 
        
        if recently_connected_device != address:
            # use IP-address of connected device and put it into queue to reply telemetry data
            recently_connected_device = address
            queue_recent_udp_connection.put_nowait(address)
            print('Recently connected device: ' + str(address), flush=True)
            
        # print(f'Processing UDP data: {data.decode()}', flush=True)
        
        # convert received communication data (json) into ICU-protocol (Bitoperations)        
        received_CommData = json.loads(data, object_hook=CommData.to_object)
        
        print(received_CommData.to_uart_data(), flush=True)
        # send data to Teensy via UART
        uart_transport.write(received_CommData.to_uart_data())
        
        # region testing loopback
        # Create a list of the float values
        # float_values = [12.5, 23, 25.8, 466, 54, 24, 9.856, 47.58]

        # # Pack the floats into a binary string
        # packed = struct.pack('<ffffffff', *float_values)
        # bytearray_32 = bytearray(packed)
            
        # uart_transport.write(packed)
        # endregion
        
        # IMPORTANT:
        await asyncio.sleep(0.001)       # check if sleep is needed
        
        # print('Processing UDP data done', flush=True)
    


# sends the received telemetry data (e.g. GPS, sensors, ...) to the smartphone
async def process_uart_recv_data(queue_recent_udp_connection, queue_uart, udp_transport):
    """
    This method receives telemetry data from Teensy via UART and sends it 
    to the connected smartphone via the UDP protocol. It waits until the 
    address is received of the smartphone, before it begins to receive data from the 
    UART queue.
    """
    # get the ip address of the smartphone once
    addr = await queue_recent_udp_connection.get()   
    
    print('Smartphone connected', flush=True)
    print('Ready for telemetry data.', flush=True)
    
    while True:
        # check if connection is new --> send to the recently connected device
        if not queue_recent_udp_connection.empty():
            addr = await queue_recent_udp_connection.get()  
            print(f'New client connected: {addr}', flush=True)
            
        data = await queue_uart.get()   # receive telemetry data from Teensy 
                                        # continously
                                        
        # print(f'Processing UART data: {data}', flush=True)
        teldata = TelemetryData(time.time(), data)
        teldataJSON = json.dumps(teldata, cls=TelemetryDataEncoder)
        udp_transport.sendto(teldataJSON.encode('utf-8'), addr)     # send the telemetry data to 
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
    camera.framerate = config.FRAMERATE
    camera.resolution = (config.WIDTH, config.HEIGHT)
    camera.vflip = config.VFLIP # flips image rightside up, as needed
    camera.hflip = config.HFLIP # flips image left-right, as needed
    await asyncio.sleep(1) # camera warm-up time

    #Custom output for h264 stream
    output = StreamingOutput()    

    #Websocket
    print('Initializing websockets server on port %d' % config.WS_PORT, flush=True)
    WebSocketWSGIHandler.http_version = '1.1'
    websocket_server = make_server(
            '', config.WS_PORT,
            server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=StreamingWebSocket))

    websocket_server.initialize_websockets_manager()
    websocket_thread = Thread(target=websocket_server.serve_forever)

    #Http
    print('Initializing HTTP server on port %d' % config.HTTP_PORT, flush=True)
    http_server = StreamingHttpServer()
    http_thread = Thread(target=http_server.serve_forever)
   
    #Broadcast
    print('Initializing broadcast thread', flush=True)
    broadcast_thread = BroadcastThread(camera, output, websocket_server)
        
    #endregion

    queue_udp = asyncio.Queue()
    queue_recent_udp_connection = asyncio.Queue()   # get the recent connected device's
                                                    # IP address and send telemetry data to it
    queue_uart = asyncio.Queue()
    queue_uart_handshake = asyncio.Queue()
    
    loop = asyncio.get_running_loop()

    udp_transport, udp_protocol = await loop.create_datagram_endpoint(
        lambda: UDP_ServerProtocol(queue_udp),
        local_addr=('0.0.0.0', config.SMARTPHONE_PORT)
    )
    
    uart_transport, uart_protocol = await serial_asyncio.create_serial_connection(
        loop, 
        lambda: Uart_Protocol(queue_uart, queue_uart_handshake), 
        '/dev/ttyAMA0', baudrate=2000000, bytesize=8, parity="N", stopbits=1, 
        xonxoff=False, rtscts=True
    )
    
    task_udp = asyncio.create_task(process_udp_data(queue_udp, queue_recent_udp_connection,
                                                    queue_uart_handshake, uart_transport))
    task_uart = asyncio.create_task(process_uart_recv_data(queue_recent_udp_connection, queue_uart, 
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
