import json
from pathlib import Path

from twin.cli import run_baseline


def test_end_to_end_smoke(tmp_path, monkeypatch):
    csv_file = tmp_path / "mini.csv"
    csv_file.write_text(
        "id,age,sex,cp,trestbps,chol,fbs,restecg,thalch,exang,oldpeak,slope,ca,thal,num\n"
        "1,63,Male,typical angina,145,233,TRUE,lv hypertrophy,150,FALSE,2.3,downsloping,0,fixed defect,0\n"
        "2,67,Male,asymptomatic,160,286,FALSE,lv hypertrophy,108,TRUE,1.5,flat,3,normal,2\n"
        "3,67,Male,asymptomatic,120,229,FALSE,lv hypertrophy,129,TRUE,2.6,flat,2,reversable defect,1\n"
        "4,37,Male,non-anginal,130,250,FALSE,normal,187,FALSE,3.5,downsloping,0,normal,0\n"
        "5,41,Female,atypical angina,130,204,FALSE,lv hypertrophy,172,FALSE,1.4,upsloping,0,normal,0\n"
        "6,56,Male,atypical angina,120,236,FALSE,normal,178,FALSE,0.8,upsloping,0,normal,1\n"
        "7,62,Female,asymptomatic,140,268,FALSE,normal,160,FALSE,3.6,downsloping,2,normal,3\n"
        "8,57,Female,asymptomatic,120,354,FALSE,normal,163,TRUE,0.6,upsloping,0,normal,0\n"
        "9,63,Male,asymptomatic,130,254,FALSE,lv hypertrophy,147,FALSE,1.4,flat,1,reversable defect,2\n"
        "10,53,Male,asymptomatic,140,203,TRUE,lv hypertrophy,155,TRUE,3.1,downsloping,0,reversable defect,1\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    run_baseline(str(csv_file))

    assert Path("data/processed/cohort_features.parquet").exists()
    assert Path("reports/metrics.json").exists()
    assert Path("reports/summary.md").exists()

    metrics = json.loads(Path("reports/metrics.json").read_text(encoding="utf-8"))
    for key in ["auroc", "auprc", "accuracy", "f1", "brier_score"]:
        assert key in metrics
