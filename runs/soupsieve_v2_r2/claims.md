# Claims for soupsieve.css_parser

## CLAIM-1
- evidence: —
- source:   implicit
- reading:  `CSSParser.selector_iter` and the regexes it uses (`RE_WS_BEGIN`, `RE_WS_END`, the token
            patterns) build a tokenizer over user-supplied selector text. Any tokenizer is expected to
            run in time roughly linear in the input. Nothing documents this; it holds of every
            correct implementation.
- claim:    `sv.compile(p)` (which calls `CSSParser(p).process_selectors()`) runs in roughly linear time
            in `len(p)`: doubling the length of a whitespace run should not quadruple the time.
- strength: Stated as a growth bound, not an absolute number. A weaker "finishes eventually"
            would pass on a quadratic implementation.

## CLAIM-2
- evidence: css_parser.py:691-695 — `if self.count > SELECTOR_LIMIT: raise ValueError(f'Selector exceeds pseudo-class nesting limit of {SELECTOR_LIMIT}')`
            and css_parser.py:1199/1208/`SelectorSyntaxError` raises for malformed input.
- source:   assertion (explicit guard) + implicit
- reading:  The parser contains an explicit guard for "pseudo-class nesting", with a limit of 8192
            tokens. The author's contract for over-nested selectors is therefore a `ValueError`, and
            for malformed selectors a `SelectorSyntaxError`. Every other exception (e.g.
            `RecursionError`) is undocumented. The guard implies nesting below 8192 is accepted.
- claim:    For any selector string, `sv.compile` returns or raises only `SelectorSyntaxError`,
            `ValueError`, or `NotImplementedError` (the documented at-rule/pseudo-element case);
            in particular nested `:is(` ... `)` well under the 8192 limit never raises RecursionError.
- strength: Strongest form: closed set of exception types. I did not claim that nesting up to 8192
            must succeed (the limit counts tokens, not depth), only that failure must be one of the
            documented types.

## CLAIM-3
- evidence: css_parser.py:284 — `def escape(ident: str) -> str: """Escape identifier."""`; css_parser.py:257 `css_unescape` — "Unescape CSS value."
- source:   structure
- reading:  `escape` produces a CSS identifier; the parser runs `css_unescape` on identifiers
            (`parse_class_id`). An escape function exists so that an arbitrary string can be
            placed in a selector and matched literally. NUL is mapped to U+FFFD on both sides
            (escape line 297, CSSParser.__init__ line 685), so it is excluded from equality.
- claim:    For any non-empty string `s` without NUL, compiling `'.' + escape(s)` succeeds and the
            parsed class equals `s`.
- strength: Full round trip through the actual parser, not just `css_unescape(escape(s))`.
