"""Regressão do ranking diário, isolada do PostgreSQL de produção."""
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["COOKIE_SECURE"] = "false"

from app import app, db, Student, Submission, Award


class DailyRankingTests(unittest.TestCase):
    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
            students = [
                Student(name="Ana Aluna", enrollment="DAILY001", course="ADS"),
                Student(name="Bruno Aluno", enrollment="DAILY002", course="Jogos Digitais"),
            ]
            db.session.add_all(students)
            db.session.commit()
            self.ids = [s.id for s in students]
        self.client = app.test_client()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def add_submission(self, student_index, framework, exercise, timestamp, passed=True):
        with app.app_context():
            db.session.add(Submission(student_id=self.ids[student_index],
                                      framework=framework, exercise=exercise,
                                      variant="top", code="<section>teste</section>",
                                      passed=passed, score=int(passed),
                                      feedback="teste", submitted_at=timestamp))
            db.session.commit()

    def teacher_login(self):
        with self.client.session_transaction() as session:
            session["teacher"] = True

    def test_teacher_authorization_and_invalid_date(self):
        self.assertEqual(self.client.get("/api/teacher/ranking/daily").status_code, 403)
        self.teacher_login()
        self.assertEqual(self.client.get("/api/teacher/ranking/daily?date=10-11-2026").status_code, 400)
        self.assertEqual(self.client.get("/api/teacher/ranking/daily?date=2026-02-30").status_code, 400)
        self.assertEqual(self.client.get("/api/teacher/ranking/daily?date=2026-11-10").status_code, 200)

    def test_fortaleza_midnight_duplicate_attempts_and_next_day(self):
        # 02:59 UTC => 09/11 23:59 em Fortaleza; 03:00 UTC => 10/11 00:00.
        self.add_submission(0, "materialize", 1, datetime(2026, 11, 10, 2, 59, tzinfo=timezone.utc))
        self.add_submission(0, "materialize", 1, datetime(2026, 11, 10, 3, 0, tzinfo=timezone.utc))
        self.add_submission(0, "materialize", 1, datetime(2026, 11, 10, 14, tzinfo=timezone.utc))
        self.add_submission(0, "bootstrap", 1, datetime(2026, 11, 10, 15, tzinfo=timezone.utc))
        self.add_submission(0, "tailwind", 2, datetime(2026, 11, 10, 16, tzinfo=timezone.utc), passed=False)
        self.add_submission(1, "materialize", 4, datetime(2026, 11, 10, 17, tzinfo=timezone.utc))
        self.teacher_login()

        yesterday = self.client.get("/api/teacher/ranking/daily?date=2026-11-09").get_json()
        today = self.client.get("/api/teacher/ranking/daily?date=2026-11-10").get_json()
        tomorrow = self.client.get("/api/teacher/ranking/daily?date=2026-11-11").get_json()
        self.assertEqual(yesterday["ranking"][0]["points"], 1)
        self.assertEqual([row["points"] for row in today["ranking"]], [2, 1])
        self.assertEqual([row["position"] for row in today["ranking"]], [1, 2])
        self.assertEqual(tomorrow["ranking"], [])
        self.assertEqual(today["timezone"], "America/Fortaleza")

    def test_ties_have_same_position_and_original_award_remains_unchanged(self):
        stamp = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
        self.add_submission(0, "materialize", 1, stamp)
        self.add_submission(1, "materialize", 2, stamp)
        with app.app_context():
            db.session.add(Award(student_id=self.ids[0], framework="materialize", exercise=1))
            db.session.commit()
        self.teacher_login()
        result = self.client.get("/api/teacher/ranking/daily?date=2026-11-10").get_json()
        self.assertEqual([row["position"] for row in result["ranking"]], [1, 1])
        with app.app_context():
            self.assertEqual(Award.query.count(), 1)

    def test_teacher_markup_is_scoped_to_results_panel(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="dailyRankingPanel"'), 1)
        self.assertEqual(html.count('id="dailyRankingDate"'), 1)
        self.assertEqual(html.count('id="dailyRankingRows"'), 1)
        self.assertIn("loadDailyRanking();", html)
        self.assertIn("function faTodayFortaleza()", html)
        self.assertIn("function loadDailyRanking()", html)
        self.assertTrue(html.index('id="view-teacher"') < html.index('id="dailyRankingPanel"') < html.index("</main>"))


if __name__ == "__main__":
    unittest.main()
