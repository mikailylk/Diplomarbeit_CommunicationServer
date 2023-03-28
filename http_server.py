import io
import config

from http.server import HTTPServer, BaseHTTPRequestHandler
from ws4py.websocket import WebSocket
from string import Template
from os import curdir, sep

from time import time 


#region streaming httphandler
class StreamingHttpHandler(BaseHTTPRequestHandler):
    """
    HTTP handler for serving streaming video to a web client.
    """
    
    def do_HEAD(self):
        """
        This method responds to HTTP HEAD requests.
        """
        self.do_GET()


    def do_GET(self):
        """
        This method responds to HTTP GET requests.
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
                ADDRESS='%s:%d' % (self.request.getsockname()[0], config.WS_PORT)
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
    HTTP server for streaming video to a client.
    """
    
    def __init__(self):
        """
        Constructor: 
        Initializes the HTTPServer class, sets the HTTP-PORT and 
        StreamingHttpHandler handler. Then it reads and saves the index.html 
        file into index_template variable.
        """
        super(StreamingHttpServer, self).__init__(
                    ('', config.HTTP_PORT), StreamingHttpHandler)
        with io.open('index.html', 'r') as f:
            self.index_template = f.read()


class StreamingWebSocket(WebSocket):
    def opened(self):
        """
        This method is called, when socket is opened. It also prints, when new clients 
        are connected.
        """
        print("New client connected", flush=True)
        # you can override various WebSocket class methods
        # to do more stuff with WebSockets other than streaming
  
#endregion      

