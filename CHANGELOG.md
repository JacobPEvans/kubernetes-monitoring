# Changelog

## [1.2.0](https://github.com/JacobPEvans/kubernetes-monitoring/compare/v1.1.0...v1.2.0) (2026-03-12)

### Features

* CPU defaults via namespace LimitRange ([#90](https://github.com/JacobPEvans/kubernetes-monitoring/issues/90)) ([cb98230](https://github.com/JacobPEvans/kubernetes-monitoring/commit/cb982300621b131dc8383c1d5b08ce4fb5be3384))

### Bug Fixes

* move CRIBL_VOLUME_DIR outside CRIBL_HOME to prevent recursive copy ([#94](https://github.com/JacobPEvans/kubernetes-monitoring/issues/94)) ([453d72b](https://github.com/JacobPEvans/kubernetes-monitoring/commit/453d72b102d5aedca6550c9a1117175afa4992e2))

## [1.1.0](https://github.com/JacobPEvans/kubernetes-monitoring/compare/v1.0.0...v1.1.0) (2026-03-11)

### Features

* add Cribl MCP server to monitoring stack ([#33](https://github.com/JacobPEvans/kubernetes-monitoring/issues/33)) ([f5c1835](https://github.com/JacobPEvans/kubernetes-monitoring/commit/f5c1835eee6e4848a0b38837f5dfc0520f342431))
* add daily repo health audit agentic workflow ([#88](https://github.com/JacobPEvans/kubernetes-monitoring/issues/88)) ([fd12713](https://github.com/JacobPEvans/kubernetes-monitoring/commit/fd12713b05bf8cf14dac8e6a76f21d8ddd3d41df))
* add disk GC guardrails for ephemeral storage ([#80](https://github.com/JacobPEvans/kubernetes-monitoring/issues/80)) ([d96bfa8](https://github.com/JacobPEvans/kubernetes-monitoring/commit/d96bfa8b058082b793b581eafea44122dc33b028))
* add Doppler + SOPS secret management for deployment ([#2](https://github.com/JacobPEvans/kubernetes-monitoring/issues/2)) ([74a980d](https://github.com/JacobPEvans/kubernetes-monitoring/commit/74a980d4f5cb7a1be066f0de14a07fe90e940303))
* add full AI workflow suite ([#60](https://github.com/JacobPEvans/kubernetes-monitoring/issues/60)) ([5ecc7ad](https://github.com/JacobPEvans/kubernetes-monitoring/commit/5ecc7adae0dbf61c4cad65b98a23d46d03492dc1))
* add Gemini pack integration with REST API installer refactor ([#71](https://github.com/JacobPEvans/kubernetes-monitoring/issues/71)) ([e5fa1b2](https://github.com/JacobPEvans/kubernetes-monitoring/commit/e5fa1b27f0c527f7ba7434988f184b36dae32b7b))
* add gh-aw agentic workflows (ci-doctor, malicious-code-scan, sub-issue-closer, ai-moderator) ([#56](https://github.com/JacobPEvans/kubernetes-monitoring/issues/56)) ([7950b42](https://github.com/JacobPEvans/kubernetes-monitoring/commit/7950b4280439a3a68fe039f3119368d7740cff38))
* add Hammerspoon power management script ([#21](https://github.com/JacobPEvans/kubernetes-monitoring/issues/21)) ([365054f](https://github.com/JacobPEvans/kubernetes-monitoring/commit/365054f4a669db9a6d521532e202cca1feae950d))
* add kubeconform schema validation to pre-commit and CI ([#10](https://github.com/JacobPEvans/kubernetes-monitoring/issues/10)) ([eb8c0ac](https://github.com/JacobPEvans/kubernetes-monitoring/commit/eb8c0acb22efcd7e0948ce0fd0f55c0323995a0b))
* add per-repo devShell ([#53](https://github.com/JacobPEvans/kubernetes-monitoring/issues/53)) ([4f7c58d](https://github.com/JacobPEvans/kubernetes-monitoring/commit/4f7c58def8a2a3b394fd44212edfe1b16aa50d89))
* add two-phase log masking to E2E workflow ([fa6b879](https://github.com/JacobPEvans/kubernetes-monitoring/commit/fa6b8790a40a49386f5663f03e96ca4877622ca2))
* architecture diagram, test overhaul, fix Cribl Stream data path ([#22](https://github.com/JacobPEvans/kubernetes-monitoring/issues/22)) ([f06b287](https://github.com/JacobPEvans/kubernetes-monitoring/commit/f06b287b7fe3df3086e50a00e702c65594e4cb29))
* disable automatic triggers on Claude-executing workflows ([551133b](https://github.com/JacobPEvans/kubernetes-monitoring/commit/551133bf74878e3343586b50691003c8eeb2c597))
* expand Claude Code collection to 10 data sources via fork pack ([#52](https://github.com/JacobPEvans/kubernetes-monitoring/issues/52)) ([66676e3](https://github.com/JacobPEvans/kubernetes-monitoring/commit/66676e37a1818734ebb3493504f6d5359a40e3c6))
* healthchecks.io dead-man's switch integration for all components ([#50](https://github.com/JacobPEvans/kubernetes-monitoring/issues/50)) ([226c23c](https://github.com/JacobPEvans/kubernetes-monitoring/commit/226c23c734161396eddd9f6295b755b8ca3aa5ff))
* pipeline heartbeat CronJob with dead-man's switch ([#35](https://github.com/JacobPEvans/kubernetes-monitoring/issues/35)) ([ce75e5a](https://github.com/JacobPEvans/kubernetes-monitoring/commit/ce75e5a23d08f268d83a4032f6afbb9ac4894cbd))
* release readiness — security hardening, NetworkPolicies, PDBs, and tests ([#25](https://github.com/JacobPEvans/kubernetes-monitoring/issues/25)) ([0951ffd](https://github.com/JacobPEvans/kubernetes-monitoring/commit/0951ffd45f36a6776748aef8af9b9c53c702b39f))
* Renovate trusted-publisher allowlist with Tier 1 + Tier 2 rules ([#30](https://github.com/JacobPEvans/kubernetes-monitoring/issues/30)) ([c74a839](https://github.com/JacobPEvans/kubernetes-monitoring/commit/c74a8393baa047d3d4fea86163a03c231b68dcf4))
* **renovate:** extend shared preset, remove duplicated rules ([d8dab9e](https://github.com/JacobPEvans/kubernetes-monitoring/commit/d8dab9e0e603a506d9cc088141e5d53c1d4b538a))
* split Cribl Stream into standalone + managed, fix OOM ([#6](https://github.com/JacobPEvans/kubernetes-monitoring/issues/6)) ([7287f7e](https://github.com/JacobPEvans/kubernetes-monitoring/commit/7287f7e306ed213579d2eba3a07bbec72e7a13eb))

### Bug Fixes

* add -x to test-e2e to fail fast on first error ([#87](https://github.com/JacobPEvans/kubernetes-monitoring/issues/87)) ([66016f9](https://github.com/JacobPEvans/kubernetes-monitoring/commit/66016f9535820bf43c7e83679a9e4edeafb50107))
* add startup probe to cribl-edge-managed StatefulSet ([#45](https://github.com/JacobPEvans/kubernetes-monitoring/issues/45)) ([105d58c](https://github.com/JacobPEvans/kubernetes-monitoring/commit/105d58c8685f4453f94efb30c105dd2d692346a2)), closes [#41](https://github.com/JacobPEvans/kubernetes-monitoring/issues/41)
* add yq to runner image, mount age key, remove DOPPLER_TOKEN override ([4b847cf](https://github.com/JacobPEvans/kubernetes-monitoring/commit/4b847cfdf6b8bd3a6f6fecae1c6fc34dedfa3256))
* devShell DIRENV_DIR check, version fallbacks, helm-docs in CLAUDE.md ([f9b961c](https://github.com/JacobPEvans/kubernetes-monitoring/commit/f9b961c2af4eaac33bc053a2f9145fb70c944212))
* enforce edge→stream→splunk architecture, fix stream CrashLoopBackOff, auto-restart on deploy ([#34](https://github.com/JacobPEvans/kubernetes-monitoring/issues/34)) ([b422135](https://github.com/JacobPEvans/kubernetes-monitoring/commit/b422135b839e139963f5bd53fffccbae23cd6d4d))
* fix FileMonitor patterns at pack source, remove all sed workarounds ([#83](https://github.com/JacobPEvans/kubernetes-monitoring/issues/83)) ([469eece](https://github.com/JacobPEvans/kubernetes-monitoring/commit/469eece2dc05e7122eec6b0bec218ded797f3815))
* heartbeat uses /api/v1/health (stats API requires auth) ([#47](https://github.com/JacobPEvans/kubernetes-monitoring/issues/47)) ([dff07a7](https://github.com/JacobPEvans/kubernetes-monitoring/commit/dff07a721b44740471a8d76ac474aa54594863bd))
* heartbeat-edge K8s API health check + remove postStart hook crash loop ([#51](https://github.com/JacobPEvans/kubernetes-monitoring/issues/51)) ([94fdfc2](https://github.com/JacobPEvans/kubernetes-monitoring/commit/94fdfc22214df31984f2aa176d4dc8cec594055c))
* make pack install reliable on cold start, fix stale test assertion ([#84](https://github.com/JacobPEvans/kubernetes-monitoring/issues/84)) ([bab9421](https://github.com/JacobPEvans/kubernetes-monitoring/commit/bab94210edbbe594009a2b2d3e75019d24755aa8))
* make Trivy vulnerability scanning blocking in CI ([#44](https://github.com/JacobPEvans/kubernetes-monitoring/issues/44)) ([33145fc](https://github.com/JacobPEvans/kubernetes-monitoring/commit/33145fc86d64823a64d655bceb0b0007d708b414)), closes [#40](https://github.com/JacobPEvans/kubernetes-monitoring/issues/40)
* remove hardcoded Splunk IP, add SPLUNK_HEC_URL secret, pin OTEL to latest ([#8](https://github.com/JacobPEvans/kubernetes-monitoring/issues/8)) ([605adcb](https://github.com/JacobPEvans/kubernetes-monitoring/commit/605adcbadaffba47a612696b0dc16e8d5e1b8978))
* **renovate:** migrate aquasecurity rules to shared preset ([#73](https://github.com/JacobPEvans/kubernetes-monitoring/issues/73)) ([84adbd2](https://github.com/JacobPEvans/kubernetes-monitoring/commit/84adbd234b888ff396f7ac03138dacbc5b5a8b73))
* repo cleanup — leftover issues and code quality gaps ([#24](https://github.com/JacobPEvans/kubernetes-monitoring/issues/24)) ([2d5c225](https://github.com/JacobPEvans/kubernetes-monitoring/commit/2d5c225741351b827a43a6691b37e74b1aeda6f7))
* resolve E2E test failures from pack installer refactor and CI infra ([#81](https://github.com/JacobPEvans/kubernetes-monitoring/issues/81)) ([e796e01](https://github.com/JacobPEvans/kubernetes-monitoring/commit/e796e016d9d893d626fbd70bcfb51865059ccdf9))
* resolve E2E test failures from REST API pack installer refactor ([#78](https://github.com/JacobPEvans/kubernetes-monitoring/issues/78)) ([93d2d82](https://github.com/JacobPEvans/kubernetes-monitoring/commit/93d2d82a9eab06255527755ff974cb699f2370cd))
* resolve flaky E2E tests (log contamination + pipeline warmup) ([#89](https://github.com/JacobPEvans/kubernetes-monitoring/issues/89)) ([3bb158b](https://github.com/JacobPEvans/kubernetes-monitoring/commit/3bb158b447fa23945ec9c93eb384d435e76c66f4))
* restore edge log pipeline — CRIBL_VOLUME_DIR, splunk_hec output, real-time tests ([#32](https://github.com/JacobPEvans/kubernetes-monitoring/issues/32)) ([b844149](https://github.com/JacobPEvans/kubernetes-monitoring/commit/b844149d633c11e5c0514b7782182d280b6bad09))
* set CRIBL_VOLUME_DIR for non-root cribl/cribl:latest image ([#31](https://github.com/JacobPEvans/kubernetes-monitoring/issues/31)) ([dcfd429](https://github.com/JacobPEvans/kubernetes-monitoring/commit/dcfd429478cfb08cd3888c841846de130bfcb4fc))
* set index/sourcetype via pipeline eval, add true Splunk E2E tests ([#48](https://github.com/JacobPEvans/kubernetes-monitoring/issues/48)) ([4ca9ded](https://github.com/JacobPEvans/kubernetes-monitoring/commit/4ca9dedc618d439aa53e9e2099314797f0d742b9))
* update pack URLs to v1.2.6 (Claude) and v0.2.2 (Gemini) ([#85](https://github.com/JacobPEvans/kubernetes-monitoring/issues/85)) ([edae96b](https://github.com/JacobPEvans/kubernetes-monitoring/commit/edae96bc6d0b592418e4a26c689f883dc5a9897c))
* use direct IP for Splunk HEC, add granular forwarding tests ([#23](https://github.com/JacobPEvans/kubernetes-monitoring/issues/23)) ([ee15edb](https://github.com/JacobPEvans/kubernetes-monitoring/commit/ee15edbd7add161caeb15ba9388ae01dce36bb4b))
* use host.orb.internal for Splunk HEC and refactor Cribl config ([#20](https://github.com/JacobPEvans/kubernetes-monitoring/issues/20)) ([fbe600d](https://github.com/JacobPEvans/kubernetes-monitoring/commit/fbe600d6e6593111a434ed07a797a62f7c8ec42c))
