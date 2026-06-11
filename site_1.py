import os

from base_nodes import Router, SwitchL3, DNSDHCPServer

SITE_DIR = os.path.dirname(os.path.abspath(__file__))


class SiteOne:
    """Site 1: Sales / Management / Guests / Surveillance / Kitchen / VoIP."""

    # WAN-side addressing for the hub-and-spoke link to HQ
    WAN_LOCAL_IP = '10.0.20.34/30'
    WAN_REMOTE_IP = '10.0.20.33'  # rHQ

    def __init__(self):
        self.gateway = None  # rS1
        self.dns = None      # hS1dns
        self.dhcp_clients = []  # (host, intf) pairs that need `dhclient`

    def build(self, net):
        # --- Router for Site 1 ---
        self.gateway = net.addHost('rS1', cls=Router, ip=None)

        # --- DHCP/DNS server for Site 1 ---
        self.dns = net.addHost('hS1dns', cls=DNSDHCPServer, ip=None)

        # --- VLAN 10: Sales (10.0.10.0/25, gw .1) ---
        swSales = net.addSwitch('swS1sl', cls=SwitchL3, dpid='5')
        net.addLink(self.gateway, swSales)   # rS1-eth0
        net.addLink(self.dns, swSales)       # hS1dns-eth0
        hS1sl1 = net.addHost('hS1sl1', ip=None)
        hS1sl2 = net.addHost('hS1sl2', ip=None)
        net.addLink(hS1sl1, swSales)
        net.addLink(hS1sl2, swSales)
        self.dhcp_clients += [(hS1sl1, 'hS1sl1-eth0'), (hS1sl2, 'hS1sl2-eth0')]

        # --- VLAN 20: Management (10.0.10.128/25, gw .129) ---
        swMgmt = net.addSwitch('swS1mg', cls=SwitchL3, dpid='6')
        net.addLink(self.gateway, swMgmt)    # rS1-eth1
        net.addLink(self.dns, swMgmt)        # hS1dns-eth1
        hS1mg1 = net.addHost('hS1mg1', ip=None)
        net.addLink(hS1mg1, swMgmt)
        self.dhcp_clients += [(hS1mg1, 'hS1mg1-eth0')]

        # --- VLAN 30: Guests (10.0.11.0/24, gw .1) ---
        swGuests = net.addSwitch('swS1gst', cls=SwitchL3, dpid='7')
        net.addLink(self.gateway, swGuests)  # rS1-eth2
        net.addLink(self.dns, swGuests)      # hS1dns-eth2
        hS1gst1 = net.addHost('hS1gst1', ip=None)
        net.addLink(hS1gst1, swGuests)
        self.dhcp_clients += [(hS1gst1, 'hS1gst1-eth0')]

        # --- VLAN 40: Surveillance (10.0.12.0/24, gw .1) ---
        swCam = net.addSwitch('swS1cam', cls=SwitchL3, dpid='8')
        net.addLink(self.gateway, swCam)     # rS1-eth3
        net.addLink(self.dns, swCam)         # hS1dns-eth3
        hS1cam1 = net.addHost('hS1cam1', ip=None)
        hS1nvr1 = net.addHost('hS1nvr1', ip=None)
        net.addLink(hS1cam1, swCam)
        net.addLink(hS1nvr1, swCam)
        self.dhcp_clients += [(hS1cam1, 'hS1cam1-eth0'), (hS1nvr1, 'hS1nvr1-eth0')]

        # --- VLAN 50: Kitchen (10.0.13.0/27, gw .1) ---
        swKitchen = net.addSwitch('swS1kit', cls=SwitchL3, dpid='9')
        net.addLink(self.gateway, swKitchen)  # rS1-eth4
        net.addLink(self.dns, swKitchen)      # hS1dns-eth4
        hS1kit1 = net.addHost('hS1kit1', ip=None)
        net.addLink(hS1kit1, swKitchen)
        self.dhcp_clients += [(hS1kit1, 'hS1kit1-eth0')]

        # --- VLAN 60: VoIP (10.0.13.64/26, gw .65) ---
        swVoip = net.addSwitch('swS1vo', cls=SwitchL3, dpid='a')
        net.addLink(self.gateway, swVoip)    # rS1-eth5
        net.addLink(self.dns, swVoip)        # hS1dns-eth5
        hS1ph1 = net.addHost('hS1ph1', ip=None)
        net.addLink(hS1ph1, swVoip)
        self.dhcp_clients += [(hS1ph1, 'hS1ph1-eth0')]

    def config(self, net):
        rS1 = self.gateway
        dns = self.dns

        # --- Router VLAN gateway addresses ---
        rS1.setIP('10.0.10.1/25', intf='rS1-eth0')    # Sales
        rS1.setIP('10.0.10.129/25', intf='rS1-eth1')  # Management
        rS1.setIP('10.0.11.1/24', intf='rS1-eth2')    # Guests
        rS1.setIP('10.0.12.1/24', intf='rS1-eth3')    # Surveillance
        rS1.setIP('10.0.13.1/27', intf='rS1-eth4')    # Kitchen
        rS1.setIP('10.0.13.65/26', intf='rS1-eth5')   # VoIP

        # Hub-and-spoke: everything not local goes to HQ
        rS1.cmd('ip route add default via %s' % self.WAN_REMOTE_IP)

        # --- Firewall: VLAN isolation policy (FORWARD chain, default ACCEPT) ---
        # Guests (10.0.11.0/24) cannot reach Sales or Management (10.0.10.0/24)
        rS1.cmd('iptables -A FORWARD -s 10.0.11.0/24 -d 10.0.10.0/24 -j DROP')
        # Surveillance (10.0.12.0/24) cannot reach Sales (10.0.10.0/25)
        rS1.cmd('iptables -A FORWARD -s 10.0.12.0/24 -d 10.0.10.0/25 -j DROP')
        # Surveillance cannot leave the site over the WAN link
        rS1.cmd('iptables -A FORWARD -s 10.0.12.0/24 -o s1-hq -j DROP')

        # --- DHCP/DNS server addresses (one per VLAN) ---
        dns.setIP('10.0.10.2/25', intf='hS1dns-eth0')    # Sales
        dns.setIP('10.0.10.130/25', intf='hS1dns-eth1')  # Management
        dns.setIP('10.0.11.2/24', intf='hS1dns-eth2')    # Guests
        dns.setIP('10.0.12.2/24', intf='hS1dns-eth3')    # Surveillance
        dns.setIP('10.0.13.2/27', intf='hS1dns-eth4')    # Kitchen
        dns.setIP('10.0.13.66/26', intf='hS1dns-eth5')   # VoIP
        dns.setDefaultRoute('via 10.0.10.1')

        # --- Static resolv.conf for static-addressed nodes (dns + router) ---
        resolv_path = os.path.join(SITE_DIR, 'site_1', 'resolv.conf')
        for node in (dns, rS1):
            node.cmd('umount /etc/resolv.conf 2>/dev/null')
            node.cmd('touch /etc/resolv.conf')
            node.cmd('mount --bind %s /etc/resolv.conf' % resolv_path)

        # --- Start DHCP/DNS service ---
        conf_path = os.path.join(SITE_DIR, 'site_1', 'site.conf')
        dns.start_dnsmasq(conf_path)

        # --- Bring up DHCP clients ---
        for host, intf in self.dhcp_clients:
            host.cmd('ip link set %s up' % intf)
            # Right after net.start() the OVS switches/ports may still be
            # settling, so a single short dhclient attempt can time out.
            # Retry a few times before giving up.
            for attempt in range(3):
                host.cmd('timeout 15 dhclient -1 %s' % intf)
                host.intf(intf).updateIP()
                if host.intf(intf).ip:
                    break

    def cleanup(self, net):
        for host, intf in self.dhcp_clients:
            host.cmd('pkill -f "dhclient.*%s"' % intf)
            host.cmd('dhclient -r %s 2>/dev/null' % intf)

        self.dns.stop_dnsmasq()

        for node in (self.dns, self.gateway):
            node.cmd('umount /etc/resolv.conf 2>/dev/null')
