# Subnet Allocation and Network Access Control (NACL) Analysis

## 1. Subnet Allocation Working and Calculations

**Base IP Address Block:** `10.20.0.0/16`  
- Available address space: $2^{32 - 16} = 2^{16} = 65,536$ total IP addresses.
- Allocation rule: Allocate from largest requirement to smallest, starting at `10.20.0.0`, contiguous placement, using the smallest prefix satisfying $2^{(32 - \text{prefix})} - 2 \ge \text{Hosts Needed}$.

---

### Step-by-Step Derivation

#### Subnet 1: `app` Subnet
- **Hosts Needed:** 1,000 hosts
- **Capacity Requirement:** $2^h - 2 \ge 1,000 \implies h = 10 \implies 2^{10} - 2 = 1,024 - 2 = 1,022$ usable hosts.
- **Prefix Length:** $32 - 10 = \mathbf{/22}$
- **Subnet Mask:** `255.255.252.0`
- **Network Address:** `10.20.0.0/22`
- **Address Span:** 1,024 addresses (`10.20.0.0` to `10.20.3.255`)
- **Usable Host Range:** `10.20.0.1` – `10.20.3.254`
- **Broadcast Address:** `10.20.3.255`
- **Usable Hosts:** 1,022
- **Next Available Address:** `10.20.4.0`

#### Subnet 2: `public` Subnet (Load Balancer Tier)
- **Hosts Needed:** 250 hosts
- **Capacity Requirement:** $2^h - 2 \ge 250 \implies h = 8 \implies 2^8 - 2 = 256 - 2 = 254$ usable hosts.
- **Prefix Length:** $32 - 8 = \mathbf{/24}$
- **Subnet Mask:** `255.255.255.0`
- **Network Address:** `10.20.4.0/24`
- **Address Span:** 256 addresses (`10.20.4.0` to `10.20.4.255`)
- **Usable Host Range:** `10.20.4.1` – `10.20.4.254`
- **Broadcast Address:** `10.20.4.255`
- **Usable Hosts:** 254
- **Next Available Address:** `10.20.5.0`

#### Subnet 3: `data` Subnet (SeaweedFS / Storage Tier)
- **Hosts Needed:** 100 hosts
- **Capacity Requirement:** $2^h - 2 \ge 100 \implies h = 7 \implies 2^7 - 2 = 128 - 2 = 126$ usable hosts.
- **Prefix Length:** $32 - 7 = \mathbf{/25}$
- **Subnet Mask:** `255.255.255.128`
- **Network Address:** `10.20.5.0/25`
- **Address Span:** 128 addresses (`10.20.5.0` to `10.20.5.127`)
- **Usable Host Range:** `10.20.5.1` – `10.20.5.126`
- **Broadcast Address:** `10.20.5.127`
- **Usable Hosts:** 126
- **Next Available Address:** `10.20.5.128`

#### Subnet 4: `management` Subnet (Bastion / Admin Tier)
- **Hosts Needed:** 20 hosts
- **Capacity Requirement:** $2^h - 2 \ge 20 \implies h = 5 \implies 2^5 - 2 = 32 - 2 = 30$ usable hosts.
- **Prefix Length:** $32 - 5 = \mathbf{/27}$
- **Subnet Mask:** `255.255.255.224`
- **Network Address:** `10.20.5.128/27`
- **Address Span:** 32 addresses (`10.20.5.128` to `10.20.5.159`)
- **Usable Host Range:** `10.20.5.129` – `10.20.5.158`
- **Broadcast Address:** `10.20.5.159`
- **Usable Hosts:** 30
- **Next Available Address:** `10.20.5.160` (remaining space in `10.20.0.0/16` is reserved for future growth)

---

## 2. Subnet Allocation Table

| Subnet Name | Hosts Needed | Network Address | Prefix Length | Usable Host Range | Broadcast Address | Number of Usable Hosts |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **app** | 1,000 | `10.20.0.0` | `/22` | `10.20.0.1` – `10.20.3.254` | `10.20.3.255` | 1,022 |
| **public** | 250 | `10.20.4.0` | `/24` | `10.20.4.1` – `10.20.4.254` | `10.20.4.255` | 254 |
| **data** | 100 | `10.20.5.0` | `/25` | `10.20.5.1` – `10.20.5.126` | `10.20.5.127` | 126 |
| **management** | 20 | `10.20.5.128` | `/27` | `10.20.5.129` – `10.20.5.158` | `10.20.5.159` | 30 |

---

## 3. Stateless Network Access Control List (NACL) Reasoning

### Why a Stateless NACL Requires Separate Rules for Reply Traffic
Unlike stateful firewalls or security groups that maintain a connection state table (automatically permitting return traffic for established sessions regardless of inbound/outbound rules), a Network Access Control List (NACL) is completely **stateless**. Every single packet traveling across a subnet boundary is evaluated independently in isolation:
1. When external clients initiate HTTP/HTTPS requests to the public subnet load balancer, the inbound packets match rules permitting destination ports 80/443.
2. When the load balancer replies back to the client, the outbound response packet has a source port of 80/443 and a destination port in the client's ephemeral port range (`1024`–`65535`). Because the NACL has no concept of an existing "session", an explicit **outbound rule** must exist to allow TCP traffic to destination ports `1024`–`65535`.
3. Similarly, when the load balancer forwards requests to backend application pods on port 8000 (outbound rule), the response packet sent from the application pod back to the load balancer arrives with destination port set to the load balancer's ephemeral port. Hence, an explicit **inbound rule** is required on the public subnet to permit TCP traffic from the `app` subnet (`10.20.0.0/22`) arriving on ports `1024`–`65535`. Without these complementary return rules, two-way TCP handshakes immediately fail.

### Why Rule Order Matters for the `198.51.100.0/24` Abusive Block
NACL rules are evaluated sequentially in ascending order of their rule numbers, and evaluation terminates upon the **first matching rule** ("first match wins"). If no rule matches, the default implicit deny rule rejects the packet.

The requirement dictates that all traffic from `198.51.100.0/24` must be blocked, even on web ports 80 and 443:
- By assigning the deny rule a **lower rule number** (e.g., Rule 10) than the general web traffic allow rules (Rules 20 and 30 for ports 80 and 443 with CIDR `0.0.0.0/0`), any inbound packet from `198.51.100.0/24` matches Rule 10 first and is promptly dropped.
- If the deny rule were placed with a higher rule number than the allow rules (for example, placing allow rules at 100/200 and the deny rule at 300), an inbound packet from `198.51.100.9` destined for port 80/443 would match the broader `0.0.0.0/0` allow rule first and be admitted into the subnet, completely invalidating the security policy.
