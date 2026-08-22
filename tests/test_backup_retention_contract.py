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


def test_age_pruning_spares_database_only_backups():
    """--keep-db must be reachable.

    Age used to expire both kinds, so a 14-day age limit capped the daily
    database backups at 14 no matter what --keep-db said. They cost ~2 MB
    against a full backup's ~2 GB; expiring them buys nothing and throws away
    the cheapest restore points there are.
    """
    text = _executable_source(VPS)
    age_block = text[text.index('KEEP_DAYS:-0'):]
    age_block = age_block[: age_block.index('prune_by_kind_count')]
    assert 'backup_kind' in age_block, (
        "age pruning does not distinguish full from database-only backups, so "
        "--keep-db can never be reached"
    )
    assert 'NEWEST_FULL' in age_block, (
        "age pruning does not spare the newest full backup; if the weekly job "
        "has been failing, that stale copy is the only copy of the deliverables"
    )


# --- what the documentation promises about deliverables ---------------------


def test_deliverables_are_off_unless_asked_for():
    """The installer default and the model default must agree on "no"."""
    model = (REPO / "app" / "models" / "app_settings.py").read_text(encoding="utf-8")
    assert "backup_include_deliverables = BooleanField(default=False)" in model, (
        "deliverables must default to OFF: they are many GB against a few MB "
        "and CAD can regenerate them"
    )
    installer = (REPO / "deploy" / "community" / "install.sh").read_text(encoding="utf-8")
    assert "Also back up deliverables?" in installer, (
        "the installer must ask, rather than deciding silently"
    )
    assert "'no'" in installer, "the installer's default answer must be no"


def test_the_installer_asks_where_deliverables_backups_go():
    installer = (REPO / "deploy" / "community" / "install.sh").read_text(encoding="utf-8")
    assert "Deliverables backup folder" in installer
    assert "BACKUP_DELIVERABLES_DEST" in installer, (
        "the answer must be recorded, or it is a question with no effect"
    )
    assert "TINYMRP_BACKUP_DELIVERABLES" in installer, (
        "non-interactive installs need the same choice"
    )


def test_a_separate_destination_leaves_a_pointer_restore_can_follow():
    """Both halves must agree, or a restore silently loses the deliverables."""
    backup = _executable_source(VPS)
    restore = _executable_source(REPO / "deploy" / "scripts" / "restore-instance.sh")
    assert "DELIVERABLES_ARCHIVE=" in backup, (
        "the backup must record where it put the archive"
    )
    assert "DELIVERABLES_ARCHIVE" in restore, (
        "restore-instance.sh does not follow the pointer, so a backup written "
        "to another drive would restore its database and silently skip its files"
    )


def test_the_off_drive_archive_still_counts_as_a_full_backup():
    """Retention classifies by content; a pointer is content."""
    backup = _executable_source(VPS)
    kind = backup[backup.index("backup_kind() {"):]
    kind = kind[: kind.index(chr(10) + "}")]
    assert "DELIVERABLES_ARCHIVE" in kind, (
        "backup_kind checks only for a local archive, so every off-drive full "
        "backup would be counted as database-only and retention would keep 30"
    )


def test_the_second_drive_gets_its_own_free_space_check():
    backup = _executable_source(VPS)
    assert "deliverables backup drive" in backup, (
        "a separate destination is a separate filesystem; without its own floor "
        "the script would fill it while reporting the first disk was fine"
    )


def test_the_terminal_overrides_the_stored_policy():
    backup = _executable_source(VPS)
    assert "FORCE_DELIVERABLES" in backup and "NO_DELIVERABLES" in backup, (
        "--with-deliverables / --no-deliverables must beat the stored policy: "
        "they are a decision about THIS run by the person running it"
    )


def test_reading_the_policy_can_never_fail_the_backup():
    backup = _executable_source(VPS)
    apply_block = backup[backup.index("apply_backup_policy() {"):]
    apply_block = apply_block[: apply_block.index(chr(10) + "}")]
    assert "return 0" in apply_block, (
        "apply_backup_policy must return success even when the settings cannot "
        "be read; an unreachable database must not stop the backup"
    )


def test_the_documentation_states_the_default_and_the_drive_advice():
    doc = (REPO / "docs" / "deployment" / "10-operations.md").read_text(encoding="utf-8")
    assert "Deliverables are not, unless you ask" in doc
    assert "another drive" in doc, (
        "the docs must say why a separate drive matters: a backup on the same "
        "disk protects against a mistake, not a dead drive"
    )
    for token in ("--with-deliverables", "--deliverables-dest", "fortnightly"):
        assert token in doc, f"10-operations.md does not document {token}"


def test_the_script_default_matches_the_documented_default():
    """"Database only, no flag needed" has to be true of the script itself.

    The policy layer falls back to the script's own default when nothing is
    stored, so a default of ON meant a fresh instance captured gigabytes of
    files while the documentation said it would not.
    """
    backup = _executable_source(VPS)
    assert "WITH_DELIVERABLES=0" in backup, (
        "backup-instance.sh must default to database-only; anything else "
        "contradicts the documented default on any instance with no stored policy"
    )

