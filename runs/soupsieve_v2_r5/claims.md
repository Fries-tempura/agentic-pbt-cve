# Claims for soupsieve.css_parser (soupsieve 2.9 checkout)

## CLAIM-1
- evidence: —
- source:   implicit
- reading:  CSSParser builds tokens by matching regexes (IDENTIFIER, WSC, COMMENTS) against
            user-supplied selector text. Every correct selector parser does work roughly linear in
            the selector length, whether it accepts the selector or rejects it with
            SelectorSyntaxError. Nothing in the code says so, but nothing correct breaks it.
- claim:    Parsing (or rejecting) a selector of length n costs O(n); doubling n should roughly
            double the time, not quadruple it.
- strength: Strongest implicit form. I assert a growth-ratio bound (time(4n)/time(n) well under 16)
            and not an absolute wall-clock time, so machine speed does not matter.

## CLAIM-2
- evidence: css_parser.py:122-125 — `IDENTIFIER = ... (?:[^\x00-\x2f...]|{CSS_ESCAPES})+ ... ` and
            css_parser.py:119 `CSS_ESCAPES = fr'(?:\\(?:[a-f0-9]{{1,6}}{WS}?|[^\r\n\f]|$))'`;
            css_parser.py:177 RE_CSS_ESC; css_parser.py:264-279 `replace` (`chr(codepoint)`).
- source:   structure / reference (CSS Syntax Level 3 §4.3.7 "consume an escaped code point")
- reading:  The tokenizer accepts any 1-6 hex digit escape inside an identifier, so `.\110000` is
            tokenized as a class selector. css_unescape is the function that turns those escapes into
            characters, and its own docstring says "Unescape CSS value"; it already replaces 0 with
            U+FFFD (line 269-270), following CSS Syntax which says a code point that is zero, a
            surrogate, or greater than U+10FFFF becomes U+FFFD. Whatever value it chooses, a
            selector the tokenizer has accepted must not crash with an undocumented exception.
- claim:    For every 1-6 digit hex escape, css_unescape returns a str (no exception), and
            compiling a selector `.\<hex>` either succeeds or raises SelectorSyntaxError.
- strength: I state the weaker "must not crash" form as the tested claim; the stronger "returns
            U+FFFD for > 0x10FFFF" follows the spec but the code only implements the 0 case, so I
            only note it in the report rather than assert it.

## CLAIM-3
- evidence: css_parser.py:284 `def escape(ident: str) -> str: """Escape identifier."""` and
            soupsieve/__init__.py exports it as `soupsieve.escape`.
- source:   docstring + structure (escape / unescape pair)
- reading:  Escaping an identifier means producing CSS text that denotes that identifier. The
            module's own decoder is css_unescape; the selector `.` + escape(s) must therefore parse
            as a single class selector whose class name is s (except NUL, which escape maps to
            U+FFFD by design, line 296-297).
- claim:    For any non-empty s without NUL, parsing `'.' + escape(s)` yields exactly one selector
            with classes == (s,).
- strength: Strongest: full round trip through the real parser, not just css_unescape.

## CLAIM-4
- evidence: css_parser.py:1321 "# Ignore whitespace and comments at start and end of pattern"
- source:   comment
- reading:  Leading/trailing whitespace and comments are insignificant.
- claim:    Parsing ws1 + sel + ws2 gives the same SelectorList as parsing sel.
- strength: Equality of the frozen structures (they are hashable/comparable).

## CLAIM-5
- evidence: css_parser.py:20 `SELECTOR_LIMIT = 8192`; css_parser.py:694-695
            `raise ValueError(f'Selector exceeds pseudo-class nesting limit of {SELECTOR_LIMIT}')`
- source:   assertion (explicit guard) + implicit (must not crash)
- reading:  The parser has its own guard for oversized selectors: it counts tokens and raises
            ValueError above 8192. So selectors below that count are meant to be processed, and
            selectors above it are meant to be rejected with that ValueError, not some other error.
- claim:    A selector of k < 8192 compound selectors joined by descendant combinators compiles
            without raising RecursionError.
- strength: Found while running the CLAIM-1 test (unit 'a '). Added here so the finding traces to
            a claim.
