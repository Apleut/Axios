from types import SimpleNamespace

from axios.moderation.ban import build_audit_reason, outranks


# stand-in member with only the attributes outranks() reads
def make_member(member_id: int, top_role: int, owner_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=member_id,
        top_role=top_role,
        guild=SimpleNamespace(owner_id=owner_id),
    )


# stand-in moderator whose string form is a username, like a real discord user
class FakeModerator:
    id = 42

    def __str__(self) -> str:
        return "moduser"


def test_owner_outranks_everyone_even_with_a_lower_role():
    owner = make_member(member_id=1, top_role=1, owner_id=1)
    target = make_member(member_id=2, top_role=10, owner_id=1)

    assert outranks(owner, target) is True


def test_higher_role_outranks_lower_role():
    actor = make_member(member_id=2, top_role=5)
    target = make_member(member_id=3, top_role=2)

    assert outranks(actor, target) is True


def test_equal_roles_do_not_outrank():
    actor = make_member(member_id=2, top_role=5)
    target = make_member(member_id=3, top_role=5)

    assert outranks(actor, target) is False


def test_lower_role_does_not_outrank_higher_role():
    actor = make_member(member_id=2, top_role=2)
    target = make_member(member_id=3, top_role=5)

    assert outranks(actor, target) is False


def test_audit_reason_includes_moderator_and_reason():
    reason = build_audit_reason(FakeModerator(), "spamming links")

    assert reason == "moduser (ID: 42): spamming links"


def test_audit_reason_has_a_default_when_none_is_given():
    reason = build_audit_reason(FakeModerator(), None)

    assert reason.endswith("No reason provided.")


def test_audit_reason_is_capped_at_discords_limit():
    reason = build_audit_reason(FakeModerator(), "x" * 1000)

    assert len(reason) == 512
