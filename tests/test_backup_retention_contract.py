"""The two backup implementations must not drift apart on safety.

TinyMRP backs up through two separate paths, deliberately:

  deploy/scripts/backup-instance.sh   the VPS fleet, many instances per host
  deploy/community/tinymrp.sh         a single instance, shipped as a
                                      self-contained bundle that must keep
                                      working when downloaded on its own

The bundle cannot source deploy/scripts/lib/, which is why the logic is written
twice. That is a packaging constraint, not a feature tier - but it means a fix
made in one place can silently miss the other. Every rule below was written
twice for that reason, and these tests fail if a future change only lands in
one of them.

They assert the SAFETY PROPERTIES, not the wording, so ordinary edits are free.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
VPS = REPO / "deploy" / "scripts" / "backup-instance.sh"
BUNDLE = REPO / "deploy" / "community" / "tinymrp.sh"

BOTH = pytest.mark.parametrize(
    "script",
    [pytest.param(VPS, id="vps"), pytest.param(BUNDLE, id="bundle")],
)


def _source(script: Path) -> str:
    return script.read_text(encoding="utf-8")


@BOTH
def test_the_script_exists_and_is_a_shell_program(script: Path):
    assert script.is_file(), f"{script} is missing"
    assert _source(script).startswith("#!"), f"{script} lost its shebang"


@BOTH
def test_a_free_space_floor_is_configurable(script: Path):
    """The other limits bound the backup folder; only this bounds the disk."""
    text = _source(script)
    assert "MIN_FREE_GB" in text, (
        f"{script.name} has no absolute free-space floor. Retention by age, "
        "count or folder size cannot stop a disk filling, because none of them "
        "know what else is on the disk."
    )
    assert "MIN_FREE_PCT" in text, (
        f"{script.name} has no percentage floor. A fixed GB floor is wrong as "
        "soon as the host is resized."
    )


@BOTH
def test_the_floor_takes_the_larger_of_the_two_limits(script: Path):
    """Whichever is larger wins, so the floor scales with the host."""
    text = _source(script)
    assert "1024 * 1024" in text or "1024*1024" in text, (
        f"{script.name} does not convert its GB floor into the units df reports"
    )
    assert "/ 100" in text, (
        f"{script.name} does not derive a percentage of the filesystem size"
    )


@BOTH
def test_the_floor_is_checked_before_the_backup_is_written(script: Path):
    """Pruning only afterwards cannot prevent the failure it exists to prevent.

    The disk fills while the archive is being written, so the check has to
    happen before a single byte is committed.
    """
    text = _source(script)
    marker = "free_space_until" if script == VPS else "backup_free_space_until"
    assert text.count(marker) >= 3, (
        f"{script.name} should define the floor helper and call it both before "
        "and after the backup; found fewer references than that"
    )
    # Line-wise and comment-blind: both files describe themselves in a header
    # comment, so a plain substring search finds the prose, not the code.
    code = [
        (index, line)
        for index, line in enumerate(text.splitlines())
        if line.strip() and not line.lstrip().startswith("#")
    ]
    first_write = next(
        index for index, line in code if "mongodump" in line
    )
    first_check = next(
        index for index, line in code if f"{marker} " in line or f"{marker}(" in line
    )
    assert first_check < first_write, (
        f"{script.name} checks the free-space floor at line {first_check}, "
        f"after it starts writing at line {first_write}. By then the disk is "
        "already full."
    )


@BOTH
def test_running_out_of_room_aborts_instead_of_writing_anyway(script: Path):
    """A missed backup is recoverable; a full disk takes the instance down."""
    text = _source(script)
    assert "Not enough disk" in text, (
        f"{script.name} does not refuse when there is no room. It must abort "
        "and keep the existing backups rather than fill the disk."
    )
    assert "KEPT" in text, (
        f"{script.name} does not tell the operator the existing backups "
        "survived, which is the one thing they need to know on failure"
    )


@BOTH
def test_the_newest_backup_of_each_kind_is_protected(script: Path):
    """Full and database-only backups are complementary, not interchangeable.

    The newest full backup is the only copy of the deliverables; the newest
    database-only one is the freshest data. Pruning for space must never leave
    zero of either.
    """
    text = _source(script)
    assert "deliverables.tar.gz" in text, (
        f"{script.name} cannot tell a full backup from a database-only one"
    )
    if script == VPS:
        assert "protected_backups" in text
        assert "KEEP_FULL" in text and "KEEP_DB" in text, (
            "full and database-only backups must be counted separately: they "
            "differ by three orders of magnitude, and sharing one ceiling let "
            "a single full backup evict a month of daily restore points"
        )
    else:
        assert "newest_full" in text, (
            "the bundle must protect its newest full backup as well as its "
            "newest backup overall"
        )


@BOTH
def test_pruning_for_space_takes_the_oldest_first(script: Path):
    """Stop as soon as there is room, so one backup is the worst case."""
    text = _source(script)
    assert "sort" in text, f"{script.name} does not order backups before pruning"
    marker = "prunable_backups_oldest_first" if script == VPS else "sort)"
    assert marker in text, (
        f"{script.name} does not prune oldest-first; pruning newest-first "
        "would destroy the most useful copy on the way to the floor"
    )


def _executable_source(script: Path) -> str:
    """The script with comments stripped.

    Every one of these files documents its own flags in a header comment, so a
    plain substring search proves only that the flag was described - not that
    it is still wired up. Two assertions here passed against prose before this
    was added.
    """
    return chr(10).join(
        line
        for line in script.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def test_the_fleet_wrapper_forwards_every_retention_flag():
    """backup-all.sh whitelists arguments, so a new flag is silently dropped."""
    wrapper = _executable_source(REPO / "deploy" / "scripts" / "backup-all.sh")
    instance = _executable_source(VPS)
    for flag in ("--keep-days", "--keep-full", "--keep-db", "--max-total-gb",
                 "--min-free-gb", "--min-free-pct"):
        assert flag in instance, f"backup-instance.sh no longer accepts {flag}"
        assert flag in wrapper, (
            f"backup-all.sh does not forward {flag}, so scheduled backups would "
            "silently ignore it while single-instance runs honoured it"
        )


def test_the_installed_timers_carry_the_retention_settings():
    """The systemd units embed the command, so the flags must reach them."""
    installer = _executable_source(REPO / "deploy" / "scripts" / "install-backup-job.sh")
    for flag in ("--keep-full", "--keep-db", "--min-free-gb", "--min-free-pct"):
        assert flag in installer, (
            f"install-backup-job.sh does not pass {flag}, so the scheduled "
            "backups would run with different rules from a manual one"
        )


def test_the_documentation_describes_the_floor():
    """Help and behaviour are meant to be checkable against each other."""
    doc = (REPO / "docs" / "deployment" / "10-operations.md").read_text(encoding="utf-8")
    for token in ("--min-free-gb", "--min-free-pct", "--keep-full", "--keep-db"):
        assert token in doc, f"10-operations.md does not document {token}"
    assert "refuses to run" in doc, (
        "the docs must state that a backup with no room aborts rather than "
        "filling the disk, because that is the surprising part"
    )
