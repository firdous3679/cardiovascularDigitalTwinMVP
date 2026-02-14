from twin.data.uci_loader import load_uci_dataset, normalize_column_name


def test_column_normalization_and_target_mapping(tmp_path):
    csv_file = tmp_path / "mini.csv"
    csv_file.write_text(
        "Age (Years),Chest Pain,target\n"
        "60,asymptomatic,0\n"
        "55,typical angina,3\n",
        encoding="utf-8",
    )

    X, y, pids = load_uci_dataset(str(csv_file))

    assert normalize_column_name("Age (Years)") == "age_years"
    assert list(X[0].keys()) == ["age_years", "chest_pain"]
    assert y == [0, 1]
    assert len(pids) == 2


def test_patient_id_is_deterministic(tmp_path):
    csv_file = tmp_path / "mini.csv"
    csv_file.write_text(
        "age,sex,target\n"
        "63,Male,1\n"
        "63,Male,1\n",
        encoding="utf-8",
    )

    _, _, pids_a = load_uci_dataset(str(csv_file))
    _, _, pids_b = load_uci_dataset(str(csv_file))

    assert pids_a == pids_b
