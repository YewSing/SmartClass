"""Make an LLM answer readable on a phone: turn leftover LaTeX into plain text.

The system prompt already asks for plain-text formulas, but models still slip into LaTeX
(`$$\\frac{a}{b}$$`, `50\\%`). The app shows plain text, so this runs on every answer before
it is saved. Code (``` blocks and `inline`) is left untouched.
"""
import re

_SYMBOLS = {
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈",
    "equiv": "≡", "sim": "~", "propto": "∝", "infty": "∞",
    "rightarrow": "→", "to": "→", "leftarrow": "←", "Rightarrow": "⇒", "implies": "⇒",
    "Leftrightarrow": "⇔", "iff": "⇔", "in": "∈", "notin": "∉", "subseteq": "⊆", "subset": "⊂",
    "cup": "∪", "cap": "∩", "emptyset": "∅", "forall": "∀", "exists": "∃", "neg": "¬",
    "land": "∧", "wedge": "∧", "lor": "∨", "vee": "∨", "sum": "Σ", "prod": "Π", "int": "∫",
    "partial": "∂", "nabla": "∇", "ldots": "...", "cdots": "...", "dots": "...", "circ": "°",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "phi": "φ", "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Pi": "Π", "Sigma": "Σ", "Phi": "Φ", "Omega": "Ω",
}
# Commands whose argument is just text: \text{if} -> if
_TEXT_CMDS = r"text|textbf|textit|textrm|mathrm|mathbf|mathit|mathsf|mathtt|operatorname|boldsymbol"

_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
_DISPLAY_RE = re.compile(r"[ \t]*(?:\$\$(.+?)\$\$|\\\[(.+?)\\\])[ \t]*", re.DOTALL)
_INLINE_PAREN_RE = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
# $...$ only when the inside looks like maths, so "costs $5 or $10" is left alone
_INLINE_DOLLAR_RE = re.compile(
    r"(?<![\\$\w])\$(?!\s)([^$\n]*?[\\^_{}][^$\n]*?|[A-Za-z])(?<!\s)\$(?![$\w])")
_FRAC_RE = re.compile(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_SQRT_RE = re.compile(r"\\sqrt\s*\{([^{}]*)\}")
_TEXT_RE = re.compile(rf"\\(?:{_TEXT_CMDS})\s*\{{([^{{}}]*)\}}")
_SCRIPT_RE = re.compile(r"([\^_])\{([^{}]*)\}")
_SYMBOL_RE = re.compile(r"\\([A-Za-z]+)(?![A-Za-z])")
_SPACING_RE = re.compile(r"\\[,;:! ]|\\quad|\\qquad|~")
_SIZING_RE = re.compile(r"\\(?:left|right|big|Big|bigg|Bigg)(?![A-Za-z])\s*")


def _group(s: str) -> str:
    """Wrap in brackets unless it's a single number/word, so a+b over c becomes (a+b)/c."""
    s = s.strip()
    return s if re.fullmatch(r"[\w.]+", s) else f"({s})"


def _convert(math: str, in_math: bool) -> str:
    """Convert LaTeX commands to text. Inside $...$ also drop leftover braces and unknown commands."""
    s = math
    if in_math:
        s = _SPACING_RE.sub(" ", s)
    else:
        s = re.sub(r"\\[,;]|\\quad|\\qquad", " ", s)
    s = _SIZING_RE.sub("", s)
    for _ in range(5):  # innermost first, so nested \frac{\frac{a}{b}}{c} works
        before = s
        s = _TEXT_RE.sub(lambda m: m.group(1), s)
        s = _FRAC_RE.sub(lambda m: f"{_group(m.group(1))}/{_group(m.group(2))}", s)
        s = _SQRT_RE.sub(lambda m: f"√{_group(m.group(1))}", s)
        s = _SCRIPT_RE.sub(lambda m: m.group(1) + _group(m.group(2)), s)
        if s == before:
            break
    s = s.replace(r"\%", "%").replace(r"\$", "$").replace(r"\&", "&").replace(r"\#", "#").replace(r"\_", "_")

    def symbol(m: re.Match) -> str:
        name = m.group(1)
        if name in _SYMBOLS:
            return _SYMBOLS[name]
        return name if in_math else m.group(0)  # \log -> log in maths; leave prose (e.g. \n) alone
    s = _SYMBOL_RE.sub(symbol, s)
    if in_math:
        s = s.replace("{", "").replace("}", "")
        s = re.sub(r"[ \t]{2,}", " ", s).strip()
    return s


def _clean_prose(text: str) -> str:
    text = _DISPLAY_RE.sub(lambda m: "\n" + _convert(m.group(1) or m.group(2), True) + "\n", text)
    text = _INLINE_PAREN_RE.sub(lambda m: _convert(m.group(1), True), text)
    text = _INLINE_DOLLAR_RE.sub(lambda m: _convert(m.group(1), True), text)
    text = _convert(text, False)  # bare LaTeX outside any delimiters
    return re.sub(r"\n{3,}", "\n\n", text)


def clean_latex(text: str) -> str:
    """Return the answer with LaTeX turned into readable text; code spans are kept as written."""
    out, last = [], 0
    for m in _CODE_RE.finditer(text):
        out.append(_clean_prose(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(_clean_prose(text[last:]))
    return "".join(out).strip()
