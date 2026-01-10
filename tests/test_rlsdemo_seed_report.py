from app.services.rls_demo import seed_rls_demo, build_visibility_report, EXPECTED_VISIBILITY


def test_rlsdemo_seed_report(app):
    with app.app_context():
        seed_rls_demo(reset=True, domain="demo.com", password="demo1234")
        report = build_visibility_report(domain="demo.com")

    for alias in ["custA.viewer", "custB.viewer", "supX.viewer", "supY.viewer", "misconfig.custrole"]:
        expected_jobs = sorted(EXPECTED_VISIBILITY[alias]["jobs"])
        expected_orders = sorted(EXPECTED_VISIBILITY[alias]["orders"])
        assert report[alias]["jobs"] == expected_jobs
        assert report[alias]["orders"] == expected_orders

    assert set(report["planner"]["jobs"]) == set(EXPECTED_VISIBILITY["planner"]["jobs"])
    assert set(report["planner"]["orders"]) == set(EXPECTED_VISIBILITY["planner"]["orders"])

    assert report["misconfig.custrole"]["jobs"] == []
    assert report["misconfig.custrole"]["orders"] == []

    assert report["custA.viewer"]["parts_allowed"] not in (None, 0)
    assert report["planner"]["parts_allowed"] is None
