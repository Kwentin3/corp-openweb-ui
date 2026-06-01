# DNS Requirements

## DNS Model

Wildcard DNS is not required for Hermes Corporate v1.

The stand requires six explicit A records. All records must point to the public IPv4 address of the new VPS.

## Node Domains

- `node1.example.com -> VPS_PUBLIC_IP`
- `node2.example.com -> VPS_PUBLIC_IP`
- `node3.example.com -> VPS_PUBLIC_IP`

## Auth Domains

- `auth-node1.example.com -> VPS_PUBLIC_IP`
- `auth-node2.example.com -> VPS_PUBLIC_IP`
- `auth-node3.example.com -> VPS_PUBLIC_IP`

## Placeholder Domain

`example.com` is only a placeholder. Replace it after the real domain is approved.
