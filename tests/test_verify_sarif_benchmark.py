from scripts.verify_sarif_benchmark import verify


def case(expected, actual):
    classification = ("TP" if actual else "FN") if expected else ("FP" if actual else "TN")
    return {"expected_visible": expected, "actual_visible": actual,
            "classification": classification,
            "status": "PASSED" if classification in ("TP", "TN") else "FAILED"}


def payload(results):
    tp = sum(x["classification"] == "TP" for x in results)
    fp = sum(x["classification"] == "FP" for x in results)
    fn = sum(x["classification"] == "FN" for x in results)
    tn = sum(x["classification"] == "TN" for x in results)
    return {"results": results, "results_summary": {
        "cases": len(results), "true_positives": tp, "false_positives": fp,
        "false_negatives": fn, "true_negatives": tn,
        "passed": tp + tn, "failed": fp + fn}}


def test_accepts_labeled_positive_and_negative_controls():
    assert verify(payload([case(True, True), case(False, False)])) == []


def test_rejects_false_positive_and_false_negative():
    errors = verify(payload([case(True, False), case(False, True)]))
    assert any("regression" in error for error in errors)


def test_rejects_fabricated_summary():
    item = payload([case(True, True), case(False, False)])
    item["results_summary"]["passed"] = 999
    assert any("summary passed" in error for error in verify(item))


def test_rejects_mislabeled_case():
    item = payload([case(True, True), case(False, False)])
    item["results"][0]["classification"] = "TN"
    assert any("inconsistent classification" in error for error in verify(item))


def test_rejects_empty_benchmark():
    assert verify(payload([]))


def test_rejects_missing_negative_control():
    assert any("negative controls" in e for e in verify(payload([case(True, True)])))
