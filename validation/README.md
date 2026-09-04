# Captured validation output

These logs were captured during local repository validation on 2026-09-02,
using Python 3.12.13 and `cryptography` 46.0.0. Each supplied script ran in a
separate directory with its matching module. All eleven runner targets exited
with code 0.

| Log | Target |
| --- | --- |
| [demo.txt](demo.txt) | Primary v0.6 demonstration |
| [validate.txt](validate.txt) | Supplied v0.6 assertions |
| [example.txt](example.txt) | New owner walkthrough |
| [demo-v03.txt](demo-v03.txt) | Historical v0.3 demonstration |
| [demo-v04.txt](demo-v04.txt) | Historical v0.4 demonstration |
| [probe-v04.txt](probe-v04.txt) | Historical v0.4 observations |
| [demo-v05.txt](demo-v05.txt) | Historical v0.5 demonstration |
| [probe-v05.txt](probe-v05.txt) | Historical v0.5 observations |
| [demo-v06-birth-root.txt](demo-v06-birth-root.txt) | Alternative v0.6 demonstration |
| [probe-v06-birth-root.txt](probe-v06-birth-root.txt) | Alternative v0.6 observations |
| [triage-v06-birth-root.txt](triage-v06-birth-root.txt) | Alternative v0.6 triage |
| [installation.txt](installation.txt) | Local wheel installation and import check |

Generated state and keys are excluded. The fresh random identifiers appearing
in these logs are demonstration values. Read the
[validation record](../docs/VALIDATION.md) for the difference between process
completion, printed observations, and assertion results, including the known
probe defects.
