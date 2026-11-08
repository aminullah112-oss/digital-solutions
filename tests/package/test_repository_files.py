import yaml

REQUIRED = ["README.md", "LICENSE", "pyproject.toml", "requirements.txt", ".gitignore", "DEVELOPMENT_STATUS.md", "RELEASE_CHECKLIST.md", "ENGINEERING_REVIEW_LOG.md",
            "config/project_config.yaml", "config/load_schedule.yaml", "config/equipment_data_template.yaml", "config/standards_register.yaml", "config/assumptions_register.yaml", "config/design_basis_revisions.yaml"]


def test_required_files_exist(root):
    for rel in REQUIRED:
        assert (root / rel).is_file(), rel


def test_no_secrets_or_personal_data_in_the_repository(root):
    banned = ["password", "api_key", "secret", "@gmail.com", "BEGIN PRIVATE KEY"]
    for p in root.rglob("*"):
        if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts and "output" not in p.relative_to(root).parts[:1] and p.suffix in {".md", ".yaml", ".py", ".toml", ".txt"} and p.name != "test_repository_files.py":
            text = p.read_text(errors="ignore").lower()
            for b in banned:
                assert b.lower() not in text, f"{b!r} found in {p}"


def test_every_standard_starts_not_verified_with_no_invented_edition(root):
    reg = yaml.safe_load((root / "config" / "standards_register.yaml").read_text())
    assert len(reg["standards"]) >= 16
    for s in reg["standards"]:
        assert s["applicability_status"] == "NOT_VERIFIED" and s["edition"] is None, s["id"]


def test_equipment_template_contains_no_values(root):
    t = yaml.safe_load((root / "config" / "equipment_data_template.yaml").read_text())["equipment_template"]
    assert all(v in (None, "MANUFACTURER_DATA", "PENDING", "NOT_STARTED") or isinstance(v, dict) for v in t.values())
