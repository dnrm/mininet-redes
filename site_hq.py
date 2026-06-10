import os

from base_nodes import Router, SwitchL3, DNSDHCPServer

# HQ has no dedicated config folder (per the requested layout), so its
# dnsmasq config and resolv.conf are generated at runtime.
TMP_DIR = '/tmp'
HQ_DNSMASQ_CONF = os.path.join(TMP_DIR, 'site_hq-dnsmasq.conf')
HQ_RESOLV_CONF = os.path.join(TMP_DIR, 'site_hq-resolv.conf')

HQ_DNSMASQ_TEMPLATE = """\
# dnsmasq configuration for HQ (hHQdns)
# Provides DHCP for Empleados/Visitantes/Surveillance SR and authoritative
# DNS for hq.local. Also acts as the central fallback resolver for
# site1.local and site2.local.
#
# Interface order MUST match the link order created in site_hq.py:
#   eth0 -> Servers (VLAN 80)        10.0.17.64/26  (DNS only, no DHCP)
#   eth1 -> Empleados (VLAN 50)      10.0.18.0/24
#   eth2 -> Visitantes (VLAN 60)     10.0.19.0/24
#   eth3 -> Surveillance SR (VLAN 70) 10.0.20.0/27

domain-needed
bogus-priv
expand-hosts
domain=hq.local
local=/hq.local/

interface=lo
interface=hHQdns-eth0
interface=hHQdns-eth1
interface=hHQdns-eth2
interface=hHQdns-eth3
bind-interfaces
no-resolv
dhcp-authoritative

# --- VLAN 50: Empleados (10.0.18.0/24, gw 10.0.18.1) ---
dhcp-range=set:empleados,10.0.18.10,10.0.18.250,255.255.255.0,12h
dhcp-option=tag:empleados,3,10.0.18.1
dhcp-option=tag:empleados,6,10.0.18.2

# --- VLAN 60: Visitantes (10.0.19.0/24, gw 10.0.19.1) ---
dhcp-range=set:visitantes,10.0.19.10,10.0.19.250,255.255.255.0,12h
dhcp-option=tag:visitantes,3,10.0.19.1
dhcp-option=tag:visitantes,6,10.0.19.2

# --- VLAN 70: Surveillance SR (10.0.20.0/27, gw 10.0.20.1) ---
dhcp-range=set:surveillance_sr,10.0.20.5,10.0.20.25,255.255.255.224,12h
dhcp-option=tag:surveillance_sr,3,10.0.20.1
dhcp-option=tag:surveillance_sr,6,10.0.20.2

# --- Static records for the HQ servers VLAN ---
address=/db.hq.local/10.0.17.66
address=/files.hq.local/10.0.17.67
address=/web.hq.local/10.0.17.68
address=/dns.hq.local/10.0.17.69

# --- Forward each branch's local zone to its own site DNS server ---
server=/site1.local/10.0.10.2
server=/site2.local/10.0.13.130

log-queries
log-dhcp
"""

HQ_RESOLV_TEMPLATE = """\
# Static resolver configuration for HQ's statically-addressed nodes
# (db/files/web/dns servers and rHQ). HQ's own DNS server is authoritative
# for hq.local and is the root fallback resolver for the whole WAN.
nameserver 10.0.17.69
search hq.local
"""


class SiteHQ:
    """Headquarters: Servers / Empleados / Visitantes / Surveillance SR."""

    # WAN-side addressing for the hub-and-spoke links
    WAN_S1_IP = '10.0.20.33/30'   # towards Site 1 (rS1 = 10.0.20.34)
    WAN_S2_IP = '10.0.20.37/30'   # towards Site 2 (rS2 = 10.0.20.38)
    S1_NEXTHOP = '10.0.20.34'
    S2_NEXTHOP = '10.0.20.38'

    SITE1_SUBNETS = [
        '10.0.10.0/25',   # Sales
        '10.0.10.128/25',  # Management
        '10.0.11.0/24',   # Guests
        '10.0.12.0/24',   # Surveillance
        '10.0.13.0/27',   # Kitchen
        '10.0.13.64/26',  # VoIP
    ]

    SITE2_SUBNETS = [
        '10.0.13.128/25',  # Sales
        '10.0.14.0/25',   # Management
        '10.0.15.0/24',   # Guests
        '10.0.16.0/24',   # Surveillance
        '10.0.17.0/26',   # VoIP
    ]

    def __init__(self):
        self.gateway = None  # rHQ
        self.dns = None      # hHQdns
        self.dhcp_clients = []  # (host, intf) pairs that need `dhclient`

    def build(self, net):
        # --- Router for HQ ---
        self.gateway = net.addHost('rHQ', cls=Router, ip=None)

        # --- VLAN 80: Servers (10.0.17.64/26, gw .65) ---
        swServers = net.addSwitch('swHQsrv', cls=SwitchL3, dpid='1')
        net.addLink(self.gateway, swServers)  # rHQ-eth0
        hHQdb = net.addHost('hHQdb', ip=None)
        hHQfile = net.addHost('hHQfile', ip=None)
        hHQweb = net.addHost('hHQweb', ip=None)
        self.dns = net.addHost('hHQdns', cls=DNSDHCPServer, ip=None)
        net.addLink(hHQdb, swServers)
        net.addLink(hHQfile, swServers)
        net.addLink(hHQweb, swServers)
        net.addLink(self.dns, swServers)      # hHQdns-eth0
        self.servers = (hHQdb, hHQfile, hHQweb)

        # --- VLAN 50: Empleados (10.0.18.0/24, gw .1) ---
        swEmp = net.addSwitch('swHQemp', cls=SwitchL3, dpid='2')
        net.addLink(self.gateway, swEmp)      # rHQ-eth1
        net.addLink(self.dns, swEmp)          # hHQdns-eth1
        hHQemp1 = net.addHost('hHQemp1', ip=None)
        hHQemp2 = net.addHost('hHQemp2', ip=None)
        net.addLink(hHQemp1, swEmp)
        net.addLink(hHQemp2, swEmp)
        self.dhcp_clients += [(hHQemp1, 'hHQemp1-eth0'), (hHQemp2, 'hHQemp2-eth0')]

        # --- VLAN 60: Visitantes (10.0.19.0/24, gw .1) ---
        swGst = net.addSwitch('swHQgst', cls=SwitchL3, dpid='3')
        net.addLink(self.gateway, swGst)      # rHQ-eth2
        net.addLink(self.dns, swGst)          # hHQdns-eth2
        hHQgst1 = net.addHost('hHQgst1', ip=None)
        net.addLink(hHQgst1, swGst)
        self.dhcp_clients += [(hHQgst1, 'hHQgst1-eth0')]

        # --- VLAN 70: Surveillance SR (10.0.20.0/27, gw .1) ---
        swCam = net.addSwitch('swHQcam', cls=SwitchL3, dpid='4')
        net.addLink(self.gateway, swCam)      # rHQ-eth3
        net.addLink(self.dns, swCam)          # hHQdns-eth3
        hHQcam1 = net.addHost('hHQcam1', ip=None)
        net.addLink(hHQcam1, swCam)
        self.dhcp_clients += [(hHQcam1, 'hHQcam1-eth0')]

    def config(self, net):
        rHQ = self.gateway
        dns = self.dns
        hHQdb, hHQfile, hHQweb = self.servers

        # --- Router VLAN gateway addresses ---
        rHQ.setIP('10.0.17.65/26', intf='rHQ-eth0')  # Servers
        rHQ.setIP('10.0.18.1/24', intf='rHQ-eth1')   # Empleados
        rHQ.setIP('10.0.19.1/24', intf='rHQ-eth2')   # Visitantes
        rHQ.setIP('10.0.20.1/27', intf='rHQ-eth3')   # Surveillance SR

        # HQ is the WAN hub: explicit routes to every branch subnet
        for subnet in self.SITE1_SUBNETS:
            rHQ.cmd('ip route add %s via %s' % (subnet, self.S1_NEXTHOP))
        for subnet in self.SITE2_SUBNETS:
            rHQ.cmd('ip route add %s via %s' % (subnet, self.S2_NEXTHOP))

        # --- Static servers in the Servers VLAN ---
        hHQdb.setIP('10.0.17.66/26')
        hHQdb.setDefaultRoute('via 10.0.17.65')
        hHQfile.setIP('10.0.17.67/26')
        hHQfile.setDefaultRoute('via 10.0.17.65')
        hHQweb.setIP('10.0.17.68/26')
        hHQweb.setDefaultRoute('via 10.0.17.65')

        # --- DHCP/DNS server addresses (one per VLAN it serves) ---
        dns.setIP('10.0.17.69/26', intf='hHQdns-eth0')  # Servers
        dns.setIP('10.0.18.2/24', intf='hHQdns-eth1')   # Empleados
        dns.setIP('10.0.19.2/24', intf='hHQdns-eth2')   # Visitantes
        dns.setIP('10.0.20.2/27', intf='hHQdns-eth3')   # Surveillance SR
        dns.setDefaultRoute('via 10.0.17.65')

        # --- Generate HQ's dnsmasq config + resolv.conf at runtime ---
        with open(HQ_DNSMASQ_CONF, 'w') as f:
            f.write(HQ_DNSMASQ_TEMPLATE)
        with open(HQ_RESOLV_CONF, 'w') as f:
            f.write(HQ_RESOLV_TEMPLATE)

        # --- Static resolv.conf for static-addressed nodes ---
        for node in (hHQdb, hHQfile, hHQweb, dns, rHQ):
            node.cmd('umount /etc/resolv.conf 2>/dev/null')
            node.cmd('touch /etc/resolv.conf')
            node.cmd('mount --bind %s /etc/resolv.conf' % HQ_RESOLV_CONF)

        # --- Start DHCP/DNS service ---
        dns.start_dnsmasq(HQ_DNSMASQ_CONF)

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

        hHQdb, hHQfile, hHQweb = self.servers
        for node in (hHQdb, hHQfile, hHQweb, self.dns, self.gateway):
            node.cmd('umount /etc/resolv.conf 2>/dev/null')
