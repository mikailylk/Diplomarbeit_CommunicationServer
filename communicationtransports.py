import asyncio
import struct 

#region UDP_ServerProtocol
# UDP protocol server class
class UDP_ServerProtocol(asyncio.DatagramProtocol):
    def __init__(self, queue):
        """
        Constructor for the UDP_ServerProtocol class.
        Initializes the queue instance variable to put received data in a queue.
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
        self.handshake = False  
        # self.handshake = True     # testing purposes

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
        If the handshake is already done, decodes the data and puts it into the 
        instance's queue. If the received data is the handshake, sets the handshake 
        instance variable to True and puts a message in the instance's queue_handshake.
        """
        #decoded_data = data.decode(encoding='utf-8')
        # print(f'Received data from UART port: {data}', flush=True)
        
        # check if handshake done 
        if self.handshake == True:
            # if handshake done, put received UART data into queue 
            # receive telemetry data
            
            # Check if the length of data is 32 bytes
            if (len(data) == 32):
                # region unpacking float values
                # https://docs.python.org/3/library/struct.html
                # byte order, data type, and size of floats
                byte_order = '<'    # little-endian
                float_type = 'f'    # single-precision float
                float_size = 4      # float size
                float_count = 8     # 8x4Bytes => 32 Bytes
                
                # decode float values
                floats = struct.unpack(byte_order + float_type * float_count, data)
            
                # put telemetry data into queue to send to smartphone via JSON
                # print(floats, flush=True)
                
                self.queue.put_nowait(floats)
                # endregion
            else:
                # wrong bit size
                print('The length of telemetrydata is incorrect! Length: ', flush=True)
                print(len(data), flush=True)
                pass
            

        # Check if Teensy is ready
        # if not ready, then wait for Teensy in "process_udp_data" and 
        # discard communication data received from smartphone
        if data == b'\xAA' and self.handshake == False:
            self.handshake = True
            self.queue_handshake.put_nowait(True)
            print('Handshake in UART-transport done!', flush=True)
#endregion    