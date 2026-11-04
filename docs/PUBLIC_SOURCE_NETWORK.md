# Public source network

SalesIntel can use a dedicated local discovery runtime to identify possible public data sources, and can query a separately reviewed Planning Data England operation. Source suggestions are unreviewed; they are not evidence, permission to run a source, or a guarantee that a source is public, licensed, UK-wide, accurate or relevant. The network does not monitor all UK data or automatically verify sales opportunities.

## Local setup

Set up SalesIntel and the pilot database as described in [VIRTUAL_SENSOR.md](VIRTUAL_SENSOR.md). Node.js 22.18 or later is required. Install the reviewed upstream revision in SalesIntel's ignored runtime directory:

```bash
mkdir -p .runtime
git clone https://github.com/rossbuckley1990-hash/rightclick-x.git .runtime/rightclick-x
git -C .runtime/rightclick-x checkout 278d66c327ffe60b25805399b1f6d284840d1628
pnpm dev:sensor
```

The upstream repository and its licence govern the third-party runtime; retain its licence and attribution when distributing it. With that checkout present, the startup script launches a separate loopback-only runtime, creates an owner-only local token, and loads the Planning Data England OpenAPI contract. Runtime state, token, checkout and pilot database are ignored local files. Protect the machine and its files; this unauthenticated pilot is not a shared production deployment. If the runtime is unavailable, SalesIntel can continue without it.

A separately managed runtime can be configured using the existing backend environment variables `RIGHTCLICK_X_URL` and `RIGHTCLICK_X_TOKEN`. The URL must be a loopback IP with an MCP path, and the dedicated runtime must contain the approved contract and operator-owned read-only restrictions. Never place tokens in frontend environment variables.

## Discovery and evidence

When configured, research can look for candidate source descriptions using up to three generic topics from a fixed allowlist. The directory queries do not include the user's brief, account names, contact details or postcodes. Candidate descriptions are screened locally and remain unreviewed; they are not executed or treated as findings. An empty result is not a comprehensive search.

The reviewed Planning Data England lookup requires an explicit UPRN or full postcode and an approved dataset: planning applications, brownfield land or conservation areas. Its actual provider, GET operation, HTTPS origin and read-only policy are checked before use. At most five records enter a research brief; up to ten can be shown in source exploration. Planning data covers England, local authority participation varies, and a missing result is not proof that no activity exists. A receipt records a call; it does not verify site identity, a maintenance requirement or buying intent.

A separate opt-in food establishment lookup accepts an explicit full postcode and calls the Food Standards Agency's public register directly. The register covers England, Scotland, Wales and Northern Ireland, but only food establishments, and may be incomplete or stale. SalesIntel examines at most the first 20 upstream records and shows up to ten exact-postcode matches. Multiple premises may share a postcode. The register is estate context only: food registration and inspections do not establish fire or security conditions, maintenance gaps or purchasing intent. An empty result is not proof a business or site is absent.

The model and public web research operate separately from directory discovery. Returned material is untrusted and needs independent verification. Further operational sources require explicit source-specific permissions and checks; directory discovery does not grant those permissions.
