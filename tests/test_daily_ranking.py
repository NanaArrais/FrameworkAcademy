"""Testes do ranking diário visível somente para alunos identificados."""
import os
import sys
import unittest
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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
        self.day = datetime.now(ZoneInfo("America/Fortaleza")).date()

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

    def login_student(self, index=0):
        with self.client.session_transaction() as session:
            session["student_id"] = self.ids[index]

    def test_only_logged_students_can_view_ranking(self):
        self.assertEqual(self.client.get("/api/ranking/today").status_code, 401)
        with self.client.session_transaction() as session:
            session["teacher"] = True
        self.assertEqual(self.client.get("/api/ranking/today").status_code, 401)
        self.login_student()
        response = self.client.get("/api/ranking/today")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["date"], self.day.isoformat())

    def test_only_today_even_when_date_query_is_supplied(self):
        self.login_student()
        response = self.client.get("/api/ranking/today?date=2020-01-01")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["date"], self.day.isoformat())
        self.assertEqual(response.get_json()["timezone"], "America/Fortaleza")

    def test_fortaleza_midnight_duplicates_and_failed_attempts(self):
        start = datetime.combine(self.day, time.min, tzinfo=ZoneInfo("America/Fortaleza")).astimezone(timezone.utc)
        self.add_submission(0, "materialize", 1, start - timedelta(minutes=1))
        self.add_submission(0, "materialize", 1, start)
        self.add_submission(0, "materialize", 1, start + timedelta(hours=1))
        self.add_submission(0, "bootstrap", 1, start + timedelta(hours=2))
        self.add_submission(0, "tailwind", 2, start + timedelta(hours=3), passed=False)
        self.add_submission(1, "materialize", 4, start + timedelta(hours=4))
        self.login_student()
        ranked = self.client.get("/api/ranking/today").get_json()["ranking"]
        self.assertEqual([item["points"] for item in ranked], [2, 1])
        self.assertEqual([item["position"] for item in ranked], [1, 2])

    def test_ties_and_accumulated_awards_unchanged(self):
        stamp = datetime.now(timezone.utc)
        self.add_submission(0, "materialize", 1, stamp)
        self.add_submission(1, "materialize", 2, stamp)
        with app.app_context():
            db.session.add(Award(student_id=self.ids[0], framework="materialize", exercise=1))
            db.session.commit()
        self.login_student()
        ranked = self.client.get("/api/ranking/today").get_json()["ranking"]
        self.assertEqual([item["position"] for item in ranked], [1, 1])
        with app.app_context():
            self.assertEqual(Award.query.count(), 1)

    def test_ranking_is_own_menu_tab_without_history_picker(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="rankingNav"'), 1)
        self.assertIn('data-view="ranking" id="rankingNav" hidden', html)
        self.assertEqual(html.count('id="view-ranking"'), 1)
        self.assertEqual(html.count('id="rankingTodayRows"'), 1)
        self.assertNotIn('id="dailyRankingPanel"', html)
        self.assertNotIn('id="dailyRankingDate"', html)
        self.assertIn("document.getElementById('rankingNav').hidden=false", html)
        self.assertIn("document.getElementById('rankingNav').addEventListener('click',loadStudentRanking)", html)
        self.assertTrue(html.index('id="view-ranking"') < html.index('id="view-teacher"'))


if __name__ == "__main__":
    unittest.main()
