from src.pedagogy.observations import build_observation_from_check
from src.pedagogy.evidence import build_evidence
from src.pedagogy.reasoning import build_reasoning
from src.pedagogy.decisions import build_decision
from src.pedagogy.actions import build_action_plan


def make_pedagogical_decision(check_result: dict, learning_dna: dict | None) -> dict:
    observation = build_observation_from_check(check_result)
    evidence = build_evidence(observation, learning_dna)
    reasoning = build_reasoning(observation, evidence)
    decision = build_decision(observation, evidence)
    action_plan = build_action_plan(decision)

    return {
        "observation": observation,
        "evidence": evidence,
        "reasoning": reasoning,
        "decision": decision,
        "action_plan": action_plan,
    }