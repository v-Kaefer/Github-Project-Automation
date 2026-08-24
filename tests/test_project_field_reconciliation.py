from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, patch

from project_setup.project import ensure_fields, single_select_option_inputs, update_single_select_field


class ProjectFieldReconciliationTests(TestCase):
    def test_option_inputs_preserve_matching_option_ids(self):
        existing = {
            "id": "FIELD",
            "options": [
                {"id": "DONE-ID", "name": "Done"},
                {"id": "TODO-ID", "name": "Todo"},
            ],
        }
        desired = {"name": "Status", "type": "single_select", "options": ["In review", "Done"]}

        self.assertEqual(
            single_select_option_inputs(existing, desired),
            [
                {"name": "In review", "color": "GRAY", "description": ""},
                {"name": "Done", "color": "GRAY", "description": "", "id": "DONE-ID"},
            ],
        )

    def test_update_single_select_field_uses_project_v2_field_mutation(self):
        client = Mock()
        client.graphql.return_value = {"updateProjectV2Field": {"projectV2Field": {"id": "FIELD"}}}
        existing = {
            "id": "FIELD",
            "options": [
                {"id": "TODO-ID", "name": "Todo"},
                {"id": "INPROGRESS-ID", "name": "In Progress"},
                {"id": "DONE-ID", "name": "Done"},
            ],
        }
        desired = {"name": "Status", "type": "single_select", "options": ["In progress", "In review", "Done"]}

        update_single_select_field(client, existing, desired)

        query, variables = client.graphql.call_args.args
        self.assertIn("updateProjectV2Field", query)
        self.assertEqual(variables["field"], "FIELD")
        self.assertEqual([item["name"] for item in variables["options"]], ["In progress", "In review", "Done"])
        self.assertEqual(variables["options"][0]["id"], "INPROGRESS-ID")
        self.assertEqual(variables["options"][2]["id"], "DONE-ID")

    @patch("project_setup.project.update_single_select_field")
    @patch("project_setup.project.list_project_fields")
    def test_ensure_fields_reconciles_builtin_status_options(self, list_fields, update_field):
        initial = {
            "__typename": "ProjectV2SingleSelectField",
            "id": "STATUS-FIELD",
            "name": "Status",
            "dataType": "SINGLE_SELECT",
            "options": [
                {"id": "TODO-ID", "name": "Todo"},
                {"id": "INPROGRESS-ID", "name": "In Progress"},
                {"id": "DONE-ID", "name": "Done"},
            ],
        }
        reconciled = {
            **initial,
            "options": [
                {"id": "NEW-PROGRESS", "name": "In progress"},
                {"id": "NEW-REVIEW", "name": "In review"},
                {"id": "DONE-ID", "name": "Done"},
            ],
        }
        list_fields.side_effect = [[initial], [reconciled]]
        definition = {
            "fields": [
                {"name": "Status", "type": "single_select", "options": ["In progress", "In review", "Done"]}
            ]
        }

        result = ensure_fields(Mock(), "PROJECT", definition, dry_run=False)

        update_field.assert_called_once_with(update_field.call_args.args[0], initial, definition["fields"][0])
        self.assertEqual(result["Status"]["options"][1]["name"], "In review")

    @patch("project_setup.project.update_single_select_field")
    @patch("project_setup.project.list_project_fields")
    def test_ensure_fields_keeps_matching_status_idempotent(self, list_fields, update_field):
        current = {
            "__typename": "ProjectV2SingleSelectField",
            "id": "STATUS-FIELD",
            "name": "Status",
            "dataType": "SINGLE_SELECT",
            "options": [
                {"id": "PROGRESS", "name": "In progress"},
                {"id": "REVIEW", "name": "In review"},
                {"id": "DONE", "name": "Done"},
            ],
        }
        list_fields.return_value = [current]
        definition = {
            "fields": [
                {"name": "Status", "type": "single_select", "options": ["In progress", "In review", "Done"]}
            ]
        }

        result = ensure_fields(Mock(), "PROJECT", definition, dry_run=False)

        update_field.assert_not_called()
        self.assertEqual(result["Status"], current)
