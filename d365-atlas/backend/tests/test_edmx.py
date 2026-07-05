from app.d365.edmx import parse_edmx


def test_parses_all_document_kinds(sample_edmx):
    docs = parse_edmx(sample_edmx)
    kinds = {d.kind for d in docs}
    assert kinds == {"entity", "enum", "action"}
    assert len([d for d in docs if d.kind == "entity"]) == 5
    assert len([d for d in docs if d.kind == "enum"]) == 2


def test_entity_fields_keys_and_set_resolution(sample_edmx):
    docs = {d.name: d for d in parse_edmx(sample_edmx)}
    journal = docs["LedgerJournalHeader"]
    assert journal.entity_set == "LedgerJournalHeaders"
    assert journal.keys == ["dataAreaId", "JournalBatchNumber"]
    field_names = [f["name"] for f in journal.fields]
    assert "JournalName" in field_names
    assert next(f for f in journal.fields if f["name"] == "dataAreaId")["nullable"] is False


def test_enum_member_decoding(sample_edmx):
    docs = {d.name: d for d in parse_edmx(sample_edmx)}
    status = docs["SalesOrderStatus"]
    assert status.members["Backorder"] == 1
    assert status.members["Invoiced"] == 3


def test_action_parameters(sample_edmx):
    docs = {d.name: d for d in parse_edmx(sample_edmx)}
    action = docs["createJournal"]
    assert action.kind == "action"
    assert action.fields[0]["name"] == "_request"


def test_to_text_is_searchable(sample_edmx):
    docs = {d.name: d for d in parse_edmx(sample_edmx)}
    text = docs["LedgerJournalHeader"].to_text()
    assert "LedgerJournalHeader" in text
    assert "JournalName" in text
