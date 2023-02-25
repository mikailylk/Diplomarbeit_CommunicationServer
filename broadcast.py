# Origin: https://github.com/Onixaz/picamera-h264-web-streaming
# Modified by: Mikail Yoelek

from threading import Thread, Event

class BroadcastThread(Thread):
    """
    A thread that broadcasts camera frames to a websocket server.
    """
    
    def __init__(self, camera, output, websocket_server):
        """
        Constructs a BroadcastThread instance (parameters are camera, streamoutput 
        and websocket server)
        """
        super(BroadcastThread, self).__init__()
        self.camera = camera
        self.output = output
        self.websocket_server = websocket_server
        self.stop_event = Event()

    def run(self):
        """
        This function starts the camera recording and broadcasts the frames to the 
        websocket server. It uses the baseline h264 profile, which fits perfectly 
        for low cost applications like low delay video streams.
        """
        try:
            self.camera.start_recording(self.output, 'h264', profile="baseline")
            while not self.stop_event.is_set():
                with self.output.condition:
                    self.output.condition.wait()
                    self.websocket_server.manager.broadcast(self.output.frame, 
                                                            binary=True)           
        except:
            raise Exception
    
    def stop_thread(self, timeout=5):
        """
        This function stops the thread within a specific timeout.
        """
        self.stop_event.set()
        self.join(timeout)
        if self.is_alive():
            self._stop()