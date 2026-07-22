import copy
import json
import unittest
from pathlib import Path

from src.learning_dna.trajectory import (
    migrate_trajectory_to_skill_graph,
    select_next_focus_from_graph,
)
from src.skills.skill_graph import (
    DEFAULT_MAP_PATH,
    SkillMapValidationError,
    load_skill_map,
    select_next_skill,
    validate_skill_map,
)


class EgeSkillMapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_map = load_skill_map()

    def test_map_contains_all_27_tasks_once(self):
        self.assertEqual(
            [task["number"] for task in self.skill_map["tasks"]],
            list(range(1, 28)),
        )

    def test_every_attachment_task_names_real_source_file(self):
        expected = {
            "3": ["1_3.ods"], "9": ["1_9.ods"], "10": ["1_10.odt"],
            "17": ["1_17.txt"], "18": ["1_18.ods"], "22": ["1_22.ods"],
            "24": ["1_24.txt"], "26": ["1_26.txt"],
            "27": ["1_27_A.txt", "1_27_B.txt"],
        }
        self.assertEqual(self.skill_map["source"]["attachments"], expected)

    def test_every_task_has_measurable_evidence_and_error_model(self):
        for task in self.skill_map["tasks"]:
            with self.subTest(task=task["number"]):
                self.assertTrue(task["operations"])
                self.assertTrue(task["typical_errors"])
                self.assertTrue(task["evidence"])
                self.assertGreaterEqual(
                    task["mastery"]["min_independent_attempts"], 2
                )
                self.assertTrue(task["mastery"]["requires_exam_level"])

    def test_all_skill_exam_task_links_are_bidirectional(self):
        tasks = {task["number"]: set(task["skills"]) for task in self.skill_map["tasks"]}
        for skill in self.skill_map["skills"]:
            for task_number in skill["exam_tasks"]:
                with self.subTest(skill=skill["id"], task=task_number):
                    self.assertIn(skill["id"], tasks[task_number])

    def test_validator_rejects_prerequisite_cycle(self):
        broken = copy.deepcopy(self.skill_map)
        broken["skills"][0]["prerequisites"] = [broken["skills"][-1]["id"]]
        broken["skills"][-1]["prerequisites"] = [broken["skills"][0]["id"]]
        with self.assertRaises(SkillMapValidationError):
            validate_skill_map(broken)

    def test_map_file_is_valid_utf8_json(self):
        parsed = json.loads(Path(DEFAULT_MAP_PATH).read_text(encoding="utf-8"))
        self.assertEqual(parsed["schema_version"], 1)


class SkillGraphTrajectoryTest(unittest.TestCase):
    def test_initial_focus_is_first_high_priority_available_skill(self):
        self.assertEqual(select_next_skill({}), "information.units_conversion")

    def test_prerequisite_blocks_advanced_skill(self):
        states = {
            "information.units_conversion": {
                "mastered": True,
                "mastery_level": 100,
                "evidence_count": 2,
                "difficulty_max": "exam_level",
            }
        }
        self.assertEqual(select_next_skill(states), "number_systems.base_conversion")

    def test_legacy_algorithms_focus_migrates_to_atomic_skill(self):
        dna = {
            "trajectory": {"next_focus": "Алгоритмы и исполнители"},
            "skills": {},
        }
        changed = migrate_trajectory_to_skill_graph(dna)
        self.assertTrue(changed)
        self.assertEqual(
            dna["trajectory"]["next_focus_skill_id"], "algorithms.tracing"
        )
        self.assertEqual(dna["trajectory"]["next_focus"], "Алгоритмы и исполнители")

    def test_mastered_legacy_topics_become_evidence_backed_skills(self):
        dna = {
            "trajectory": {"next_focus": None},
            "topic_mastery": {
                "Системы счисления": {"mastered": True},
                "Основы логики": {"mastered": True},
            },
            "skills": {},
        }
        migrate_trajectory_to_skill_graph(dna)
        self.assertTrue(dna["skills"]["number_systems.base_conversion"]["mastered"])
        self.assertTrue(dna["skills"]["logic.operations"]["mastered"])
        self.assertEqual(
            dna["skills"]["logic.operations"]["difficulty_max"], "exam_level"
        )

    def test_next_focus_uses_graph_not_legacy_linear_sequence(self):
        dna = {
            "trajectory": {"next_focus": None},
            "skills": {
                "information.units_conversion": {"mastered": True},
                "number_systems.base_conversion": {"mastered": True},
                "logic.operations": {"mastered": True},
            },
        }
        self.assertEqual(select_next_focus_from_graph(dna), "algorithms.tracing")


if __name__ == "__main__":
    unittest.main()
