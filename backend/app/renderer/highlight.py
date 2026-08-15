"""Syntax highlighting utility using Pygments with a custom dark cyber-technical theme."""
from __future__ import annotations

import html
from typing import Optional
from pygments import highlight
from pygments.formatter import Formatter
from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
from pygments.token import (
    Comment,
    Error,
    Generic,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
)

# Language alias mapping to ensure Pygments recognizes standard tags
LANG_ALIASES = {
    "csharp": "c#",
    "cpp": "c++",
    "sh": "bash",
    "plaintext": "text",
    "dockerfile": "docker",
}


class StudyReelHTMLFormatter(Formatter):
    """Custom Pygments HTML Formatter producing sleek, dark-themed styled token spans."""

    def __init__(self, **options):
        super().__init__(**options)
        self.show_line_numbers = options.get("show_line_numbers", True)

    def _get_token_class(self, ttype) -> str:
        if ttype in Keyword.Constant or ttype in Keyword.Type:
            return "text-cyan-400 font-medium"
        elif ttype in Keyword:
            return "text-sky-400 font-semibold"
        elif ttype in Name.Function or ttype in Name.Class:
            return "text-indigo-300 font-semibold"
        elif ttype in Name.Builtin or ttype in Name.Builtin.Pseudo:
            return "text-teal-300 font-medium"
        elif ttype in Name.Decorator:
            return "text-amber-300 font-medium"
        elif ttype in Name.Variable or ttype in Name.Attribute:
            return "text-slate-200"
        elif ttype in String.Doc or ttype in String.Interpol:
            return "text-emerald-400 italic"
        elif ttype in String:
            return "text-emerald-300"
        elif ttype in Number:
            return "text-amber-400 font-medium"
        elif ttype in Operator:
            return "text-pink-400 font-medium"
        elif ttype in Punctuation:
            return "text-slate-400"
        elif ttype in Comment:
            return "text-slate-500 italic"
        elif ttype in Generic.Heading or ttype in Generic.Subheading:
            return "text-sky-300 font-bold"
        elif ttype in Generic.Deleted:
            return "text-rose-400 bg-rose-950/40"
        elif ttype in Generic.Inserted:
            return "text-emerald-400 bg-emerald-950/40"
        elif ttype in Error:
            return "text-rose-400 underline decoration-rose-500"
        return "text-slate-100"

    def format(self, tokensource, outfile):
        lines = []
        current_line_tokens = []

        for ttype, value in tokensource:
            parts = value.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    lines.append(current_line_tokens)
                    current_line_tokens = []
                if part:
                    cls = self._get_token_class(ttype)
                    escaped = html.escape(part)
                    current_line_tokens.append(f'<span class="{cls}">{escaped}</span>')

        if current_line_tokens or not lines:
            lines.append(current_line_tokens)

        # Remove trailing empty line often added by lexers
        if lines and len(lines) > 1 and not lines[-1]:
            lines.pop()

        total_lines = len(lines)
        num_width = len(str(total_lines))

        outfile.write('<div class="font-mono text-sm leading-relaxed select-none">\n')
        for idx, line_spans in enumerate(lines, start=1):
            line_html = "".join(line_spans) if line_spans else "&nbsp;"
            if self.show_line_numbers:
                outfile.write(
                    f'<div class="flex items-baseline py-[2px] px-2 rounded hover:bg-slate-800/40 transition-colors group">'
                    f'<span class="select-none text-right pr-4 text-slate-600 font-mono text-xs w-8 group-hover:text-slate-400 transition-colors">{idx:>{num_width}}</span>'
                    f'<div class="flex-1 font-mono text-slate-100 break-words whitespace-pre-wrap overflow-hidden">{line_html}</div>'
                    f'</div>\n'
                )
            else:
                outfile.write(
                    f'<div class="py-[2px] px-2 font-mono text-slate-100 break-words whitespace-pre-wrap overflow-hidden">{line_html}</div>\n'
                )
        outfile.write('</div>\n')


def highlight_code(code: str, language: Optional[str] = None, show_line_numbers: bool = True) -> str:
    """Highlight source code with Pygments using dark brand styles."""
    if not code:
        return ""

    lang_str = str(language).lower() if language else "text"
    lang_str = LANG_ALIASES.get(lang_str, lang_str)

    try:
        lexer = get_lexer_by_name(lang_str, stripall=True)
    except Exception:
        try:
            lexer = guess_lexer(code)
        except Exception:
            lexer = TextLexer()

    formatter = StudyReelHTMLFormatter(show_line_numbers=show_line_numbers)
    return highlight(code, lexer, formatter)
