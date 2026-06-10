# Network Topology — Mininet Implementation

## 1. Overview

The network is made up of **three sites** connected over a WAN:

- **HQ (Headquarters)** — acts as the WAN **hub** and as the central DNS
  fallback resolver for the whole organization. Hosts the Servers VLAN
  (Database, File Server, Web Server, DNS/DHCP server) plus Empleados,
  Visitantes and Surveillance SR VLANs.
- **Site 1** — a branch with Sales, Management, Guests, Surveillance,
  Kitchen and VoIP VLANs.
- **Site 2** — a branch with Sales, Management, Guests, Surveillance and
  VoIP VLANs.

Each site is built the same way:

- **One `Router` node** (`rHQ`, `rS1`, `rS2`) with one interface per local
  VLAN, configured with that VLAN's gateway IP. The `Router` class enables
  `ip_forward`, so the router does inter-VLAN routing for everything
  directly connected to it.
- **One OVS L2 switch per VLAN** (e.g. `swS1sl` for Site 1 Sales). End hosts
  and the router/DNS-server interfaces for that VLAN connect to this switch.
- **One DHCP/DNS server per site** (`hHQdns`, `hS1dns`, `hS2dns`), running
  `dnsmasq`. It has **one extra interface into every VLAN it serves**, so it
  can hand out leases and answer DNS queries on each subnet.
- **End hosts** representing the devices in each VLAN (sales PCs, cameras,
  phones, kitchen display, employees, guests, etc.), all configured via DHCP.

## 2. Topology Diagram

```
                         WAN (hub-and-spoke through HQ)

   Site 1 (rS1) ====== 10.0.20.32/30 ====== HQ (rHQ) ====== 10.0.20.36/30 ====== Site 2 (rS2)
   .34                                   .33    .37                                   .38
     |                                     |                                            |
  6 VLAN switches                     4 VLAN switches                            5 VLAN switches
  (Sales, Mgmt, Guests,           (Servers, Empleados,                      (Sales, Mgmt, Guests,
   Surveillance, Kitchen,           Visitantes, Surv. SR)                     Surveillance, VoIP)
   VoIP)
     |                                     |                                            |
  hS1dns (1 leg per VLAN)             hHQdns (1 leg per VLAN)                    hS2dns (1 leg per VLAN)
```

- The 2 unused `/30`s (`10.0.20.40/30`, `10.0.20.44/30`) are **reserved** for
  a future redundant SD-WAN path or additional site, and are not wired up.

## 3. IP / VLAN Address Plan

### Site 1 (`rS1`, WAN: 10.0.20.34/30, peer = HQ 10.0.20.33)

| VLAN | Area | Subnet | Gateway | DHCP Pool | DNS/DHCP host |
|---|---|---|---|---|---|
| 10 | Sales | 10.0.10.0/25 | 10.0.10.1 | .10–.120 | 10.0.10.2 |
| 20 | Management | 10.0.10.128/25 | 10.0.10.129 | .140–.250 | 10.0.10.130 |
| 30 | Guests | 10.0.11.0/24 | 10.0.11.1 | .10–.250 | 10.0.11.2 |
| 40 | Surveillance | 10.0.12.0/24 | 10.0.12.1 | .10–.250 | 10.0.12.2 |
| 50 | Kitchen | 10.0.13.0/27 | 10.0.13.1 | .10–.30 | 10.0.13.2 |
| 60 | VoIP | 10.0.13.64/26 | 10.0.13.65 | .70–.126 | 10.0.13.66 |

### Site 2 (`rS2`, WAN: 10.0.20.38/30, peer = HQ 10.0.20.37)

| VLAN | Area | Subnet | Gateway | DHCP Pool | DNS/DHCP host |
|---|---|---|---|---|---|
| 10 | Sales | 10.0.13.128/25 | 10.0.13.129 | .140–.250 | 10.0.13.130 |
| 20 | Management | 10.0.14.0/25 | 10.0.14.1 | .10–.120 | 10.0.14.2 |
| 30 | Guests | 10.0.15.0/24 | 10.0.15.1 | .10–.250 | 10.0.15.2 |
| 40 | Surveillance | 10.0.16.0/24 | 10.0.16.1 | .10–.250 | 10.0.16.2 |
| 50 | VoIP | 10.0.17.0/26 | 10.0.17.1 | .10–.60 | 10.0.17.2 |

### HQ (`rHQ`, WAN: 10.0.20.33/30 to Site1, 10.0.20.37/30 to Site2)

| VLAN | Area | Subnet | Gateway | Notes |
|---|---|---|---|---|
| 80 | Servers | 10.0.17.64/26 | 10.0.17.65 | hHQdb .66, hHQfile .67, hHQweb .68, hHQdns .69 (all static) |
| 50 | Empleados | 10.0.18.0/24 | 10.0.18.1 | DHCP .10–.250, DNS server 10.0.18.2 |
| 60 | Visitantes | 10.0.19.0/24 | 10.0.19.1 | DHCP .10–.250, DNS server 10.0.19.2 |
| 70 | Surveillance SR | 10.0.20.0/27 | 10.0.20.1 | DHCP .5–.25, DNS server 10.0.20.2 |

### WAN Links

| Link | Subnet | HQ side | Branch side |
|---|---|---|---|
| HQ ↔ Site 1 | 10.0.20.32/30 | 10.0.20.33 (rHQ) | 10.0.20.34 (rS1) |
| HQ ↔ Site 2 | 10.0.20.36/30 | 10.0.20.37 (rHQ) | 10.0.20.38 (rS2) |
| *(reserved)* | 10.0.20.40/30 | — | — |
| *(reserved)* | 10.0.20.44/30 | — | — |

## 4. Why it works — Routing

The WAN is **hub-and-spoke**: HQ is the only node both branches talk to
directly.

- `rS1` and `rS2` each get a single **default route** pointing at `rHQ`
  (`ip route add default via 10.0.20.33` / `...37`). Anything that isn't on
  one of the site's own VLANs (i.e. anything outside the directly-connected
  subnets) is sent to HQ.
- `rHQ` has **explicit static routes** to every Site-1 subnet via
  `10.0.20.34` and every Site-2 subnet via `10.0.20.38`. It does **not** need
  a default route — HQ already owns the only other networks that exist
  (its own VLANs).
- Because the branch subnets at Site 1 and Site 2 don't overlap (even though
  several of them live inside `10.0.13.0/24`, they use disjoint `/25`, `/26`
  and `/27` blocks), HQ's per-subnet routes never conflict and the kernel's
  longest-prefix-match always picks the right next hop.
- Site1 ↔ Site2 traffic transits HQ: `Site1 host -> rS1 (default) -> rHQ
  (explicit route to Site2 subnet) -> rS2 (directly connected) -> Site2 host`.
- Inter-VLAN traffic *within* a site never touches the WAN: every VLAN
  gateway is a directly-connected interface on that site's router, so the
  kernel routes between them automatically (enabled by `Router.config()`
  setting `net.ipv4.ip_forward=1`).

## 5. Why it works — DHCP

Each site's `dnsmasq` instance (`hS1dns`, `hS2dns`, `hHQdns`) has **one NIC
per VLAN** it serves, each configured with a static IP from that VLAN's
range. `dnsmasq`:

- Listens only on `lo` + those NICs (`bind-interfaces`).
- Has one `dhcp-range=set:<tag>,...` per VLAN — dnsmasq automatically matches
  each range to the interface whose subnet contains it.
- Uses `dhcp-option=tag:<tag>,3,<gateway>` (router) and
  `dhcp-option=tag:<tag>,6,<dns-ip>` (DNS server = the dnsmasq host's own IP
  on that VLAN) so every VLAN gets the right gateway/DNS without a single
  global setting.
- `dhcp-authoritative` lets it answer immediately in this isolated lab
  network (no other DHCP servers to defer to).

End hosts run `dhclient -nw <intf>` once their dnsmasq is up, and receive an
address, gateway and DNS server appropriate to their VLAN.

HQ's `hHQdns` only serves DHCP for **Empleados / Visitantes / Surveillance
SR** — the Servers VLAN is fully static (db/files/web/dns all have fixed
IPs), so `hHQdns-eth0` (its leg into the Servers VLAN) is listed for DNS only
(no matching `dhcp-range`).

## 6. Why it works — DNS hierarchy

DNS is split into three local zones, each served by that site's `dnsmasq`,
with HQ acting as the **central fallback**:

- `site1.local` — authoritative on `hS1dns` (10.0.10.2)
- `site2.local` — authoritative on `hS2dns` (10.0.13.130)
- `hq.local` — authoritative on `hHQdns` (10.0.17.69), with static records
  for `db.hq.local` (10.0.17.66), `files.hq.local` (10.0.17.67),
  `web.hq.local` (10.0.17.68), `dns.hq.local` (10.0.17.69).

Forwarding rules (`server=/zone/ip` in each `dnsmasq` config) tie this
together:

- Site 1 and Site 2 each forward `hq.local`, the *other* site's zone, **and**
  a catch-all (`server=10.0.17.69`) to HQ.
- HQ forwards `site1.local` → `10.0.10.2` and `site2.local` → `10.0.13.130`.

So a query for `web.hq.local` made by a Site 1 host goes:
`hS1dns` (not authoritative for `hq.local`) → forwards to `hHQdns`
(10.0.17.69) → answered from its static `address=` record. The reverse path
(an HQ host resolving `dns.site2.local`) goes through the same forwarding
chain in the opposite direction. Routing works for these forwarded queries
because of the WAN routing described above (e.g. `hS1dns` → `rS1` →
default route → `rHQ` → directly connected Servers VLAN).

Static-IP nodes (the HQ servers, both sites' DNS hosts, and the three
routers) get `/etc/resolv.conf` **bind-mounted** from
`site_1/resolv.conf` / `site_2/resolv.conf` (HQ's resolv.conf is generated at
runtime in `site_hq.py` since there's no `site_hq/` folder). Each Mininet
host runs in its own mount namespace (`mnexec -n`), so this bind mount is
private to that host and doesn't affect the rest of the system.

## 7. File Layout

```
base_nodes.py     - Router, SwitchL3, DNSDHCPServer node classes
site_hq.py        - SiteHQ: builds/configures HQ (router, 4 VLANs, dnsmasq)
site_1.py         - SiteOne: builds/configures Site 1 (router, 6 VLANs, dnsmasq)
site_2.py         - SiteTwo: builds/configures Site 2 (router, 5 VLANs, dnsmasq)
wan.py            - Builds the full Mininet topology, wires the WAN links,
                    starts the network, runs the CLI, and tears everything down
site_1/
  site.conf       - dnsmasq config for hS1dns (DHCP ranges + DNS zone + forwarders)
  resolv.conf     - resolv.conf for Site 1's static hosts (hS1dns, rS1)
site_2/
  site.conf       - dnsmasq config for hS2dns
  resolv.conf     - resolv.conf for Site 2's static hosts (hS2dns, rS2)
```

`base_nodes.py` classes:

- **`Router(Node)`** — enables `ip_forward` and disables `rp_filter`, used
  for `rHQ`, `rS1`, `rS2`.
- **`SwitchL3(OVSSwitch)`** — provided abstraction for an L3-capable switch
  (kept for completeness/future use); the per-VLAN switches in this design
  are plain L2 switches.
- **`DNSDHCPServer(Node)`** — a host that wraps starting/stopping `dnsmasq`
  with a given config file (`start_dnsmasq()` / `stop_dnsmasq()`), used for
  `hHQdns`, `hS1dns`, `hS2dns`.

## 8. Running the Network

Mininet needs root privileges (it manipulates network namespaces and OVS):

```bash
cd proyecto-final
sudo python3 wan.py
```

You should see Mininet's startup log and end up at the `mininet>` prompt.

## 9. Testing Guide

All commands below are typed at the `mininet>` prompt.

### 9.1 Basic connectivity

```
pingall
```
Every host should be reachable — intra-VLAN, cross-VLAN within a site (via
its router), and cross-site (via HQ).

Targeted checks:
```
hS1sl1 ping -c2 hS1gst1     # cross-VLAN, Site 1
hS1sl1 ping -c2 hS2sl1      # cross-site, via HQ
hHQemp1 ping -c2 hHQdb      # HQ employee -> HQ server
```

### 9.2 DHCP

```
hS1sl1 ip addr show hS1sl1-eth0
```
Expect an address in `10.0.10.10–120/25` with default route via `10.0.10.1`.

```
hS2mg1 ip addr show hS2mg1-eth0
hHQcam1 ip addr show hHQcam1-eth0
```
Expect `10.0.14.x/25` (gw 10.0.14.1) and `10.0.20.x/27` (gw 10.0.20.1)
respectively.

### 9.3 DNS resolution / hierarchy

```
hS1sl1 dig +short db.hq.local        # Site1 -> forwarded to HQ -> 10.0.17.66
hS1sl1 dig +short dns.site2.local    # Site1 -> HQ -> Site2 -> 10.0.13.130
hHQemp1 dig +short dns.site1.local   # HQ -> Site1 -> 10.0.10.2
hS2sl1 dig +short web.hq.local       # Site2 -> HQ -> 10.0.17.68
```

### 9.4 Routing tables

```
rS1 ip route          # default via 10.0.20.33
rS2 ip route          # default via 10.0.20.37
rHQ ip route          # explicit /25,/26,/27,/24 routes to both branches
```

### 9.5 Service status

```
hS1dns ps aux | grep dnsmasq
hHQdns cat /tmp/hHQdns-dnsmasq.log
```

## 10. Exiting / Cleanup

```
exit
```

`wan.py` then automatically, for each site:
- kills the `dhclient` processes and releases leases on every DHCP client,
- stops the site's `dnsmasq` (via its pidfile),
- unmounts the bind-mounted `/etc/resolv.conf` on static hosts,

before calling `net.stop()`. If a previous run was killed abnormally and
left `dnsmasq` processes or mounts behind, run:

```bash
sudo mn -c
sudo pkill dnsmasq
```
