# Third-Party and Bundled Component Notices

This file records redistribution notices for components bundled with this
repository. It supplements, and does not replace, `COPYING.md`, which carries
the original runit license and copyright notices (retained unchanged).

## runit (core)

Copyright (C) Gerrit Pape and contributors. Licensed under the 3-clause BSD
license reproduced in `COPYING.md`. All original license headers and the
project history are preserved.

## Bundled local diagnostic model

* Path: `scripts/edge_diag/model.json`
* Type: interpretable linear scoring model over service-failure features.
* Origin: authored in this repository for the embedded AI diagnostics
  capability. It contains no third-party weights, no scraped corpora, and no
  personal data.
* License: same 3-clause BSD terms as the rest of this repository; it may be
  redistributed, modified and used offline without additional permission.
* Offline guarantee: the model is loaded from local disk only. No network
  access, no telemetry, and no external model service is contacted at any point.
* Attribution requirement on redistribution: retain this notice and
  `COPYING.md` alongside the model file.

## Python runtime

The platform capabilities require a Python 3 interpreter, which is **not**
bundled. It is provided by the host distribution under its own license (PSF).
