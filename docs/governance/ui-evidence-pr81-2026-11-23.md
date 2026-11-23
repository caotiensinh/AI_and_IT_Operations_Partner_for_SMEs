# Verified synthetic browser screenshots — PR #81 (2026-11-23)

**Scope:** existing Overview, Assets and Monitoring UI in disposable CI only; not deployed HTTPS staging or owner/customer acceptance.

## Source and provenance
- Repository visibility at capture review: public. Screens and test data are synthetic.
- [CI workflow run 45177590260](https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/actions/runs/45177590260).
- Source/test commit: `0eeda0f9180b7762674c708031ead9e084ebe543`.
- [Merged PR #81](https://github.com/caotiensinh/AI_and_IT_Operations_Partner_for_SMEs/pull/81); main squash merge `138716b260fa66fb9842f7d82221dcd471e80812`. **Different SHA**: these screenshots prove only the PR head under test, not a new capture against main.
- Artifact ID: `14820451841`, name `sme-real-browser-synthetic-ci-evidence`, 603087 stored bytes at verification time; expires under workflow retention policy (14 days).
- The ZIP was retrieved from GitHub and all **13** embedded PNG files were independently checked against the included `manifest.json` for file byte count, pixel dimensions and SHA-256. The manifest identifies captures as `INTEGRATION_TEST_NOT_USER_ACCEPTANCE`, `UNREVIEWED`, `NOT_VERIFIED` archival state when initially produced.
- Captured viewports per screen: 1440×900, 820×1180, 390×844, 320×640; one additional unauthorized screenshot at 390×844.
- The real Chromium→Vite→FastAPI→PostgreSQL tests passed: per-field UI/API equality, tenant separation, SQL NULL CPU/memory rendered N/A, temporary HTTP 503 outage and recovery. The transient 503 was injected by Playwright, not a real production outage.

## Independently verified image inventory
| Screenshot | Bytes | SHA-256 |
|---|---:|---|
| `assets-1440x900.png` | 59929 | `6b39f1ef01d6b0986a89689a1d336cf5aec0cc21173ef412dbb01a3107fd7ee2` |
| `assets-320x640.png` | 42256 | `96db443137bff086d89d01c890c8eb92513b7aeed729a52b6c4f58da9428d890` |
| `assets-390x844.png` | 43483 | `f85ea555d21162256dfe62e6ccfc8baf5c7ce0092105e1e7517b69e44fa36b7c` |
| `assets-820x1180.png` | 60722 | `7f1ea90c6010a229a110a38eb9fb28df69aaa41e28cad64443af09ca5e40b24b` |
| `monitoring-1440x900.png` | 58407 | `8feb3f6653fce567ac075be5c41897e44201b417ced55489d8575b5ccd291c70` |
| `monitoring-320x640.png` | 39135 | `64de78d49fa4315ec7e171953609cfb261fa74298d53afe67f1abb097bc35602` |
| `monitoring-390x844.png` | 42480 | `3b739331c955427c75ebae4c415e4e754b048a657d80b99c5f124242e3c6317d` |
| `monitoring-820x1180.png` | 56602 | `5cfdd7ac5af03336985d84eae2ed25bd559a38350ca0609099e90525a404a0d8` |
| `overview-1440x900.png` | 72815 | `657f647a4256139ef6c116b943049a636f2ae4e747121a6eb169abdfb04bbbcd` |
| `overview-320x640.png` | 34597 | `e5d23b5d5c1c1d038ad00bb724d83448c4a3f958e543bb37c2f3bd0496ceebf3` |
| `overview-390x844.png` | 43311 | `d751ca897aeb62574134d98b369dd67b83da0e6e165d8b02682d27001be30dac` |
| `overview-820x1180.png` | 74501 | `56e63c489bda29d0747a12a64e909d5455d8250a66c7bba2e9756e2d4a2c2a30` |
| `unauthorized-390x844.png` | 22035 | `3403d91e375c564264e107173eb79034a658c79f8871cee06f122a22439eafce` |

## Evidence acceptance decision
- **Capture integrity:** PASS (13/13)
- **GitHub artifact storage:** CONFIRMED PRESENT on run 45177590260 (earlier quota failures were separate runs)
- **Visual inspection:** screenshots opened and reviewed as synthetic browser outputs; Overview, Assets and Monitoring render at desktop/mobile; Monitoring screenshot visibly shows SQL NULL sensors as N/A.
- **Actual enterprise OIDC sign-in:** NOT TESTED; CI uses a special synthetic bearer header and test session.
- **Deployed HTTPS staging:** NOT TESTED.
- **Failure/restart/backup of real collector:** NOT TESTED.
- **Independent owner sign-off:** NOT RECEIVED.
- **UI L4 ACCEPTED:** **NO**. The five-item acceptance baseline remains **0/5 accepted**; artifact storage success does not grant human acceptance.

## Preservation and reproduction
The artifact has limited retention. The file inventory and hashes in this version-controlled document remain as integrity evidence only, **not as a substitute for the 13 images**. Before promoting acceptance, an authorized reviewer must archive the original screenshots in durable access-controlled storage, inspect the same source SHA, and repeat with real staging authentication, owner sign-off and failure/recovery validation. Do not call this production-ready.
