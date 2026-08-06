from __future__ import annotations

from app.agent.intents import AgentIntent, IntentClassifier


def test_classify_empty_message_is_unknown() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("") == AgentIntent.UNKNOWN
    assert classifier.classify("   ") == AgentIntent.UNKNOWN


def test_classify_greetings_are_help() -> None:
    classifier = IntentClassifier()
    for message in ("help", "Help", "aide", "/start", "hello", "bonjour"):
        assert classifier.classify(message) == AgentIntent.HELP


def test_classify_import_resume() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("import resume C:\\resumes\\cv.pdf") == AgentIntent.PROFILE_IMPORT
    assert classifier.classify("import cv from ./cv.docx") == AgentIntent.PROFILE_IMPORT
    assert classifier.classify("importer mon cv") == AgentIntent.PROFILE_IMPORT


def test_classify_profile_status() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("show profile") == AgentIntent.PROFILE_STATUS
    assert classifier.classify("what is my profile status") == AgentIntent.PROFILE_STATUS


def test_classify_discover() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("discover jobs") == AgentIntent.DISCOVER
    assert classifier.classify("find me jobs in germany") == AgentIntent.DISCOVER
    assert classifier.classify("cherche des stages") == AgentIntent.DISCOVER


def test_classify_recommend() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("recommend top 5") == AgentIntent.RECOMMEND
    assert classifier.classify("show me the best matching jobs") == AgentIntent.RECOMMEND


def test_classify_list_recommendations() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("list recommendations") == AgentIntent.LIST_RECOMMENDATIONS
    assert classifier.classify("show my saved recommendations") == AgentIntent.LIST_RECOMMENDATIONS


def test_classify_explain() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("explain job 42") == AgentIntent.AI_EXPLAIN
    assert classifier.classify("pourquoi ce job") == AgentIntent.AI_EXPLAIN


def test_classify_pipeline() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("run the pipeline") == AgentIntent.PIPELINE
    assert classifier.classify("run everything") == AgentIntent.PIPELINE


def test_classify_application_analytics() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("application analytics") == AgentIntent.APPLICATION_ANALYTICS
    assert (
        classifier.classify("how many applications did I submit")
        == AgentIntent.APPLICATION_ANALYTICS
    )


def test_classify_approval_queue() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("approval queue") == AgentIntent.APPROVAL_QUEUE
    assert classifier.classify("what needs my approval") == AgentIntent.APPROVAL_QUEUE


def test_classify_unknown_falls_back() -> None:
    classifier = IntentClassifier()
    assert classifier.classify("the sky is blue today") == AgentIntent.UNKNOWN
