"""Tests for the simulate domain: simulated users, their identity-backed
state, the actor agent, and the admin API surface.

The design invariant worth guarding: a simulated user IS a UserIdentity,
so the assistant's machinery (uploads, flow answers, threads) works for a
simulation without special cases, and deleting the identity removes
everything the simulation created.
"""

import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfWriter

from litigant_portal.agents import LitigantAssistant, SimulatedLitigant
from litigant_portal.agents.tools.simulate import AttachUpload, EndConversation
from litigant_portal.app.models import (
    ChatThread,
    SimulatedUser,
    Topic,
    TopicFlow,
    TopicFlowField,
    TopicFlowFieldGroup,
    UserIdentity,
    UserUpload,
)
from litigant_portal.app.services.simulate import (
    SIMULATION_ACTOR_THREAD_TYPE,
    SIMULATION_THREAD_TYPE,
    simulated_user_create,
    simulated_user_delete,
    simulation_run_create,
)
from litigant_portal.app.services.topic_flow import topic_flow_answers_update
from litigant_portal.app.services.upload import user_upload_create


def _pdf_file(name="notice.pdf"):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return SimpleUploadedFile(name, buffer.getvalue(), "application/pdf")


class SimulatedUserServiceTests(TestCase):
    def test_create_makes_backing_identity(self):
        sim = simulated_user_create(name="Jane", story="Facing eviction.")
        self.assertIsInstance(sim.identity, UserIdentity)
        self.assertEqual(sim.identity.simulated_user, sim)

    def test_delete_cascades_everything(self):
        sim = simulated_user_create(name="Jane")
        run = simulation_run_create(sim=sim)
        upload = user_upload_create(identity=sim.identity, file=_pdf_file())
        storage, file_name = upload.file.storage, upload.file.name
        self.assertTrue(storage.exists(file_name))
        simulated_user_delete(sim=sim)
        # Rows cascade via the identity; the stored file must go explicitly.
        self.assertFalse(storage.exists(file_name))
        self.assertFalse(SimulatedUser.objects.exists())
        self.assertFalse(
            UserIdentity.objects.filter(id=sim.identity_id).exists()
        )
        self.assertFalse(
            ChatThread.objects.filter(
                id__in=[
                    run["assistant_thread_id"],
                    run["actor_thread_id"],
                ]
            ).exists()
        )
        self.assertFalse(UserUpload.objects.filter(id=upload.id).exists())

    def test_run_create_links_thread_pair(self):
        sim = simulated_user_create(name="Jane")
        run = simulation_run_create(sim=sim)
        assistant = ChatThread.objects.get(id=run["assistant_thread_id"])
        actor = ChatThread.objects.get(id=run["actor_thread_id"])
        self.assertEqual(assistant.thread_type, SIMULATION_THREAD_TYPE)
        self.assertEqual(actor.thread_type, SIMULATION_ACTOR_THREAD_TYPE)
        self.assertEqual(assistant.identity, sim.identity)
        self.assertEqual(actor.identity, sim.identity)
        self.assertEqual(assistant.state["actor_thread_id"], str(actor.id))
        self.assertEqual(actor.state["assistant_thread_id"], str(assistant.id))


class SimulatedLitigantAgentTests(TestCase):
    def setUp(self):
        self.sim = simulated_user_create(
            name="Jane Roe", story="Landlord filed for eviction last week."
        )
        self.thread = ChatThread.objects.create(
            identity=self.sim.identity,
            thread_type=SIMULATION_ACTOR_THREAD_TYPE,
        )

    def test_prompt_contains_persona_and_documents(self):
        upload = user_upload_create(
            identity=self.sim.identity, file=_pdf_file("summons.pdf")
        )
        prompt = SimulatedLitigant().generate_system_prompt(
            thread_id=self.thread.id
        )
        self.assertIn("Jane Roe", prompt)
        self.assertIn("Landlord filed for eviction", prompt)
        self.assertIn("summons.pdf", prompt)
        self.assertIn(str(upload.id), prompt)

    def test_attach_upload_validates_ownership(self):
        other = UserIdentity.objects.create(session_key="other")
        foreign = user_upload_create(identity=other, file=_pdf_file())
        output = AttachUpload(upload_ids=[str(foreign.id)])(
            thread_id=self.thread.id
        )
        self.assertIn("Error", output.result)
        self.assertIsNone(output.render_data)

    def test_attach_upload_returns_render_data(self):
        upload = user_upload_create(
            identity=self.sim.identity, file=_pdf_file("lease.pdf")
        )
        output = AttachUpload(upload_ids=[str(upload.id)])(
            thread_id=self.thread.id
        )
        self.assertEqual(output.render_data["upload_ids"], [str(upload.id)])
        self.assertEqual(output.render_data["names"], ["lease.pdf"])

    def test_end_conversation_reports_reason(self):
        output = EndConversation(reason="Needs met")(thread_id=self.thread.id)
        self.assertEqual(output.render_data["reason"], "Needs met")

    def test_agent_prompts_never_cross(self):
        """The two sides of a run share an identity but must never share
        prompt text: the actor gets no assistant instructions, and the
        assistant gets no persona."""
        actor_prompt = SimulatedLitigant().generate_system_prompt(
            thread_id=self.thread.id
        )
        self.assertNotIn("compassionate legal assistant", actor_prompt)
        self.assertNotIn("GUIDES (TOPIC FLOWS)", actor_prompt)
        self.assertNotIn("CONVERSATION STAGES", actor_prompt)
        self.assertIn("playing a PERSON", actor_prompt)

        assistant_thread = ChatThread.objects.create(
            identity=self.sim.identity,
            thread_type=SIMULATION_THREAD_TYPE,
        )
        assistant_prompt = LitigantAssistant().generate_system_prompt(
            thread_id=assistant_thread.id
        )
        self.assertIn("compassionate legal assistant", assistant_prompt)
        self.assertNotIn("playing a PERSON", assistant_prompt)
        self.assertNotIn("Jane Roe", assistant_prompt)
        self.assertNotIn(self.sim.story, assistant_prompt)


class SimulateApiPermissionTests(TestCase):
    def setUp(self):
        self.sim = simulated_user_create(name="Jane")
        self.list_url = reverse("simulate_api:user_list")

    def _login_admin(self):
        user = get_user_model().objects.create_user(
            username="admin", password="pw"
        )
        user.user_permissions.add(
            Permission.objects.get(codename="manage_site")
        )
        self.client.force_login(user)
        return user

    def test_anonymous_is_forbidden(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_plain_user_is_forbidden(self):
        user = get_user_model().objects.create_user(
            username="plain", password="pw"
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_admin_can_list_and_create(self):
        self._login_admin()
        data = self.client.get(self.list_url).json()
        self.assertEqual(
            [row["name"] for row in data["simulated_users"]], ["Jane"]
        )
        created = self.client.post(
            reverse("simulate_api:user_create"),
            data='{"name": "Sam", "story": "Small claims."}',
            content_type="application/json",
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(SimulatedUser.objects.count(), 2)

    def test_admin_upload_scopes_to_sim_identity(self):
        self._login_admin()
        res = self.client.post(
            reverse(
                "simulate_api:upload_create",
                kwargs={"sim_id": self.sim.id},
            ),
            data={"file": _pdf_file()},
        )
        self.assertEqual(res.status_code, 200)
        upload = UserUpload.objects.get()
        self.assertEqual(upload.identity, self.sim.identity)

    def test_topic_flow_summary_uses_sim_identity(self):
        """The briefcase summary on the simulate tab must reflect the
        simulated user's answers, not the requesting admin's."""
        self._login_admin()
        topic = Topic.objects.create(slug="eviction", title="Eviction")
        flow = TopicFlow.objects.create(
            topic=topic, slug="respond", name="Respond", enabled=True
        )
        group = TopicFlowFieldGroup.objects.create(flow=flow, order=0)
        TopicFlowField.objects.create(
            flow=flow, group=group, name="full_name", data_type="text", order=0
        )
        topic_flow_answers_update(
            identity=self.sim.identity,
            flow=flow,
            answers={"full_name": "Jane"},
            reviewed=False,
        )
        res = self.client.get(
            reverse(
                "simulate_api:topic_flow_summary",
                kwargs={
                    "sim_id": self.sim.id,
                    "topic_slug": "eviction",
                    "flow_slug": "respond",
                },
            )
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["progress"]["answered"], 1)

    def test_run_create_and_list(self):
        self._login_admin()
        created = self.client.post(
            reverse("simulate_api:run_create", kwargs={"sim_id": self.sim.id})
        )
        self.assertEqual(created.status_code, 200)
        run = created.json()["run"]
        listed = self.client.get(
            reverse("simulate_api:run_list", kwargs={"sim_id": self.sim.id})
        ).json()["runs"]
        self.assertEqual(
            listed[0]["assistant_thread_id"], run["assistant_thread_id"]
        )
        self.assertEqual(listed[0]["actor_thread_id"], run["actor_thread_id"])
