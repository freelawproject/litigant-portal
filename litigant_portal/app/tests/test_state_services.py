from concurrent.futures import ThreadPoolExecutor

import pytest
from django.core.exceptions import ValidationError
from django.db import OperationalError, connections, transaction
from django.db.models.signals import pre_save

from litigant_portal.app.models import (
    FlowViewState,
    Topic,
    TopicFlow,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.services.topic_flow import (
    topic_flow_section_viewed,
    variable_answer_set,
    variable_answer_set_many,
)
from litigant_portal.app.services.user import (
    user_identity_merge,
    user_identity_reset,
)


@pytest.mark.postgres
@pytest.mark.django_db(transaction=True)
def test_fact_writes_lock_the_identity_before_persisting():
    identity = UserIdentity.objects.create(session_key="state-lock")
    variable = Variable.objects.create(name="county")

    def identity_is_locked() -> bool:
        try:
            with transaction.atomic():
                UserIdentity.objects.select_for_update(nowait=True).get(
                    pk=identity.pk
                )
        except OperationalError as error:
            assert error.__cause__.sqlstate == "55P03"
            return True
        finally:
            connections.close_all()
        return False

    with ThreadPoolExecutor(max_workers=1) as pool:

        def check_lock(**kwargs) -> None:
            assert pool.submit(identity_is_locked).result(timeout=5)

        pre_save.connect(check_lock, sender=VariableAnswer)
        try:
            variable_answer_set(
                identity=identity, variable=variable, value="Cass"
            )
        finally:
            pre_save.disconnect(check_lock, sender=VariableAnswer)


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_bad_fact_rolls_back_the_whole_service_batch():
    identity = UserIdentity.objects.create(session_key="state-batch")
    county = Variable.objects.create(name="county")
    Variable.objects.create(name="age", data_type="number")
    variable_answer_set(identity=identity, variable=county, value="Cass")

    with pytest.raises(ValidationError):
        variable_answer_set_many(
            identity=identity, values={"county": "Burleigh", "age": "invalid"}
        )

    assert list(identity.variable_answers.values_list("value", flat=True)) == [
        "Cass"
    ]


@pytest.mark.postgres
@pytest.mark.django_db
def test_viewing_state_survives_fact_writes_and_follows_identity_lifecycle():
    topic = Topic.objects.create(slug="name-change", title="Name change")
    flow = TopicFlow.objects.create(
        topic=topic, slug="standard", name="Standard"
    )
    other_flow = TopicFlow.objects.create(
        topic=topic, slug="waiver", name="Waiver"
    )
    source = UserIdentity.objects.create(session_key="view-source")
    target = UserIdentity.objects.create(session_key="view-target")
    county = Variable.objects.create(name="county")
    for identity, selected_flow, signature in (
        (source, flow, "a"),
        (source, other_flow, "b"),
        (target, flow, "c"),
    ):
        topic_flow_section_viewed(
            identity=identity,
            flow=selected_flow,
            component_id="overview",
            signature=signature * 64,
        )
    variable_answer_set(identity=source, variable=county, value="Cass")
    assert source.flow_views.get(flow=flow).viewed == {"overview": "a" * 64}
    assert target.flow_views.get(flow=flow).viewed == {"overview": "c" * 64}

    user_identity_merge(source_identity=source, target_identity=target)

    assert target.flow_views.get(flow=flow).viewed == {"overview": "c" * 64}
    assert target.flow_views.get(flow=other_flow).viewed == {
        "overview": "b" * 64
    }
    assert target.variable_answers.get(variable=county).value == "Cass"
    user_identity_reset(identity=target)
    assert not target.flow_views.exists()
    assert not target.variable_answers.exists()
    topic_flow_section_viewed(
        identity=target, flow=flow, component_id="overview", signature="d" * 64
    )
    target.delete()
    assert not FlowViewState.objects.exists()
