import os

from base_nodes import Router, SwitchL3, DNSDHCPServer

SITE_DIR = os.path.dirname(os.path.abspath(__file__))


class SiteTwo:
    """Site 2: Sales / Management / Guests / Surveillance / VoIP."""

    # WAN-side addressing for the hub-and-spoke link to HQ
    WAN_LOCAL_IP = '10.0.20.38/30'
    WAN_REMOTE_IP = '10.0.20.37'  # rHQ

    def __init__(self):
        self.gateway = None  # rS2
        self.dns = None      # hS2dns
        self.dhcp_clients = []  # (host, intf) pairs that need `dhclient`

    def build(self, net):
        # --- Router for Site 2 ---
        self.gateway = net.addHost('rS2', cls=Router, ip=None)

        # --- DHCP/DNS server for Site 2 ---
        self.dns = net.addHost('hS2dns', cls=DNSDHCPServer, ip=None)

        # --- VLAN 10: Sales (10.0.13.128/25, gw .129) ---
        swSales = net.addSwitch('swS2sl', cls=SwitchL3, dpid='b')
        net.addLink(self.gateway, swSales)   # rS2-eth0
        net.addLink(self.dns, swSales)       # hS2dns-eth0
        hS2sl1 = net.addHost('hS2sl1', ip=None)
        hS2sl2 = net.addHost('hS2sl2', ip=None)
        net.addLink(hS2sl1, swSales)
        net.addLink(hS2sl2, swSales)
        self.dhcp_clients += [(hS2sl1, 'hS2sl1-eth0'), (hS2sl2, 'hS2sl2-eth0')]

        # --- VLAN 20: Management (10.0.14.0/25, gw .1) ---
        swMgmt = net.addSwitch('swS2mg', cls=SwitchL3, dpid='c')
        net.addLink(self.gateway, swMgmt)    # rS2-eth1
        net.addLink(self.dns, swMgmt)        # hS2dns-eth1
        hS2mg1 = net.addHost('hS2mg1', ip=None)
        net.addLink(hS2mg1, swMgmt)
        self.dhcp_clients += [(hS2mg1, 'hS2mg1-eth0')]

        # --- VLAN 30: Guests (10.0.15.0/24, gw .1) ---
        swGuests = net.addSwitch('swS2gst', cls=SwitchL3, dpid='d')
        net.addLink(self.gateway, swGuests)  # rS2-eth2
        net.addLink(self.dns, swGuests)      # hS2dns-eth2
        hS2gst1 = net.addHost('hS2gst1', ip=None)
        net.addLink(hS2gst1, swGuests)
        self.dhcp_clients += [(hS2gst1, 'hS2gst1-eth0')]

        # --- VLAN 40: Surveillance (10.0.16.0/24, gw .1) ---
        swCam = net.addSwitch('swS2cam', cls=SwitchL3, dpid='e')
        net.addLink(self.gateway, swCam)     # rS2-eth3
        net.addLink(self.dns, swCam)         # hS2dns-eth3
        hS2cam1 = net.addHost('hS2cam1', ip=None)
        net.addLink(hS2cam1, swCam)
        self.dhcp_clients += [(hS2cam1, 'hS2cam1-eth0')]

        # --- VLAN 50: VoIP (10.0.17.0/26, gw .1) ---
        swVoip = net.addSwitch('swS2vo', cls=SwitchL3, dpid='f')
        net.addLink(self.gateway, swVoip)    # rS2-eth4
        net.addLink(self.dns, swVoip)        # hS2dns-eth4
        hS2ph1 = net.addHost('hS2ph1', ip=None)
        net.addLink(hS2ph1, swVoip)
        self.dhcp_clients += [(hS2ph1, 'hS2ph1-eth0')]

    def config(self, net):
        rS2 = self.gateway
        dns = self.dns

        # --- Router VLAN gateway addresses ---
        rS2.setIP('10.0.13.129/25', intf='rS2-eth0')  # Sales
        rS2.setIP('10.0.14.1/25', intf='rS2-eth1')    # Management
        rS2.setIP('10.0.15.1/24', intf='rS2-eth2')    # Guests
        rS2.setIP('10.0.16.1/24', intf='rS2-eth3')    # Surveillance
        rS2.setIP('10.0.17.1/26', intf='rS2-eth4')    # VoIP

        # Hub-and-spoke: everything not local goes to HQ
        rS2.cmd('ip route add default via %s' % self.WAN_REMOTE_IP)

        # --- DHCP/DNS server addresses (one per VLAN) ---
        dns.setIP('10.0.13.130/25', intf='hS2dns-eth0')  # Sales
        dns.setIP('10.0.14.2/25', intf='hS2dns-eth1')    # Management
        dns.setIP('10.0.15.2/24', intf='hS2dns-eth2')    # Guests
        dns.setIP('10.0.16.2/24', intf='hS2dns-eth3')    # Surveillance
        dns.setIP('10.0.17.2/26', intf='hS2dns-eth4')    # VoIP
        dns.setDefaultRoute('via 10.0.13.129')

        # --- Static resolv.conf for static-addressed nodes (dns + router) ---
        resolv_path = os.path.join(SITE_DIR, 'site_2', 'resolv.conf')
        for node in (dns, rS2):
            node.cmd('umount /etc/resolv.conf 2>/dev/null')
            node.cmd('touch /etc/resolv.conf')
            node.cmd('mount --bind %s /etc/resolv.conf' % resolv_path)

        # --- Start DHCP/DNS service ---
        conf_path = os.path.join(SITE_DIR, 'site_2', 'site.conf')
        dns.start_dnsmasq(conf_path)

        # --- Bring up DHCP clients ---
        for host, intf in self.dhcp_clients:
            host.cmd('ip link set %s up' % intf)
            host.cmd('timeout 10 dhclient -1 %s' % intf)
            # Refresh Mininet's cached IP so commands like pingAll work
            host.intf(intf).updateIP()

    def cleanup(self, net):
        for host, intf in self.dhcp_clients:
            host.cmd('pkill -f "dhclient.*%s"' % intf)
            host.cmd('dhclient -r %s 2>/dev/null' % intf)

        self.dns.stop_dnsmasq()

        for node in (self.dns, self.gateway):
            node.cmd('umount /etc/resolv.conf 2>/dev/null')
