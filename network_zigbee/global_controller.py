#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
global_controller.py: Contiki global control program

Usage:
   global_controller.py [options] [-q | -v]

Options:
   --config configFile Config directory path

Example:
   python global_controller.py --config config/portable

Other options:
   -h, --help          show this help message and exit
   -q, --quiet         print less text
   -v, --verbose       print more text
   --version           show version and exit
"""

__author__ = "Jan Bauwens & Peter Ruckebusch"
__copyright__ = "Copyright (c) ugent - idlab - imec"
__version__ = "0.1.0"
__email__ = "jan.bauwens2@ugent.be; peter.ruckebusch@ugent.be"

import datetime
import time
import logging
import gevent
import yaml
import sys
import math

from contiki.contiki_helpers.global_node_manager import *
from contiki.contiki_helpers.taisc_manager import *
from contiki.contiki_helpers.app_manager import *
from lib.global_controller_proxy import GlobalSolutionControllerProxy

## GLOBALS:
taisc_manager = None
app_manager = None
global_node_manager = None
solutionCtrProxy = None
blacklisted_channels = []
whitelisted_channels = []
wifi_to_tsch_channels_dct = {}
per_dictionary = {}
number_of_packets_received = 0
traffic_type = 0
mac_mode = "TSCH"
lte_wifi_coexistence_enabled = 0
# 0 = OFF
# 1 = LOW
# 2 = MEDIUM
# 3 = HIGH

## CALLBACKS:
def default_callback(group, node, cmd, data):
    print("{} DEFAULT CALLBACK : Group: {}, NodeName: {}, Cmd: {}, Returns: {}".format(datetime.datetime.now(), group, node.name, cmd, data))

def print_response(group, node, data):
    print("{} Print response : Group:{}, NodeIP:{}, Result:{}".format(datetime.datetime.now(), group, node.ip, data))

# PER:
# Keep track on the number of failed packets
# Dictionary with:
# - keys = node id's
# - values = [ number_of_packets_requested_prev, number_of_packets_success_prev, number_of_packets_requested_prev, number_of_packets_success_prev,  ]
per_value_prev = 0
def macstats_event_cb(mac_address, event_name, event_value):
    global solutionCtrProxy, number_of_packets_received, per_value_prev
    print(mac_address, event_name, event_value)
    if mac_address == 1:
        number_of_packets_received_cur = event_value[10]
        number_of_packets_requested = 0
        number_of_packets_transmitted = 0
        for node_id in per_dictionary.keys():
            number_of_packets_requested = per_dictionary[node_id][2] - per_dictionary[node_id][0]
            number_of_packets_transmitted = per_dictionary[node_id][3] - per_dictionary[node_id][1]
        if number_of_packets_requested != 0:
            per_value = (
                (number_of_packets_requested - number_of_packets_transmitted) 
                / number_of_packets_requested * 100
                + per_value_prev)
            if per_value < 0:
                per_value_prev = per_value
                per_value = 0
            else:
                per_value_prev = 0
        else:
            per_value = 0

        value = { "Zigbee": { 
            "THR":  (number_of_packets_received_cur - number_of_packets_received) * 128 * 8 * 1000000 / event_value[0] / 1024,
            "PER":  per_value
        }}
        solutionCtrProxy.send_monitor_report("performance", value)
        number_of_packets_received = number_of_packets_received_cur
    else:
        if mac_address not in per_dictionary:
            per_dictionary[mac_address] = [0,0,0,0]
        per_dictionary[mac_address][0] = per_dictionary[mac_address][2] 
        per_dictionary[mac_address][1] = per_dictionary[mac_address][3] 
        per_dictionary[mac_address][2] = event_value[1]
        per_dictionary[mac_address][3] = event_value[4]


## HELPER functions:
def mapWifiOnZigbeeChannels(log, channel_mapping):
    dct = {}
    try:
        file_n = open(channel_mapping, 'rt')
        import csv
        reader = csv.DictReader(file_n)
        for row in reader:
            dct[int(row["ieee80211"])] = []
            for x in row["ieee802154"].split('-'):
                dct[int(row["ieee80211"])].append(int(x))
    except Exception as e:
        logging.fatal("An error occurred while reading nodes: %s" % e)
    finally:
        file_n.close()
    return dct

def control_traffic(traffic_type):  
    global mac_mode, taisc_manager
    
    if traffic_type != 0:
        # Select the server and client nodes based on MAC mode + calculate the maximum possible inter packet delay per node
        if mac_mode == "TSCH":
            server_nodes = [1]
            client_nodes = range(2,len(global_node_manager.get_mac_address_list())+1)
            slot_length = taisc_manager.read_macconfiguration(["IEEE802154e_macTsTimeslotLength"], 1)
            logging.error(slot_length)
            send_interval = int(math.floor(
                slot_length[1]["IEEE802154e_macTsTimeslotLength"] 
                * (len(global_node_manager.get_mac_address_list()) + 2) # Superframe size (beacon, upstream, downstream+)
                / 1000 * 3 / traffic_type))
            logging.error("Send interval is {}".format(send_interval))
            app_manager.update_configuration({"app_send_interval": send_interval}, global_node_manager.get_mac_address_list())

            # Activate:
            logging.info("Activating server {}".format(server_nodes))
            app_manager.update_configuration({"app_activate": 1},server_nodes)
            logging.info("Activating clients {}".format(client_nodes))
            app_manager.update_configuration({"app_activate": 2},client_nodes)
        elif mac_mode == "LTE_COEXISTENCE":
            server_nodes = [1]
            client_nodes = [3]
            send_interval = 30
            taisc_manager.update_macconfiguration({'TAISC_PG_ACTIVE' : 1})
       
    else:
        # De-activate:
        logging.info("Stopping   {}".format(global_node_manager.get_mac_address_list()))
        app_manager.update_configuration({"app_activate": 0},global_node_manager.get_mac_address_list())

## Commands implementation:
def blacklist():
    global blacklisted_channels
    blacklisted_channels.append(wifi_to_tsch_channels_dct[6])
    logging.info("BLACKLIST {}".format(blacklisted_channels))

def whitelist():
    global whitelisted_channels
    whitelisted_channels.append(wifi_to_tsch_channels_dct[6])
    logging.info("WHITELIST {}".format(whitelisted_channels))

def sicslowpan_traffic(traffic_type_value):
    global traffic_type
    traffic_type = traffic_type_value
    
def lte_wifi_coexistence(enable):
    global lte_wifi_coexistence_enabled
    lte_wifi_coexistence_enabled = enable
    logging.info("lte_wifi_coexistence {}".format(lte_wifi_coexistence_enabled))

## MAIN functionality:
def main(args):
    global solutionCtrProxy, whitelisted_channels, blacklisted_channels, mac_mode, lte_wifi_coexistence_enabled
    # Init logging
    logging.debug(args)
    logging.info('******     WISHFUL  *****')
    logging.info('****** Starting solution (network_zigbee) ******')

    """
    ****** setup the communication with the solution global controller ******
    """

    solutionCtrProxy = GlobalSolutionControllerProxy(ip_address="172.16.16.12", requestPort=7001, subPort=7000)
    networkName = "network_zigbee"
    solutionName = "blacklisting"
    commands = {
        "6LOWPAN_BLACKLIST": blacklist,
        "6LOWPAN_WHITELIST": whitelist,
        "TRAFFIC": sicslowpan_traffic,
        "LTE_WIFI_ZIGBEE": lte_wifi_coexistence,
        }
    monitorList = ["6lowpan-THR", "6lowpan-PER"]
    solutionCtrProxy.set_solution_attributes(networkName, solutionName, commands, monitorList)

    # Register network_zigbee solution to global solution controller
    response = solutionCtrProxy.register_solution()
    if response:
        logging.info("Solution was correctly registered to GlobalSolutionController")
        solutionCtrProxy.start_command_listener()
    else:
        logging.error("Solution was not registered to Global Solution Controller")

    # Update the TSCH configuration:
    contiki_nodes = global_node_manager.get_mac_address_list()
    logging.info("Connected nodes {}".format([str(node) for node in contiki_nodes]))
    
    mac_mode = "TSCH"
    taisc_manager.activate_radio_program(mac_mode)
    taisc_manager.update_slotframe('taisc_slotframe.csv', mac_mode)
    taisc_manager.update_macconfiguration({'IEEE802154e_macSlotframeSize': len(contiki_nodes) + 1})
    
    logging.info("Finished configuring TSCH")
    
    current_traffic_type = traffic_type

    while True:
        if len(whitelisted_channels):
            taisc_manager.whitelist_channels(whitelisted_channels)
            whitelisted_channels = []
        if len(blacklisted_channels):
            taisc_manager.blacklist_channels(blacklisted_channels)
            blacklisted_channels = []
        if current_traffic_type != traffic_type:
            control_traffic(traffic_type)
            current_traffic_type = traffic_type
        if lte_wifi_coexistence_enabled and mac_mode != "LTE_COEXISTENCE":
            mac_mode = "LTE_COEXISTENCE"
            taisc_manager.activate_radio_program(mac_mode)
            control_traffic(0)
            control_traffic(current_traffic_type)
            
        gevent.sleep(1)
    logging.info('Controller Exiting')
    sys.exit()

if __name__ == "__main__":
    try:
        from docopt import docopt
    except:
        print("""
        Please install docopt using:
            pip install docopt==0.6.1
        For more refer to:
        https://github.com/docopt/docopt
        """)
        raise

    args = docopt(__doc__, version=__version__)
    
    # Logging:
    if args['--verbose']:
        log_level = logging.DEBUG
    elif args['--quiet']:
        log_level = logging.ERROR
    else:
        log_level = logging.INFO  # default

    logfile = None
    if '--logfile' in args:
        logfile = args['--logfile']

    logging.basicConfig(filename=logfile, level=log_level,
        format='%(asctime)s - %(name)s.%(funcName)s() - %(levelname)s - %(message)s')

    # Set the paths:
    config_file_path = "{}/global_config.yaml".format(args['--config'])
    nodes_file_path = "{}/nodes.yaml".format(args['--config'])

    # Load the config file:
    global_controller_config = None
    with open(config_file_path, 'r') as file_handler:
        global_controller_config = yaml.load(file_handler)
    
    # Configure the node manager:
    global_node_manager = GlobalNodeManager(global_controller_config)
    global_node_manager.set_default_callback(default_callback)

    # Wait for all agents to connect to the global controller:
    with open(nodes_file_path, 'r') as file_handler:
        node_config = yaml.load(file_handler)
    global_node_manager.wait_for_agents(node_config['ip_address_list'])
    
    # Configure the helpers:   
    taisc_manager = TAISCMACManager(global_node_manager, mac_mode)
    app_manager = AppManager(global_node_manager)
    
    # Create blacklisting dict:
    wifi_to_tsch_channels_dct = mapWifiOnZigbeeChannels(logging, 'ieee80211_to_ieee802154_channels.csv')
    
    # Set RPL border router:
    app_manager.rpl_set_border_router([0xfd, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01],1)

    # Set the event callback:
    logging.info("Start local monitoring cp and events")
    global_node_manager.start_local_monitoring_cp()
    gevent.sleep(1)
    taisc_manager.subscribe_events(["IEEE802154_event_macStats"], macstats_event_cb, 0)

    # Start MAIN functionality:
    try:
        main(args)
        print('End main')
    except KeyboardInterrupt:
        logging.debug("Controller exits")
    finally:
        logging.debug("Exit")
        global_node_manager.stop()
