# https://howtodoinjava.com/python-json/custom-deserialization/
import json

class CommData:
    """
    A class to represent communication data and to convert it to an ICU protocol.
    """
    def __init__(self, Pitch, Roll, Yaw, Power, PitchG, RollG, YawG):
        """
        Initializes a CommData object with values for pitch, roll, ...
        """
        self.Pitch = Pitch
        self.Roll = Roll
        self.Yaw = Yaw
        self.Power = Power
        self.PitchG = PitchG
        self.RollG = RollG
        self.YawG = YawG
    
    def to_object(d):
        """
        Converts a JSON object to a CommData object
        """
        inst = CommData(d['Pitch'], d['Roll'], d['Yaw'], d['Power'],
                        d['PitchG'], d['RollG'], d['YawG'])
        return inst
    
    def to_uart_data(self):
        """
        Converts the communication data to ICU protocol and returns a bytearray
        """
        pitch = int(self.Pitch)
        roll = int(self.Roll)
        yaw = int(self.Yaw)
        power = int(self.Power)
        pitchg = int(self.PitchG)
        rollg = int(self.RollG)
        yawg = int(self.YawG)
        
        # split into 2x8 Bit array
        # TODO: should it get negative numbers?
        pitch_arr = pitch.to_bytes(2, 'little')  
        # pitchg_arr = pitchg.to_bytes(4, 'little', signed=True) # example for signed int (32 Bits)
        
        roll_arr = roll.to_bytes(2, 'little')
        yaw_arr = yaw.to_bytes(2, 'little')
        power_arr = power.to_bytes(2, 'little')
        
        pitchg_arr = pitchg.to_bytes(2, 'little')
        rollg_arr = rollg.to_bytes(2, 'little')
        yawg_arr = yawg.to_bytes(2, 'little')
        
        # 8 Bits Power
        byte0 = power_arr[0]
        # 5 Bits Yaw ; 3 Bits Power
        byte1 =  ((yaw_arr[0]<<3) & 0b11111000) | (power_arr[1] & 0b00000111)
        # 2 Bits Pitch ; 6 Bits Yaw ( 3 Bits ; 3 Bits)
        byte2 =  ((pitch_arr[0]<<6) & 0b11000000) | ((yaw_arr[1]<<3) & 0b00111000) | ((yaw_arr[0]>>5) & 0b00000111)
        # 8 Bits Pitch (2 Bits ; 6 Bits) 
        byte3 = ((pitch_arr[1]<<6) & 0b11000000) | ((pitch_arr[0]>>2) & 0b00111111)
        # 7 Bits Roll ; 1 Bit Pitch (1 Bit ; 0) 
        byte4 = ((roll_arr[0]<<1) & 0b11111110) | ((pitch_arr[1]>>2) & 0b00000001)
        # 4 Bits YawG; 4 Bits Roll (3 Bits; 1 Bit)
        byte5 =  ((yawg_arr[0]<<4) & 0b11110000) | ((roll_arr[1]<<1) & 0b00001110) | ((roll_arr[0]>>7) & 0b00000001)
        # 2 Bits PitchG; 6 Bits YawG (2 Bits ;4 Bits) 
        byte6 =  ((pitchg_arr[0]<<6) & 0b11000000) | ((yawg_arr[1]<<4) & 0b00110000) | ((yawg_arr[0]>>4) & 0b00001111)
        # 8 Bits PitchG (2Bits ; 6 Bits)
        byte7 = ((pitchg_arr[1]<<6) & 0b11000000) | ((pitchg_arr[0]>>2) & 0b00111111)
        
        # print the representing bytes (testing purposes)
        # print(byte0)
        # print(byte1)
        # print(byte2)
        # print(byte3)
        # print(byte4)
        # print(byte5)
        # print(byte6)
        # print(byte7)

        uart_data = bytearray([byte0, byte1, byte2, byte3, byte4, byte5, byte6, byte7])
        # print("ICU-Prot: ",uart_data)
        return uart_data

    def __iter__(self):
        yield from {
            "Roll": self.Roll,
            "Pitch": self.Pitch,
            "Yaw": self.Yaw,
            "Power": self.Power,
            "PitchG": self.PitchG,
            "RollG": self.RollG,
            "YawG": self.YawG,
        }.items()
    
    def __str__(self):
        '''
        Returns a JSON string representation of the object
        '''
        return json.dumps(dict(self), ensure_ascii=False)

    def __repr__(self):
        '''
        Returns the string representation of the object
        '''
        return self.__str__()
    

    def to_json(self):
        '''
        Returns a JSON string representation of the object
        '''
        return self.__str__()
    
    
if __name__ == "__main__":
    '''
    Testprogramm for ICU protocol (bitoperation).
    '''
    import json
    import serial
    
    message = '{"Pitch":999,"Roll":555,"Yaw":888,"Power":666,"PitchG":777,"RollG":766,"YawG":944}'
    
    commdat = json.loads(message, object_hook=CommData.to_object)
    
    serialPort = serial.Serial("/dev/ttyAMA", baudrate=2000000, bytesize=8, parity="N", stopbits=1, timeout=None, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=None)
    
    print("Pitch: ", commdat.Pitch)
    uart_send_data = commdat.to_uart_data()
    print(uart_send_data)
    try:
        while True:
            serialPort.write(uart_send_data)
    except:
        serialPort.close()
