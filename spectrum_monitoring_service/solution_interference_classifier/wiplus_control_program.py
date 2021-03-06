__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2017, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


# Definition of Local Control Program
def wiplus_detector_cp(controller):
    # do all needed imports here!!!
    import time
    import random
    import datetime
    import threading

    global lteu_detection_quality
    lteu_detection_quality = 0.0

    global free_air_time_ratio
    free_air_time_ratio = 1.0

    global runControllerLoop
    runControllerLoop = False

    def controller_loop():
        global runControllerLoop
        global lteu_detection_quality
        global free_air_time_ratio

        while runControllerLoop:
            lteu_detection_quality = random.random()
            free_air_time_ratio = random.random()
            print("WiPLUS detects LTE-U with quality: ", lteu_detection_quality)
            time.sleep(2)

    # control loop
    print(("Local Control Program - Name: {}, Id: {} - STARTED".format(controller.name, controller.id)))

    runControllerLoop = True
    controllerLoop = threading.Thread(target=controller_loop)
    controllerLoop.daemon = True
    controllerLoop.start()

    while not controller.is_stopped():
        msg = controller.recv(timeout=1)
        if msg:
            cmd = msg["cmd"]
            if cmd == "get_interferers_info":
                # technology: quality of discovery (confidence)
                detected_interferers = {"LTE-U": lteu_detection_quality, "WiFi": 0.0, "ZigBee": 0.0}
                controller.send_upstream({"response": detected_interferers})
            if cmd == "get_free_air_time":
                controller.send_upstream({"response": free_air_time_ratio})
        else:
            # print(("{} Waiting for message".format(datetime.datetime.now())))
            pass

    runControllerLoop = False
    print(("Local Control Program - Name: {}, Id: {} - STOPPED".format(controller.name, controller.id)))
