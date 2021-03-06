import json
import zmq
import threading
from kvsimple import KVMsg

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2017, Technische Universität Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz@tkn.tu-berlin.de"


class GlobalSolutionControllerProxy(object):
    """docstring for GlobalSolutionControllerProxy"""
    def __init__(self, ip_address="127.0.0.1", requestPort=7001, subPort=7000):
        super(GlobalSolutionControllerProxy, self).__init__()

        self.solutionName = None
        self.commandList = []
        self.eventList = []
        self.commands = {}

        self.ctx = zmq.Context()
        # Prepare our REQ/REP socket
        self.requestSocket = self.ctx.socket(zmq.DEALER)
        self.requestSocket.linger = 0
        url = "tcp://" + ip_address + ":" + str(requestPort)
        self.requestSocket.connect(url)
        # Prepare our SUBSCRIVER socket
        self.subSocket = self.ctx.socket(zmq.SUB)
        self.subSocket.linger = 0
        self.subSocket.setsockopt(zmq.SUBSCRIBE, b'')
        url = "tcp://" + ip_address + ":" + str(subPort)
        self.subSocket.connect(url)
        self.cmdRxThread = None

    def set_solution_attributes(self, solutionName, commands, eventList):
        self.solutionName = solutionName
        self.commands = commands
        self.commandList = list(commands.keys())
        self.eventList = eventList

    def register_solution(self):
        """
        SETUP SOLUTION GLOBAL CONTROLLER CONNECTION
        This function is used to setup the connection with the experiment GUI,
        a ZMQ socket server is created on port 8500,
        able to receive command from GUI
        """
        # Register solution to solution global controller
        # Activation    Event
        # De - activation
        # Event     List    of  monitoring  parameters
        # List  of  control knobs / parameters

        # create the json format message
        msg = {"type": "registerRequest",
               "solution": self.solutionName,
               "commandList": self.commandList,
               "eventList": self.eventList}

        sequence = 1
        kvmsg = KVMsg(sequence)
        kvmsg.key = b"generic"
        kvmsg.body = json.dumps(msg).encode('utf-8')
        # send the message
        kvmsg.send(self.requestSocket)

        # process the registerRespons
        try:
            kvmsg_reply = KVMsg.recv(self.requestSocket)
        except Exception:
            return False

        body = kvmsg_reply.body
        parsed_json = json.loads(body.decode("utf-8"))
        if "type" in parsed_json:
            mtype = parsed_json["type"]
            if mtype == "registerResponse":
                print("Received registration registerResponse")
                return True
        return False

    def command_subscriber(self):
        while True:
            try:
                kvmsg = KVMsg.recv(self.subSocket)
                mdict = kvmsg.body.decode('utf-8')
                mdict = json.loads(mdict)
                involvedSolutions = mdict.get("involvedSolutions", [])

                if self.solutionName in involvedSolutions:
                    commandList = mdict.get("commandList", [])
                    if isinstance(commandList, str):
                        commandList = [commandList]

                    for cmd in commandList:
                        if cmd in self.commands:
                            print("Execute command:", cmd)
                            function = self.commands[cmd]
                            function()

            except KeyboardInterrupt:
                return
            except Exception:
                break  # Interrupted

    def start_command_listener(self):
        # Start service for COMMAND/UPDATE from global solution controller
        self.cmdRxThread = threading.Thread(target=self.command_subscriber)
        self.cmdRxThread.daemon = True
        self.cmdRxThread.start()

    def send_monitor_report(self, mon_type, value, unit):
        msg = {'type': 'monitorReport',
               'monitorType': mon_type,
               'monitorValue': value,
               'monitorUnit': unit,
               }
        sequence = 0
        kvmsg = KVMsg(sequence)
        kvmsg.key = b"generic"
        kvmsg.body = json.dumps(msg).encode('utf-8')
        kvmsg.send(self.requestSocket)

    def send_event(self, eventType):
        msg = {'type': 'eventReport',
               'solution': self.solutionName,
               'eventType': eventType,
               }
        sequence = 0
        kvmsg = KVMsg(sequence)
        kvmsg.key = b"generic"
        kvmsg.body = json.dumps(msg).encode('utf-8')
        kvmsg.send(self.requestSocket)
