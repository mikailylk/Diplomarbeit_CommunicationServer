import RPi.GPIO as GPIO
import subprocess
import signal
from time import sleep
import asyncio
import sys
from time import sleep

GPIO_PIN_NUMBER = 18
global gpio_state

# get stdout from childprocess and print in console
async def read_stdout_childprocess(queue, stream):
    """
    This function reads the output from a child process's stdout and puts it in a queue.
    """
    while True:
        # , flush=True --> manually force flush --> print instantly
        output = await stream.readline()
        if not output:
            break
        await queue.put(output.decode().strip())

# starts server.py
async def start_childprocess():
    """
    This function starts the server.py child process.

    Returns:
        The subprocess object.
    """
    
    cmd = ["python", "server.py"]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE
    )
    return proc

# stops server.py
async def stop_childprocess(process):
    """
     This function stops the specified child process.
    """
    process.send_signal(signal.SIGINT)
    await process.wait()            

# check gpio pin state (rising/falling edge)
def GPIO_pin_state(channel):
    """
    Event callback for GPIO pin (channel) state changes.
    """
    global gpio_state
    if GPIO.input(channel):
        print('rising edge')
        gpio_state = True
    else:
        print('falling edge')
        gpio_state = False
        

# main method         
async def main():
    """
    Main method to run the program.
    """
    # Set up the GPIO pin as an input
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_PIN_NUMBER, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    process = None
    task_read_stdout = None
    
    # queue for print stdout
    queue = asyncio.Queue()
    
    global gpio_state 
    gpio_state= False
    
    # add callback event, when gpio changes state (rising/falling)
    GPIO.add_event_detect(GPIO_PIN_NUMBER, GPIO.BOTH, 
                          callback=GPIO_pin_state,
                          bouncetime=1000)  # add rising/falling edge detection on a channel
    try:
        while True:
            # add new childprocess, when childprocess doesn't already exists
            if process is None and gpio_state is True:
                print('----------starting process-----------------')
                # Start the subprocess when rising edge
                process = await start_childprocess()
                task_read_stdout = asyncio.create_task(read_stdout_childprocess(queue, process.stdout))
                await asyncio.sleep(5) # wait until server has started
            
            # stop childprocess and cancel read stdout task
            elif process is not None and gpio_state is False:
                print('----------ending process--------------------')
                await stop_childprocess(process)
                process = None
                task_read_stdout.cancel

            # print stdout of childprocess
            while not queue.empty():
                output = await queue.get()
                print(output)
                
            await asyncio.sleep(0.01)
            
    except KeyboardInterrupt:        
        print('cancelling')
        # cleanup
        task_read_stdout.cancel()
        
if __name__ == '__main__':
    try:
        print('----------starting programm-----------------')
        # force kill server.py process (if any running)
        subprocess.run("sudo pkill -f server.py", shell=True)
        asyncio.run(main())
    except KeyboardInterrupt:
        # force kill server.py process (if any running)
        subprocess.run("sudo pkill -f server.py", shell=True)
        print('----------ending programm--------------------')
        sys.exit(0)