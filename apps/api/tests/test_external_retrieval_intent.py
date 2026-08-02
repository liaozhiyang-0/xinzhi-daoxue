from app.contracts.agent import AgentRequest, Intent
from app.contracts.external_retrieval import ExternalRetrievalPolicy
from app.core.config import Settings
from app.services.external_retrieval_intent import ExternalRetrievalIntentRecognizer


def _request(text: str, intent: Intent = Intent.SOLVE_PROBLEM) -> AgentRequest:
    return AgentRequest(
        session_id="session-intent",
        user_id="user-intent",
        intent=intent,
        canonical_input={"text": text},
    )


def test_external_retrieval_is_enabled_by_default_but_intent_gate_is_on() -> None:
    settings = Settings(app_env="test", _env_file=None)

    assert settings.external_retrieval_enabled is True
    assert settings.external_retrieval_intent_gate_enabled is True


def test_research_and_freshness_signals_allow_external_retrieval() -> None:
    recognizer = ExternalRetrievalIntentRecognizer()
    policy = ExternalRetrievalPolicy(enabled=True, source_scopes=["academic"])

    decision = recognizer.classify(_request("请检索最新的信号处理研究论文"), policy)

    assert decision.decision == "retrieve"
    assert decision.category in {"explicit_request", "research", "freshness"}
    assert "research_or_literature_request" in decision.reason_codes


def test_generic_explanation_and_pure_problem_solving_skip_external_retrieval() -> None:
    recognizer = ExternalRetrievalIntentRecognizer()
    policy = ExternalRetrievalPolicy(enabled=True, source_scopes=["web"])

    explanation = recognizer.classify(_request("请解释电容电压为什么不能突变"), policy)
    problem = recognizer.classify(
        _request("判断二极管当前工作状态并给出计算过程"), policy
    )

    assert explanation.decision == "skip"
    assert problem.decision == "skip"
    assert explanation.reason_codes == ["no_external_intent"]


def test_policy_can_allow_research_agent_intent_without_keyword() -> None:
    recognizer = ExternalRetrievalIntentRecognizer()
    policy = ExternalRetrievalPolicy(
        enabled=True,
        source_scopes=["academic"],
        intent_allowlist=["academic_writing"],
    )

    decision = recognizer.classify(
        _request("根据已有材料规划论文结构", Intent.ACADEMIC_WRITING),
        policy,
    )

    assert decision.decision == "retrieve"
    assert decision.category == "agent_intent"
    assert "allowlisted_agent_intent" in decision.reason_codes


def test_explicit_web_request_is_retrieved_even_for_general_question() -> None:
    recognizer = ExternalRetrievalIntentRecognizer()
    policy = ExternalRetrievalPolicy(enabled=True, source_scopes=["web"])

    decision = recognizer.classify(
        _request("请联网搜索官方文档并给出来源链接", Intent.GENERAL_QA), policy
    )

    assert decision.decision == "retrieve"
    assert decision.category == "explicit_request"
