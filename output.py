# Origin: https://github.com/Onixaz/picamera-h264-web-streaming
# Modified by: Mikail Yoelek

from io import BytesIO
from threading import Condition

class StreamingOutput(object):
    """
    This class is used as a custom output for the h264 stream. It receives a 
    continuous stream of cameradata and writes them into a buffer. When the 
    camerastream contains the sequence 00 00 00 01, the frame is extracted from the 
    buffer. After that, the condition variable is set to signal a frame 
    for broadcasting.
    """
    def __init__(self):
        self.frame = None
        self.buffer = BytesIO()
        self.condition = Condition()
        self.separator = b'\x00\x00\x00\x01'
        
        

    def write(self, buf):
        """
        This method is called when a camerastream is received.
        The data is written to a buffer. If the buffer contains the frame separator 
        (00 00 00 01) the frame is extracted from the buffer and the condition variable is 
        notified.
        """
        if buf.startswith(self.separator):           
            self.buffer.seek(0)
            with self.condition:
                self.frame = self.buffer.read()
                self.condition.notify_all()   
            self.buffer.seek(0)         # moves the buffer to pos 0
            self.buffer.truncate()      # resets the buffer
        return self.buffer.write(buf)