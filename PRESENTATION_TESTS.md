# Presentation Test Script

All commands are run at the `mininet>` prompt after `sudo python3 wan.py`.

## 1. Full Network Connectivity

```
pingall 2
```
**Description:** Pings every host pair in the topology with a 2-second
timeout per probe (`-W 2`), so isolated/dropped traffic doesn't stall the
sweep. Confirms overall reachability: all VLANs, sites, and the WAN hub
respond as expected, **except** the Guest/Visitor and Surveillance VLANs,
which are intentionally firewalled off (see Sections 3.2 and 4.2, tests
B1–B5).

---

## 2. Intra-VLAN Communication

Two hosts on the **same VLAN/subnet**, reachable purely via L2 switching
(no router involved).

```
hS1sl1 ping -c3 hS1sl2
```
**Description:** Site 1 Sales — both hosts sit on `swS1sl` in
`10.0.10.0/25`. Traffic never leaves the switch. **Expected: success.**

```
hS2sl1 ping -c3 hS2sl2
```
**Description:** Site 2 Sales — same idea, `10.0.13.128/25` on `swS2sl`.
**Expected: success.**

---

## 3. Inter-VLAN Communication

Hosts on **different VLANs**, requiring the site router (`rS1`/`rS2`/`rHQ`)
to route between them — and where applicable, the firewall to allow or
block it.

### 3.1 Allowed (routed)

```
hS1sl1 ping -c3 hS1mg1
```
**Description:** Site 1 Sales (`10.0.10.0/25`) → Management
(`10.0.10.128/25`), via `rS1`. Demonstrates normal inter-VLAN routing.
**Expected: success.**

```
hS1sl1 ping -c3 hS2sl1.site2.local
```
**Description:** Site 1 Sales → Site 2 Sales, hub-and-spoke through HQ
(`rS1` → `rHQ` → `rS2`). Note the FQDN — DHCP-issued search domains are
per-site, so the destination must be fully qualified. **Expected: success.**

### 3.2 Denied (firewall isolation)

These pings are blocked by `iptables` `FORWARD` rules added on the site
routers in `site_1.py` / `site_hq.py` (default `FORWARD` policy stays
`ACCEPT`; only these specific source/destination pairs are dropped).

| Test | Source → Destination               | Command                               | Description                                                       | Expected Result |
| ---- | ----------------------------------- | -------------------------------------- | ------------------------------------------------------------------ | ---------------- |
| B1   | Site 1 Guest → Site 1 Sales         | `hS1gst1 ping -c3 hS1sl1`              | Proves Guest Wi-Fi isolation from POS/Sales systems.               | Failed ping      |
| B2   | Site 1 Guest → Site 1 Management    | `hS1gst1 ping -c3 hS1mg1`              | Proves Guest Wi-Fi cannot reach management systems.                | Failed ping      |
| B3   | Site 1 Surveillance → Site 1 Sales  | `hS1cam1 ping -c3 hS1sl1`              | Confirms camera network isolation from POS/Sales.                  | Failed ping      |
| B4   | Site 1 Surveillance → Site 2 Sales  | `hS1cam1 ping -c3 hS2sl1.site2.local`  | Proves Surveillance cannot leave the local site through the WAN.   | Failed ping      |

> **B4 note:** DNS still resolves the FQDN (handled by `hS1dns` on its
> Sales-side interface), but the ICMP packet itself is dropped at `rS1`
> before it can exit over the WAN link `s1-hq` — proving Surveillance
> traffic cannot leave the local site.

---

## 4. HQ-Internal Communication

### 4.1 Allowed (routed)

```
hHQemp1 ping -c3 hHQdb
```
**Description:** HQ Empleados (`10.0.18.0/24`) → HQ Servers VLAN
(`10.0.17.64/26`, database server). Demonstrates that HQ employees can
reach core internal services. **Expected: success.**

### 4.2 Denied (firewall isolation)

| Test | Source → Destination     | Command                    | Description                                                  | Expected Result |
| ---- | ------------------------- | --------------------------- | ----------------------------------------------------------- | ---------------- |
| B5   | HQ Guest → HQ Employee    | `hHQgst1 ping -c3 hHQemp1`  | Confirms HQ visitors cannot access the HQ employee network. | Failed ping      |

This is enforced by an `iptables FORWARD` rule on `rHQ` dropping traffic
from Visitantes (`10.0.19.0/24`) to Empleados (`10.0.18.0/24`).
