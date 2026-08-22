# API Load Test

Requires [k6](https://grafana.com/docs/k6/latest/).

Run against a non-production environment first:

```bash
k6 run \
  -e BASE_URL=http://localhost:8000 \
  -e VUS=5 \
  -e DURATION=30s \
  load-tests/api-smoke.js
```

The script checks the health endpoint and the public privacy-policy endpoint.
Increase `VUS` and `DURATION` only after confirming database and proxy limits.
