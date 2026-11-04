"""Mapper rules on a tiny hand-made snapshot where the answers are obvious."""

from mapper import model as m

SNAP = {
    "occupations": [
        {"code": "43-3031.00", "title": "Bookkeeping, Accounting, and Auditing Clerks", "desc": "Keep financial records.",
         "alt": ["Bookkeeper", "Accounts Clerk"],
         "tasks": [[1, "Reconcile bank statements and accounts.", True], [2, "Prepare invoices for customers.", True],
                   [3, "Answer phones.", False]]},
        {"code": "23-2011.00", "title": "Paralegals and Legal Assistants", "desc": "Assist lawyers.",
         "alt": ["Legal Assistant"], "tasks": [[4, "Prepare legal documents and briefs.", True]]},
    ],
    "aei": {"1": {"global_pct": 0.26, "za_pct": 0.29, "global_auto": 49.0, "global_aug": 51.0},
            "3": {"global_pct": 0.0}},
}


def mapper():
    return m.Mapper(SNAP)


def test_words_fold_plurals_and_drop_job_ad_filler():
    assert m.words("Strong experience reconciling bank statements") == ["reconciling", "bank", "statement"]


def test_search_by_title_and_alternate_title():
    mp = mapper()
    assert mp.occ[mp.search("Bookkeeper")[0][0]]["code"] == "43-3031.00"
    assert mp.occ[mp.search("legal assistant")[0][0]]["code"] == "23-2011.00"
    assert mp.search("astronaut") == []


def test_tasks_keep_published_zero_and_missing_apart():
    t = mapper().tasks(0)
    by_id = {r["id"]: r for r in t["tasks"]}
    assert by_id[1]["global_pct"] == 0.26 and by_id[1]["za_pct"] == 0.29 and by_id[1]["automation"] == 49.0
    assert by_id[3]["global_pct"] == 0.0          # published, under 0.005%
    assert by_id[2]["global_pct"] is None         # not published
    assert (t["n_tasks"], t["n_published"], t["n_with_share"], t["share_sum"]) == (3, 2, 1, 0.26)
    assert [r["id"] for r in t["tasks"]] == [1, 3, 2]  # highest share first, unpublished last


def test_one_shared_word_is_not_a_match():
    t = mapper().tasks(0, "Invoices. Love dogs.")
    assert t["n_in_ad"] == 0


def test_ad_clauses_split_on_commas_and_and():
    t = mapper().tasks(0, "Duties: reconcile bank statements, prepare customer invoices and answer phones politely.")
    by_id = {r["id"]: r for r in t["tasks"]}
    assert by_id[1]["in_ad"] and by_id[2]["in_ad"]


def test_ad_sentences_mark_matching_tasks():
    t = mapper().tasks(0, "You will reconcile bank statements every month. You must love dogs.")
    by_id = {r["id"]: r for r in t["tasks"]}
    assert by_id[1]["in_ad"] and by_id[1]["ad_sentence"].startswith("You will reconcile")
    assert not by_id[2]["in_ad"] and t["n_in_ad"] == 1


def test_split_is_by_title_and_stable():
    titles = [[f"Title {i}", "43-3031.00"] for i in range(400)]
    test = [t for t, _ in titles if m.is_test(t)]
    assert 150 < len(test) < 250 and test == [t for t, _ in reversed(titles) if m.is_test(t)][::-1]
