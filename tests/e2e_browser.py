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

    # The expanded workspace should keep the reference and class library available.
    page.locator("#lessonMaxWorkspace").click()
    expect(page.locator("#lessonWorkspace")).to_have_class("lesson-workspace-expanded", timeout=5000)
    assert page.locator("#lessonWorkspace .lesson-target").count() == 1
    expect(page.locator("#lessonLibraryDock")).to_be_visible()
    for tab in ("colors", "type", "spacing"):
        page.locator(f'[data-dock-tab="{tab}"]').click()
        expect(page.locator(f'[data-dock-tab="{tab}"]')).to_have_class("active")
        assert page.locator("#lessonDockResults").inner_text().strip()
    page.locator("#lessonMaxWorkspace").click()
    expect(page.locator("#lessonWorkspace")).not_to_have_class("lesson-workspace-expanded")
    assert not errors, "\n".join(errors)
    print(f"PASS: onboarding, registration, {checked} framework/exercise UI combinations, maximization, class library, no main-page JS errors")
    browser.close()
