"""Phone-friendly answers (T93): LaTeX cleanup and citation renumbering. No database or LLM."""
import pytest

from app.services.kb.answer_format import clean_latex
from app.services.kb.assistant import _SYSTEM_PROMPT, SOURCE_COURSE, parse_answer
from app.services.kb.search import Passage


def _passage(n: int) -> Passage:
    return Passage(n, 100 + n, f"Lecture {n}", "Week 4", "slide", n, n, None, f"text {n}", 0.03, 0.7)


# ── system prompt ─────────────────────────────────────────────────────────────

def test_system_prompt_forbids_latex_and_asks_for_plain_formulas():
    assert "Never use LaTeX" in _SYSTEM_PROMPT
    assert "plain text" in _SYSTEM_PROMPT and "(a + b) / c" in _SYSTEM_PROMPT


# ── LaTeX conversions ─────────────────────────────────────────────────────────

def test_display_math_dollars_are_removed():
    assert clean_latex("Coverage is:\n$$C = 5$$\nwhere C is coverage.") == "Coverage is:\n\nC = 5\n\nwhere C is coverage."


def test_frac_becomes_slash_with_brackets_when_needed():
    assert clean_latex(r"$$\frac{a}{b}$$") == "a/b"
    assert clean_latex(r"$$\frac{a+b}{c}$$") == "(a+b)/c"
    assert clean_latex(r"$\dfrac{\frac{1}{2}}{n}$") == "(1/2)/n"


def test_text_command_keeps_its_words():
    assert clean_latex(r"$$\text{Coverage} = \frac{\text{tested}}{\text{total}}$$") == "Coverage = tested/total"


def test_times_becomes_multiplication_sign():
    assert clean_latex(r"$3 \times 4 = 12$") == "3 × 4 = 12"


def test_escaped_percent_becomes_percent():
    assert clean_latex(r"Coverage reached 80\% of branches.") == "Coverage reached 80% of branches."


def test_full_coverage_formula():
    raw = r"Statement coverage is $$\text{Coverage} = \frac{\text{executed}}{\text{total}} \times 100\%$$ [1]"
    assert clean_latex(raw) == "Statement coverage is\nCoverage = executed/total × 100%\n[1]"


@pytest.mark.parametrize("raw, expected", [
    (r"\(x^{2} + y_{i}\)", "x^2 + y_i"),
    (r"\[ n^{k+1} \]", "n^(k+1)"),
    (r"$\sqrt{n}$", "√n"),
    (r"$a \leq b \neq c$", "a ≤ b ≠ c"),
    (r"$\alpha \cdot \beta$", "α · β"),
    (r"$\log n$", "log n"),
    (r"$\left( a \right)$", "( a )"),
    ("the variable $n$ grows", "the variable n grows"),
])
def test_other_math_is_readable(raw, expected):
    assert clean_latex(raw) == expected


def test_bare_latex_outside_dollars_is_converted():
    assert clean_latex(r"The ratio \frac{x}{y} is 3 \times larger.") == "The ratio x/y is 3 × larger."


def test_plain_text_and_money_are_unchanged():
    text = "Testing costs $5 or $10 per run. EP and BVA [1] are black-box techniques.\n- one\n- two"
    assert clean_latex(text) == text


def test_code_is_left_as_written():
    text = 'Use `printf("%d\\n", x)` here:\n```c\nprintf("50\\%\\n");\n```\nand 80\\% done.'
    assert clean_latex(text) == 'Use `printf("%d\\n", x)` here:\n```c\nprintf("50\\%\\n");\n```\nand 80% done.'


# ── citation renumbering ──────────────────────────────────────────────────────

def test_citations_1_2_4_are_renumbered_1_2_3():
    passages = [_passage(i) for i in range(1, 6)]
    raw = "EP splits inputs [1]. BVA tests edges [2]. Both are black-box [4][1]."
    text, citations, source = parse_answer(raw, passages)
    assert text == "EP splits inputs [1]. BVA tests edges [2]. Both are black-box [3][1]."
    assert [c["n"] for c in citations] == [1, 2, 3]
    assert [c["material_id"] for c in citations] == [101, 102, 104]  # list follows the new numbers
    assert source == SOURCE_COURSE


def test_renumbering_follows_first_appearance_not_passage_order():
    passages = [_passage(i) for i in range(1, 6)]
    text, citations, _ = parse_answer("Edges [4]. Classes [2]. Again [4].", passages)
    assert text == "Edges [1]. Classes [2]. Again [1]."
    assert [(c["n"], c["material_id"]) for c in citations] == [(1, 104), (2, 102)]


def test_renumbering_drops_citations_to_missing_passages():
    text, citations, _ = parse_answer("Real [3]. Invented [7].", [_passage(i) for i in range(1, 4)])
    assert text == "Real [1]. Invented ."
    assert [(c["n"], c["material_id"]) for c in citations] == [(1, 103)]
