from app.models.auth import Role


def test_seed_roles_creates_expected(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["user", "seed-roles"])
    assert result.exit_code == 0
    names = {r.name for r in Role.objects()}
    assert "admin" in names
    assert "planner" in names
    assert "operator" in names
    assert "viewer" in names
