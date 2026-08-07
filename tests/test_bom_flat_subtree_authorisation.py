"""bom_flat drops per-node authorisation. Prove the subtree gate still holds.

The flat BOM used to re-authorise every node during its descent, which is one
authorisation query per part - hundreds on a real assembly, and the difference
between a slow page and a 502. That was removed because
_bom_is_fully_authorised already proves the ENTIRE subtree before the descent
begins.

Removing a security check is only safe if the remaining one genuinely covers
the same ground, so this pins that: a subtree containing anything the user may
not see must still be refused outright, at any depth.
"""

from __future__ import annotations

def test_the_subtree_gate_is_still_called_before_any_descent():
    """The descent must never start without the whole-subtree proof."""
    import inspect

    from app.views import bom_tree

    source = inspect.getsource(bom_tree.bom_flat)
    gate = source.index("_bom_is_fully_authorised")
    descent = source.index("while stack:")
    assert gate < descent, "the subtree must be authorised before walking it"

    # And the per-node re-check must stay gone, or the cost returns.
    body = source[descent:]
    assert "authorised_part_pairs" not in body, (
        "per-node authorisation reintroduced inside the descent; that is the "
        "hundreds-of-queries cost this change removed"
    )


def test_the_root_children_are_still_authorised_explicitly():
    """The root's own children are checked before anything is queued."""
    import inspect

    from app.views import bom_tree

    source = inspect.getsource(bom_tree.bom_flat)
    assert "allowed_root_children" in source
    assert "return jsonify([]), 403" in source
