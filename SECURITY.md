# Security policy for this public repository

## Reporting vulnerabilities
Do not include exploit details, secrets, production URLs or customer data in public GitHub issues. Use GitHub's **Report a vulnerability** / private vulnerability reporting option in the repository Security tab when enabled, or contact the repository maintainer through a non-public channel.

## Public repository exposure checklist

Visibility was verified as `public` on 2026-11-22. The `public-repo-safety.yml` workflow provides a basic **tracked-file working-tree guard**. It rejects private-key PEM headers, recognizable credential tokens, tracked `.env` and key-store files, non-placeholder sensitive `.env.staging.example` entries, symlinks, and files too large to inspect.

**This is not a clean security audit.** The guard does not inspect Git history, old/closed PR branches, forks, archived workflow logs, Actions artifacts, commit messages, issue bodies or network services. It also cannot detect every secret format or distinguish intentionally fake tokens with certainty.

Before announcing public-source security acceptance:
1. Run an authorized history-aware secret scanner, including tags and all remote refs; use up-to-date secret detection rules. Record the exact scope and result privately.
2. Rotate any credentials that may have been present in commits, Actions logs or screenshots. Removing a value from HEAD does not revoke leaked access.
3. Check GitHub Security alerts, public branch protection, PR review requirements and least-privilege Actions permissions.
4. Keep production secrets and user/customer datasets outside the repository and use approved CI secrets/variable stores.
5. Review public screenshot artifacts for names, UUIDs, API URLs and accidental user information before distribution. Synthetic fixture labels should never be presented as customer data.
6. Do not enable the Asahi production approval BFF based on a passing scanner; real IdP, HTTPS, rate limits and independent acceptance remain mandatory.

## Scope and accountability
Open source code and executable unit tests are separate from release acceptance. Existing five product records remain 0/5 ACCEPTED until their evidence and independent review satisfy the Definition of Done.
