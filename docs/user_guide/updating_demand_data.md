# Updating the demand figures

1. Copy `config/project_config.yaml` to a safe place as the previous revision.
2. Edit `demand_data.*` in the configuration: the IT load, the facility demand estimate, and the source and date. Change nothing else for a pure demand update. Raise `project.revision`.
3. Run `python -m ohmetry_dc validate-config`. Check any new WARNING or FAIL.
4. Run `python -m ohmetry_dc revision-impact --previous-config PREVIOUS.yaml --record "what changed and why"`. It prints the changed inputs, load changes, equipment sizing changes and check status changes, and adds them to `config/design_basis_revisions.yaml`.
5. Regenerate: `run-calculations`, `sizing-summary`, `generate-workbooks`, `generate-reports`.
6. A reviewer fills the `reviewer` field of the new revision entry. Until then it stays NOT REVIEWED.

Equipment ratings are in `equipment.*` and are never frozen. If the sizing changes, change them there, not in code.
