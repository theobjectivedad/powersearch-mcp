# Security Policy

We want PowerSearch MCP to be safe for everyone. Please use the process below to report vulnerabilities privately and responsibly.

## Reporting a Vulnerability

Please submit reports via the private security advisory flow:

1. Open a private report at <https://github.com/theobjectivedad/powersearch-mcp/security/advisories/new>.
2. Include the following details so we can triage quickly:
   - A clear description of the issue, affected component, and potential impact.
   - Reproduction steps or proof of concept (commands, config, logs, screenshots as needed).
   - Environment details (OS, Python version, commit hash/tag, config snippets that matter).
   - Any suggested mitigations or fixes you have in mind.
3. Do not file public issues for security topics. If you accidentally disclosed sensitive information publicly, please let us know immediately.

Preferred languages: English.

## What to Expect

- Acknowledgement: We aim to respond within 3 business days with initial triage status.
- Fix timeline: We prioritize by severity and complexity; critical issues are addressed as quickly as possible.
- Credit: With your permission, we will credit reporters in release notes or advisories once a fix is implemented.

## Safe Testing Guidelines

- Do not exploit beyond what is needed to demonstrate the issue; avoid data destruction or service disruption.
- Do not perform denial-of-service, spam, or automated volumetric testing against deployments you do not control.
- Use test or non-production instances when possible; avoid impacting other users.
- Do not access, modify, or exfiltrate data that does not belong to you.

## Out of Scope

- Social engineering, phishing, or physical attacks.
- Findings that require compromised accounts, stolen tokens, or unsafe runtime flags/configurations.
- Denial-of-service attacks or excessive load testing.
- Vulnerabilities in third-party services or dependencies not maintained in this repository (please report those upstream).

## Disclosure

Please keep reports private until a fix or mitigation is available. After a fix is released, you may disclose responsibly. If we determine not to address an issue, we will let you know and you are free to disclose after our response.
