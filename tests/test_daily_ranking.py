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

from app import app, db, Student, Submission, Award, PracticeRun, PracticeEditStart, duration_clock


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

    def test_timer_tracks_session_and_is_preserved_after_refresh(self):
        self.assertEqual(duration_clock(3661), "01:01:01")
        with self.client.session_transaction() as cookie:
            cookie.clear()
        response = self.client.post("/api/student/register", json={
            "name": "Ana Aluna", "enrollment": "DAILY001", "course": "ADS"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get_json()["progress"]["timer_started_at"])
        self.assertIsNone(self.client.get("/api/student/me").get_json()["progress"]["timer_started_at"])
        started_response = self.client.post("/api/student/first-edit")
        self.assertEqual(started_response.status_code, 200)
        started = started_response.get_json()["timer_started_at"]
        self.assertIsNotNone(started)
        self.assertEqual(self.client.post("/api/student/first-edit").get_json()["timer_started_at"], started)
        self.assertEqual(self.client.get("/api/student/me").get_json()["progress"]["timer_started_at"], started)
        with app.app_context():
            run = PracticeRun.query.filter_by(student_id=self.ids[0]).one()
            self.assertIsNotNone(run.started_at)
            self.assertIsNone(run.last_approved_at)
        self.assertEqual(self.client.post("/api/student/logout").status_code, 200)
        with app.app_context():
            self.assertIsNotNone(PracticeRun.query.one().ended_at)
        next_session = self.client.post("/api/student/register", json={
            "name": "Ana Aluna", "enrollment": "DAILY001", "course": "ADS"})
        self.assertEqual(next_session.status_code, 200)
        self.assertIsNone(next_session.get_json()["progress"]["timer_started_at"])
        with app.app_context():
            self.assertEqual(PracticeRun.query.count(), 2)
            self.assertEqual(PracticeEditStart.query.count(), 1)

    def test_ranking_includes_measured_time_and_sums_daily_sessions(self):
        # Cria uma sessão por aluno, com duração conhecida e mesma pontuação.
        start = datetime.combine(self.day, time(10, 0), tzinfo=ZoneInfo("America/Fortaleza")).astimezone(timezone.utc)
        self.add_submission(0, "materialize", 1, start + timedelta(minutes=9))
        self.add_submission(1, "bootstrap", 2, start + timedelta(minutes=5))
        with app.app_context():
            db.session.add_all([
                PracticeRun(student_id=self.ids[0], started_at=start,
                            last_approved_at=start + timedelta(minutes=9)),
                PracticeRun(student_id=self.ids[1], started_at=start,
                            last_approved_at=start + timedelta(minutes=5))
            ])
            db.session.flush()
            for run in PracticeRun.query.all():
                db.session.add(PracticeEditStart(run_id=run.id, edited_at=run.started_at))
            db.session.commit()
        self.login_student()
        ranked = self.client.get("/api/ranking/today").get_json()["ranking"]
        self.assertEqual([item["name"] for item in ranked], ["Bruno Aluno", "Ana Aluna"])
        self.assertEqual([item["points"] for item in ranked], [1, 1])
        self.assertEqual([item["duration"] for item in ranked], ["00:05:00", "00:09:00"])
        self.assertEqual([item["duration_seconds"] for item in ranked], [300, 540])
        with app.app_context():
            run = PracticeRun(student_id=self.ids[0],
                              started_at=start + timedelta(hours=1),
                              last_approved_at=start + timedelta(hours=1, minutes=3))
            db.session.add(run)
            db.session.flush()
            db.session.add(PracticeEditStart(run_id=run.id, edited_at=run.started_at))
            db.session.commit()
        ranked = self.client.get("/api/ranking/today").get_json()["ranking"]
        ana = next(item for item in ranked if item["student_id"] == self.ids[0])
        self.assertEqual(ana["duration_seconds"], 720)

    def test_old_scores_without_timer_are_not_assigned_false_zero(self):
        self.add_submission(0, "materialize", 1, datetime.now(timezone.utc))
        self.login_student()
        result = self.client.get("/api/ranking/today").get_json()["ranking"]
        self.assertEqual(result[0]["duration"], "—")
        self.assertIsNone(result[0]["duration_seconds"])

    def test_ranking_is_own_menu_tab_without_history_picker(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('id="rankingNav"'), 1)
        self.assertIn('data-view="ranking" id="rankingNav" hidden', html)
        self.assertEqual(html.count('id="view-ranking"'), 1)
        self.assertEqual(html.count('id="rankingTodayRows"'), 1)
        self.assertEqual(html.count('id="practiceTimer"'), 1)
        self.assertIn("Tempo de implementação", html)
        self.assertIn("faUpdatePracticeTimer()", html)
        self.assertNotIn('id="dailyRankingPanel"', html)
        self.assertNotIn('id="dailyRankingDate"', html)
        self.assertIn("document.getElementById('rankingNav').hidden=false", html)
        self.assertIn("document.getElementById('rankingNav').addEventListener('click',loadStudentRanking)", html)
        self.assertTrue(html.index('id="view-ranking"') < html.index('id="view-teacher"'))


if __name__ == "__main__":
    unittest.main()
