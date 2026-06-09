# DNS Requirements

## DNS Model

Wildcard DNS is not required for OpenWebUI PRD-0.

The stand requires one explicit A record:

```text
gpt.alpha-soft.ru -> target public IPv4
```

The exact public IPv4 is deployment-specific and must not be committed to Git.

## Checks

Before deploy:

```bash
dig +short gpt.alpha-soft.ru
```

After deploy:

```bash
curl -I http://gpt.alpha-soft.ru
curl -fsSI https://gpt.alpha-soft.ru
```

Expected:

- DNS resolves to the target public IPv4;
- HTTP redirects to HTTPS;
- HTTPS serves OpenWebUI through Traefik with a valid certificate.
