from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel

from site_hq import SiteHQ
from site_1 import SiteOne
from site_2 import SiteTwo


def deploy_wan_network():
    net = Mininet(controller=None,
                   switch=OVSSwitch,
                   link=TCLink,
                   autoSetMacs=True)

    hq = SiteHQ()
    hq.build(net)

    site1 = SiteOne()
    site1.build(net)

    site2 = SiteTwo()
    site2.build(net)

    # --- Hub-and-spoke WAN links (HQ is the hub) ---
    # Link 1: 10.0.20.32/30 -> rHQ <-> rS1
    net.addLink(hq.gateway, site1.gateway,
                intfName1='hq-s1', intfName2='s1-hq', cls=TCLink)
    # Link 2: 10.0.20.36/30 -> rHQ <-> rS2
    net.addLink(hq.gateway, site2.gateway,
                intfName1='hq-s2', intfName2='s2-hq', cls=TCLink)

    net.start()

    # --- Assign WAN link addresses ---
    hq.gateway.setIP(SiteHQ.WAN_S1_IP, intf='hq-s1')
    site1.gateway.setIP(site1.WAN_LOCAL_IP, intf='s1-hq')

    hq.gateway.setIP(SiteHQ.WAN_S2_IP, intf='hq-s2')
    site2.gateway.setIP(site2.WAN_LOCAL_IP, intf='s2-hq')

    # --- Configure each site (LAN addressing, routing, DHCP/DNS) ---
    # HQ first so its DNS/DHCP service is up before the branches start
    # forwarding queries to it.
    hq.config(net)
    site1.config(net)
    site2.config(net)

    CLI(net)

    for site in (site1, site2, hq):
        site.cleanup(net)

    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    deploy_wan_network()
