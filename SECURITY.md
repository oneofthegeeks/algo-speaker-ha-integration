# Security

Please report security problems privately through GitHub's
[private vulnerability reporting](https://github.com/oneofthegeeks/algo-speaker-ha-integration/security/advisories/new),
not in a public issue. Include the version and how to reproduce it; never include a real
device password.

Known and documented trade-offs (not vulnerabilities): device TLS certificates are not verified,
and Standard/None auth fall back to http. See "Known limits" in the README.
