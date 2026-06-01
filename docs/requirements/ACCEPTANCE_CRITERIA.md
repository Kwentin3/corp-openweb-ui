# Acceptance Criteria

Hermes Corporate v1 is accepted when all criteria below are satisfied in the target demo environment.

- `node1`, `node2` and `node3` are reachable over HTTPS.
- Each node is protected by authorization.
- Each node uses its own Authelia instance.
- A session for one node does not grant access to another node.
- Data does not mix across nodes.
- Logs do not mix across nodes.
- Secrets do not mix across nodes.
- Restarting one node does not break other nodes.
- Stopping one node does not break other nodes.
- After VPS reboot, services return to an operational state.
- Only 80/443 are open on the public perimeter.
- Web GUI has no direct public access outside Traefik.
- The repository contains no real secrets.
