"""Regressões isoladas: perfil do aluno, compatibilidade e sessão docente."""
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["COOKIE_SECURE"] = "false"

from app import app, db, Student, Award, Submission, PracticeRun

COURSES = ("Engenharia da Computação", "Análise e Desenvolvimento de Sistemas")


class ProfileAndTeacherSessionTests(unittest.TestCase):
    def setUp(self):
        self.previous_teacher_hash = os.environ.get("TEACHER_PASSWORD_HASH")
        os.environ["TEACHER_PASSWORD_HASH"] = generate_password_hash("senha-apenas-de-teste")
        with app.app_context():
            db.drop_all()
            db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        if self.previous_teacher_hash is None:
            os.environ.pop("TEACHER_PASSWORD_HASH", None)
        else:
            os.environ["TEACHER_PASSWORD_HASH"] = self.previous_teacher_hash

    def test_two_allowed_courses_and_invalid_course(self):
        for i, course in enumerate(COURSES):
            response = self.client.post("/api/student/register", json={
                "name": "Aluno de Teste", "enrollment": f"NEW{i:03}", "course": course})
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["student"]["course"], course)
        self.assertEqual(self.client.post("/api/student/register", json={
            "name": "Aluno inválido", "enrollment": "INVALID", "course": "Outro"}).status_code, 400)

    def test_legacy_course_login_without_modifying_student_or_scores(self):
        with app.app_context():
            student = Student(name="Estudante Legado", enrollment="LEGACY001", course="ADS")
            db.session.add(student)
            db.session.flush()
            student_id = student.id
            db.session.add(Award(student_id=student_id, framework="materialize", exercise=1))
            db.session.add(Submission(student_id=student_id, framework="materialize",
                          exercise=1, variant="top", code="<h1>Original</h1>",
                          passed=True, score=1, feedback="Concluído", submitted_at=datetime.now(timezone.utc)))
            db.session.commit()
        response = self.client.post("/api/student/register", json={
            "name": "Estudante Legado", "enrollment": "LEGACY001",
            "course": COURSES[1]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["student"]["course"], "ADS")
        with app.app_context():
            student = db.session.get(Student, student_id)
            self.assertEqual(student.course, "ADS")
            self.assertEqual(Student.query.count(), 1)
            self.assertEqual(Award.query.count(), 1)
            self.assertEqual(Submission.query.count(), 1)

    def test_edit_profile_keeps_id_enrollment_progress_and_active_run(self):
        response = self.client.post("/api/student/register", json={
            "name": "Aluna Inicial", "enrollment": "EDIT0001", "course": COURSES[1]})
        self.assertEqual(response.status_code, 200)
        original_run_id = response.get_json()["progress"]["run_id"]
        with app.app_context():
            student = Student.query.filter_by(enrollment="EDIT0001").one()
            student_id = student.id
            db.session.add(Award(student_id=student_id, framework="materialize", exercise=1))
            db.session.add(Submission(student_id=student_id, framework="materialize",
                          exercise=1, variant="top", code="<h1>Original</h1>",
                          passed=True, score=1, feedback="Concluído", submitted_at=datetime.now(timezone.utc)))
            db.session.commit()
        updated = self.client.patch("/api/student/profile",
                    json={"name": "Aluna Atualizada", "course": COURSES[0], "enrollment": "OUTRA"})
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["student"]["enrollment"], "EDIT0001")
        me = self.client.get("/api/student/me").get_json()
        self.assertEqual(me["student"]["name"], "Aluna Atualizada")
        self.assertEqual(me["student"]["course"], COURSES[0])
        self.assertEqual(me["progress"]["run_id"], original_run_id)
        with app.app_context():
            student = Student.query.filter_by(enrollment="EDIT0001").one()
            self.assertEqual(student.id, student_id)
            self.assertEqual(Student.query.count(), 1)
            self.assertEqual(Award.query.filter_by(student_id=student_id).count(), 1)
            self.assertEqual(Submission.query.filter_by(student_id=student_id).count(), 1)
            self.assertEqual(PracticeRun.query.filter_by(student_id=student_id).count(), 1)

    def test_profile_requires_session_and_rejects_invalid_values(self):
        self.assertEqual(self.client.patch("/api/student/profile",
                        json={"name": "Outra pessoa", "course": COURSES[0]}).status_code, 401)
        self.client.post("/api/student/register", json={
            "name": "Aluno Original", "enrollment": "PROF001", "course": COURSES[0]})
        for data in ({"name": "A", "course": COURSES[0]},
                     {"name": "Aluno Original", "course": "Curso não listado"}):
            self.assertEqual(self.client.patch("/api/student/profile", json=data).status_code, 400)
        self.assertEqual(self.client.get("/api/student/me").get_json()["student"]["name"], "Aluno Original")

    def test_teacher_login_survives_switching_tabs_and_page_refresh(self):
        self.assertEqual(self.client.get("/api/teacher/results").status_code, 403)
        login = self.client.post("/api/teacher/login", json={"password": "senha-apenas-de-teste"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(self.client.get("/api/teacher/results").status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/teacher/results").status_code, 200)
        self.assertEqual(self.client.get("/api/teacher/export.csv").status_code, 200)
        self.assertEqual(self.client.post("/api/teacher/logout").status_code, 200)
        self.assertEqual(self.client.get("/api/teacher/results").status_code, 403)

    def test_frontend_retains_teacher_session_and_profile_controls(self):
        html=(ROOT/"templates"/"index.html").read_text(encoding="utf-8")
        self.assertIn('id="studentEditProfile"', html)
        self.assertIn('id="studentProfileForm"', html)
        self.assertIn('id="profileEnrollment" readonly', html)
        self.assertIn('id="registerCourse" name="course" required', html)
        self.assertIn("document.querySelector('[data-view=\"teacher\"]').addEventListener('click',loadTeacherResults);",html)
        self.assertNotIn("Toda entrada no painel exige nova autenticação",html)


if __name__=="__main__":
    unittest.main()
