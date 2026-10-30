from conftest import GOAL_PLAIN, GOAL_PROMO
from mobile_agent.cli import main

DATA = '{"email": "demo@shoplite.test", "password": "secret123", "promo": "SAVE20"}'


def test_explore_cli_writes_report_and_test(tmp_path):
    assert main(["explore", "--goal", GOAL_PLAIN, "--data", DATA, "--success-text", "Order placed", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "test_generated_flow.py").exists()
    assert "Goal reached: yes" in (tmp_path / "exploration.md").read_text()


def test_explore_cli_exits_nonzero_on_defect(tmp_path):
    assert main(["explore", "--goal", GOAL_PROMO, "--data", DATA, "--success-text", "Order placed", "--out", str(tmp_path)]) == 1
    assert "ERROR_SCREEN" in (tmp_path / "exploration.md").read_text()


def test_heal_demo(tmp_path, capsys):
    assert main(["heal-demo", "--out", str(tmp_path)]) == 0
    assert "submit_signin" in capsys.readouterr().out
