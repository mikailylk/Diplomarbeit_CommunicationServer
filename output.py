# Origin: https://github.com/Onixaz/picamera-h264-web-streaming
# Modified by: Mikail Yoelek

from io import BytesIO
from threading import Condition

class StreamingOutput(object):
    """
    This class is used as a custom output for the h264 stream. It receives a 
    continuous stream of data from the camera and writes it to a buffer. When the 
    stream of data contains the frame separator, the frame is extracted from the 
    buffer, and the condition variable is notified, which signals that a frame is 
    ready for broadcast.
    """
    def __init__(self):
        self.frame = None
        self.buffer = BytesIO()
        self.condition = Condition()
        self.separator = b'\x00\x00\x00\x01'
        
        

    def write(self, buf):
        """
        This method is called when a stream of data is received from the camera. 
        The data is written to the buffer. When the data contains the frame separator, 
        the frame is extracted from the buffer and the condition variable is 
        notified.
        """
        if buf.startswith(self.separator):           
            self.buffer.seek(0)
            with self.condition:
                self.frame = self.buffer.read()
                self.condition.notify_all()   
            self.buffer.seek(0)
            self.buffer.truncate() 
        return self.buffer.write(buf)