# SkillPack pair session

SkillPack is a small toolchain for Agent Skills packages: a `SKILL.md` with YAML frontmatter and a Markdown body. `skillpack/frontmatter.py` reads the lesson's YAML subset, `skillpack/contract.py` holds the portable core fields and the name rules, `skillpack/writer.py` writes `SKILL.md` files, `skillpack/validate.py` checks a package before a host puts it in its catalog, `skillpack/lifecycle.py` checks a host's lifecycle events and reports them as TAP, and `skillpack/workflow.py` reads the workflow edges between skills.

The goal of this session is to write the application code so that every test in `tests/test_parts.py` passes as written.

## Pt 0 Setup

You need Python 3.10+ and pytest (`python -m pip install pytest`). Run `python -m pytest` from this folder. Every part starts out skipped.

## Pt 1 `test_frontmatter_and_names`

Comment out `@pytest.mark.skip("Part 1")`, run pytest, and work out why some SKILL.md files and skill names are read wrong. A frontmatter field appears once within its mapping.

## Pt 2 `test_skill_file_roundtrip`

Write a skill back out as a SKILL.md.

## Pt 3 `test_validation_order`

Check a package before a host catalogs it.

## Pt 4 `test_lifecycle_tap`

Check each skill session against the lifecycle as the host's events arrive.

## Pt 5 `test_workflow_edges`

Find the workflow edges between skills, and an order to install them in.
