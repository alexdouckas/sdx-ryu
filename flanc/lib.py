#  Author:
#  Rudiger Birkner (Networked Systems Group ETH Zurich)

from Queue import Queue

from ryu.ofproto import ether
from ryu.ofproto import inet

LOG = False

class Config(object):
    def __init__(self, config_file):
        self.server = None

        self.mode = None
        self.ofv = None
        self.tables = None
        self.dpids = None
        self.dpid_2_name = {}
        self.datapath_ports = None

        self.datapaths = {}
        self.parser = None
        self.ofproto = None

        # loading config file
        config = json.load(open(config_file, 'r'))

        # read from file
        if "fabric mode" in config:
            if config["fabric mode"] == "multi-switch":
                self.mode = 0
            elif config["fabric mode"] == "multi-table":
                self.mode = 1

        if "fabric options" in config:
            if self.mode == 1 and "tables" in config["fabric options"]:
                self.tables = config["fabric options"]["tables"]
            if self.mode == 0 and "dpids" in config["fabric options"]:
                self.dpids = config["fabric options"]["dpids"]
                for k,v in self.dpids.iteritems()
                    self.dpid_2_name[v] = k
            if "OF version" in config["fabric options"]:
                self.ofv = config["fabric options"]["OF version"]

        if "fabric connections" in config:
            self.datapath_ports = config["fabric connections"]

        if "server" in config:
            self.server = config["server"]
        else:
            raise InvalidConfigError(config)

        # check if valid config
        if self.mode == 0:
            if not (self.ofv and self.dpids and self.datapath_ports):
                raise InvalidConfigError(config)
        elif self.mode == 1:
            if not (self.ofv = "1.3" and self.tables and self.datapath_ports):
                raise InvalidConfigError(config)
        else:
            raise InvalidConfigError(config)

class InvalidConfigError(Exception):
    def __init__(self, flow_mod):
        self.flow_mod = flow_mod
    def __str__(self):
        return repr(self.flow_mod)

class MultiTableController():
    def __init__(self, config):
        self.config = config

        self.fm_queue = Queue()

        # PRIORITIES
        self.FLOW_MISS_PRIORITY = 0

        # COOKIES
        self.NO_COOKIE = 0

    def init_fabrc(self):    
        # install table-miss flow entry
        if LOG:
            self.logger.info("INIT: installing flow miss rules")
        match = self.config.parser.OFPMatch()
        actions = [self.config.parser.OFPActionOutput(self.config.ofproto.OFPP_CONTROLLER, self.config.ofproto.OFPCML_NO_BUFFER)]
        instructions = [self.config.parser.OFPInstructionActions(self.config.ofproto.OFPIT_APPLY_ACTIONS, actions)]

        for table in self.config.tables.values():
            mod = self.config.parser.OFPFlowMod(datapath=datapath, 
                                                cookie=self.NO_COOKIE, cookie_mask=self.cookie["mask"], 
                                                table_id=table, 
                                                command=self.config.ofproto.OFPFC_ADD, 
                                                priority=self.FLOW_MISS_PRIORITY, 
                                                match=match, instructions=instructions)
            self.config.datapaths["main"].send_msg(mod)

    def switch_connect(self, dp):
        self.config.datapaths["main"] = dp
        self.config.ofproto = dp.ofproto
        self.config.parser = dp.ofproto_parser

        self.init_fabric()

        if is_ready():
            while not self.fm_queue.empty():
                self.process_flow_mod(self.fm_queue.get())

    def switch_disconnect(self, dp):
        if self.config.datapaths["main"] == dp:
            print "main switch disconnected"
            del self.config.datapaths["main"]

    def process_flow_mod(self, fm):
        if not is_ready():
            self.fm_queue.put(fm)
        else:
            mod = fm.get_flow_mod(self.config)
            self.config.datapaths["main"].send_msg(mod)
           
    def packet_in(self, ev):
        print "PACKET IN"

    def is_ready(self):
        if "main" in self.config.datapaths:
            return True
        return False

class MultiSwitchController(object):
    def __init__(self):
        self.datapaths = {}

        self.config = config

    def switch_connect(self, dp):
        dp_name = self.config.dpid_2_name[dp.id]

        self.config.datapaths = dp

        if self.config.ofproto is not None:
            self.config.ofproto = dp.ofproto
        if self.config.parser is not None:
            self.config.parser = dp.ofproto_parser

        if is_ready():
            self.init_fabric()

            while not self.fm_queue.empty():
                self.process_flow_mod(self.fm_queue.get())

    def switch_disconnect(self, dp):
        
        if dp.id in self.config.dpid_2_name:
            dp_name = self.config.dpid_2_name[dp.id]
            print dp_name + " switch disconnected"
            del self.config.datapaths[dp_name]

    def init_fabric(self):
        # install table-miss flow entry
        if LOG:
            self.logger.info("INIT: installing flow miss rules")
        match = self.config.parser.OFPMatch()
        actions = [self.config.parser.OFPActionOutput(self.config.ofproto.OFPP_CONTROLLER, self.config.ofproto.OFPCML_NO_BUFFER)]

        if self.config.ofv  == "1.3":
            instructions = [self.config.parser.OFPInstructionActions(self.config.ofproto.OFPIT_APPLY_ACTIONS, actions)]

        for table in self.config.tables.values():
            if self.config.ofv  == "1.3":
                mod = self.config.parser.OFPFlowMod(datapath=datapath, 
                                                    cookie=self.NO_COOKIE, cookie_mask=self.cookie["mask"], 
                                                    command=self.config.ofproto.OFPFC_ADD, 
                                                    priority=self.FLOW_MISS_PRIORITY, 
                                                    match=match, instructions=instructions)
            else:
                mod = self.config.parser.OFPFlowMod(datapath=datapath, 
                                                    cookie=self.NO_COOKIE, 
                                                    command=self.config.ofproto.OFPFC_ADD, 
                                                    priority=self.FLOW_MISS_PRIORITY, 
                                                    match=match, actions=actions)
            self.config.datapaths["main"].send_msg(mod)

    def process_flow_mod(self, fm):
        if not is_ready():
            self.fm_queue.put(fm)
        else:
            mod = fm.get_flow_mod(self.config)
            self.config.datapaths[fm.get_dst_dp()].send_msg(mod)

    def packet_in(self, ev):
        print "PACKET IN"

    def is_ready(self):
        if "main" in self.datapaths and "inbound" in self.datapaths and "outbound" in self.datapaths:
            return True
        return False
