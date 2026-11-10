"""Smoke test in a real Chromium browser for the Framework Academy laboratory.

Requires a running Flask application at FA_TEST_URL (default http://127.0.0.1:5300).
Run with: python -m playwright install chromium && python tests/e2e_browser.py
The SQLite instance and student used by CI are disposable.
"""
import os
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.getenv("FA_TEST_URL", "http://127.0.0.1:5300")
NAMES = [
    "Menu de navegação", "Cores e fundo", "Grid responsivo", "Botões de ação",
    "Cards de conteúdo", "Formulários", "Tipografia", "Espaçamento",
    "Imagens responsivas", "Listas e coleções", "Alertas e mensagens",
    "Tabelas", "Alinhamento", "Rodapé",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
    expect(page.locator("#rankingNav")).to_be_hidden()
    page.locator('button[data-view="practice"]').first.click()

    # The new orientation screen appears BEFORE identity and exercises.
    expect(page.locator("#practiceWelcome")).to_be_visible()
    expect(page.locator("#studentGate")).to_be_hidden()
    expect(page.locator("#studentPracticeBody")).to_be_hidden()
    assert "1 ponto" in page.locator("#practiceWelcome").inner_text()
    assert "42 pontos" in page.locator("#practiceWelcome").inner_text()
    assert page.locator("[data-welcome-framework]").count() == 3
    page.locator('[data-welcome-framework="tailwind"]').click()
    expect(page.locator('[data-welcome-framework="tailwind"]')).to_have_attribute("aria-pressed", "true")
    page.locator("#practiceWelcomeStart").click()
    expect(page.locator("#studentGate")).to_be_visible()
    page.locator("#registerName").fill("Estudante de Testes")
    page.locator("#registerEnrollment").fill("E2E000007")
    page.locator("#registerCourse").fill("ADS")
    page.locator('#studentRegisterForm button[type="submit"]').click()
    expect(page.locator("#studentPracticeBody")).to_be_visible(timeout=15000)
    expect(page.locator("#practiceTimer")).to_be_visible()
    assert page.locator("#practiceTimer").inner_text() == "00:00:00"
    # Alternating exercises or viewing examples does not start the clock.

    expect(page.locator("#rankingNav")).to_be_visible()
    page.locator("#rankingNav").click()
    expect(page.locator("#view-ranking")).to_be_visible()
    expect(page.locator("#view-ranking th")).to_contain_text(["Posição","Aluno","Curso","Pontos de hoje","Tempo de implementação"])

    expect(page.locator("#rankingTodayMessage")).to_contain_text("hoje", timeout=15000)
    assert page.locator("#view-ranking input[type=date]").count() == 0
    page.locator('button[data-view="practice"]').first.click()
    expect(page.locator("#studentPracticeBody")).to_be_visible()

    assert page.locator("#lessonFramework").input_value() == "tailwind"

    # Every exercise must open, across all three frameworks, without a JS exception
    # or an empty code editor. A separate test on the backend validates grading.
    checked = 0
    for framework in ("bootstrap", "tailwind", "materialize"):
        page.locator(f'[data-framework-choice="{framework}"]').click()
        assert page.locator("#lessonFramework").input_value() == framework
        for number, title in enumerate(NAMES):
            page.locator(f'[data-lesson="{number}"]').click()
            expect(page.locator("#lessonTitle")).to_have_text(title)
            expect(page.locator("#lessonReferenceContext")).to_contain_text(f"Questão {number + 1:02d}")
            assert page.locator("#lessonCode").input_value().strip().startswith("<!DOCTYPE html>")
            assert page.locator("#lessonExampleCode").inner_text().strip(), (framework, number)
            checked += 1
    assert checked == 42

    # Select the challenge before expanding: outside controls are intentionally
    # blocked by the fullscreen editor.
    page.locator('[data-lesson="1"]').click()
    expect(page.locator("#lessonTitle")).to_have_text("Cores e fundo")

    # Example remains above the editor, and can be hidden when desired.
    expect(page.locator("#studentAvatar")).to_have_text("E")
    expect(page.locator("#studentCourse")).to_contain_text("E2E000007")
    page.locator("#lessonMaxWorkspace").click()
    expect(page.locator("#faExpandedBar")).to_be_visible()
    assert "lesson-workspace-expanded" in page.locator("#lessonWorkspace").get_attribute("class").split()
    assert page.locator("#lessonWorkspace .lesson-target").count() == 1
    expect(page.locator("#lessonWorkspace .lesson-target")).to_be_visible()
    expect(page.locator("#lessonLibraryDock")).to_be_hidden()
    page.locator("#faExpandedExample").click()
    expect(page.locator("#lessonWorkspace .lesson-target")).to_be_hidden()
    page.locator("#faExpandedExample").click()
    expect(page.locator("#lessonWorkspace .lesson-target")).to_be_visible()
    page.locator("#faExpandedClasses").click()
    expect(page.locator("#lessonLibraryDock")).to_be_visible()
    for tab in ("colors", "type", "spacing"):
        page.locator(f'[data-dock-tab="{tab}"]').click()
        expect(page.locator(f'[data-dock-tab="{tab}"]')).to_have_class("active")
        assert page.locator("#lessonDockResults").inner_text().strip()
    page.locator("#faExpandedClasses").click()
    expect(page.locator("#lessonLibraryDock")).to_be_hidden()

    # Failed validation must leave the learner on the current question.
    page.locator("#faExpandedValidateNext").click()
    expect(page.locator("#lessonTitle")).to_have_text("Cores e fundo")
    expect(page.locator("#faExpandedStatus")).to_contain_text("Tentativa registrada", timeout=15000)
    expect(page.locator("#faExpandedAlerts")).to_be_visible()
    expect(page.locator("#faExpandedAlerts")).to_contain_text("pendentes")
    assert page.locator("#practiceTimer").inner_text() == "00:00:00"

    # A correct solution must validate and open the following question
    # without closing the expanded workspace.
    good_code = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
                 '<title>Exercício autoral</title></head><body>'
                 '<section class="blue"><h4>Portal de Aprendizagem</h4></section>'
                 '</body></html>')
    page.evaluate("(code) => {window.__faCodeMirror.setValue(code);window.__faCodeMirror.save();}", good_code)
    # A real user key event starts time, not the code loaded by the exercise.
    page.evaluate("() => { const cm = window.__faCodeMirror; cm.setCursor(cm.lineCount()-1, cm.getLine(cm.lineCount()-1).length); cm.focus(); }")
    page.keyboard.type(" ")
    page.wait_for_function("faTimerStartedAt > 0", timeout=12000)
    page.locator("#faExpandedValidateNext").click()
    expect(page.locator("#lessonTitle")).to_have_text("Grid responsivo", timeout=15000)
    expect(page.locator("#faExpandedStatus")).to_contain_text("Próxima questão aberta")
    expect(page.locator("#faExpandedAlerts")).to_be_visible()
    expect(page.locator("#faExpandedAlerts")).to_contain_text("Atividade concluída")
    expect(page.locator("#faExpandedBar")).to_be_visible()
    page.locator("#faExpandedExit").click()
    assert "lesson-workspace-expanded" not in page.locator("#lessonWorkspace").get_attribute("class").split()
    # Alternância de contas: o aluno anterior sai, o cadastro volta vazio,
    # o ranking é ocultado e uma nova matrícula recebe progresso isolado.
    expect(page.locator("#studentLogoutHeader")).to_be_visible()
    expect(page.locator("#sessionStudentName")).to_contain_text("Estudante de Testes")
    page.locator("#studentSwitchPractice").click()
    expect(page.locator("#studentGate")).to_be_visible(timeout=15000)
    expect(page.locator("#rankingNav")).to_be_hidden()
    expect(page.locator("#studentSessionMenu")).to_be_hidden()
    assert page.locator("#registerEnrollment").input_value() == ""
    page.locator("#registerName").fill("Outro Estudante")
    page.locator("#registerEnrollment").fill("E2E000008")
    page.locator("#registerCourse").fill("Engenharia de Software")
    page.locator('#studentRegisterForm button[type="submit"]').click()
    expect(page.locator("#studentPracticeBody")).to_be_visible(timeout=15000)
    expect(page.locator("#sessionStudentName")).to_contain_text("Outro Estudante")
    expect(page.locator("#rankingNav")).to_be_visible()
    expect(page.locator("#practiceDone")).to_have_text("0/42")
    assert not errors, "\n".join(errors)
    print(f"PASS: onboarding, registration, {checked} framework/exercise UI combinations, maximization, class library, no main-page JS errors")
    browser.close()
