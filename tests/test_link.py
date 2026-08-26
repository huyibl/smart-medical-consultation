from smc.rag.link import link_from_hits, link_from_query, link_symptoms


def test_link_头疼_to_头痛():
    assert "头痛" in link_symptoms("最近老是头疼该挂哪科")


def test_link_disease_names_from_query():
    assert "肝炎" in link_from_query("肝炎应该挂哪科")
    assert "支气管炎" in link_from_query("支气管炎应该挂什么科")
    assert "荨麻疹" in link_from_query("荨麻疹应该去什么科室")
    assert "流鼻涕" in link_from_query("流鼻涕该挂哪科")


def test_link_hits_cannot_inject_dizziness():
    hits = [
        {
            "metadata": {"symptom": "头晕", "title": "头晕导诊"},
            "text": "头晕常见神经内科",
        }
    ]
    linked = link_from_hits("肝炎应该挂哪科", hits)
    assert "头晕" not in linked
    assert "肝炎" in linked
