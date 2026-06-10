from mininet.node import Node
from mininet.node import OVSSwitch


class SwitchL3(OVSSwitch):
    def __init__(self, name, failMode='standalone', **params):
        # Without a controller, OVS switches default to fail_mode='secure'
        # and drop all traffic. 'standalone' makes them behave like normal
        # learning switches, which is what every per-VLAN switch needs here.
        super(SwitchL3, self).__init__(name, failMode=failMode, **params)

    def config(self, **params):
        super(SwitchL3, self).config(**params)
        # Ensure root namespace routes cleanly between SVIs and transit segments
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')
        self.cmd('iptables -P FORWARD ACCEPT')
        self.cmd('iptables -F FORWARD')


class Router(Node):
    def config(self, **params):
        super(Router, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.cmd('sysctl -w net.ipv4.conf.all.rp_filter=0')
        self.cmd('sysctl -w net.ipv4.conf.default.rp_filter=0')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(Router, self).terminate()


class DNSDHCPServer(Node):
    """A host that runs dnsmasq to provide DHCP + DNS service for a site.

    It is a plain (non-forwarding) host with one interface per VLAN it
    serves. dnsmasq is started with an explicit config file so each site
    can ship its own dhcp-range/DNS-forwarding rules.
    """

    def config(self, **params):
        super(DNSDHCPServer, self).config(**params)
        # This node only serves DHCP/DNS, it does not route between subnets
        self.cmd('sysctl -w net.ipv4.ip_forward=0')

    def start_dnsmasq(self, conf_file):
        pidfile = '/tmp/%s-dnsmasq.pid' % self.name
        leasefile = '/tmp/%s-dnsmasq.leases' % self.name
        # -k: keep dnsmasq in the foreground (we background it ourselves with &)
        self.cmd('dnsmasq -k --conf-file=%s --pid-file=%s '
                 '--dhcp-leasefile=%s > /tmp/%s-dnsmasq.log 2>&1 &'
                 % (conf_file, pidfile, leasefile, self.name))

    def stop_dnsmasq(self):
        pidfile = '/tmp/%s-dnsmasq.pid' % self.name
        self.cmd('kill $(cat %s) 2>/dev/null' % pidfile)
        self.cmd('rm -f %s' % pidfile)

    def terminate(self):
        self.stop_dnsmasq()
        super(DNSDHCPServer, self).terminate()
