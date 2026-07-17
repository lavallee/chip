# Security Policy

## Supported versions

Only the latest published release of `chipspec` is supported with
security fixes. There is no long-term-support branch — please upgrade
before reporting an issue against an older version.

## Reporting a vulnerability

Please report security issues privately by emailing
**mlavallee@gmail.com** rather than opening a public GitHub issue.
Include:

- A description of the issue and its potential impact
- Steps to reproduce (a minimal repro is ideal)
- The `chipspec` version and platform

You should get an acknowledgement within a few days. Once a fix is
ready, we'll coordinate disclosure and credit with you.

## Scope

`chipspec` is a contract, validator, and conformance kit — it is not a
runtime and does not execute chips, hold credentials, or make network
calls on its own. The relevant attack surface is narrow:

- **Schema and spec validation** — malformed or adversarial chip
  manifests, port payloads, or receipts should fail validation
  predictably rather than crash the validator or execute arbitrary
  code.
- **The conformance kit** — test fixtures and example chips run
  locally against the spec; they should not read or write outside the
  project directory.

Actual chip execution, credential handling, and network egress are the
responsibility of a host (for example fab (being open-sourced))
and a gateway (for example [somm](https://github.com/lavallee/somm)) —
report runtime concerns to those projects instead.

Out of scope: vulnerabilities that require an attacker to already have
arbitrary code execution on the machine running `chipspec`, or that
require physical access to the host.
