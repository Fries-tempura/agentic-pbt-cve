# Claims for soupsieve.css_parser

## CLAIM-1
- evidence: soupsieve/css_parser.py:694-695 — `if self.count > SELECTOR_LIMIT: raise ValueError(f'Selector exceeds pseudo-class nesting limit of {SELECTOR_LIMIT}')`; docs/src/markdown/api.md:41 — "number of selectors in a given pattern are arbitrarily capped at ~8192. This limitation was added to prevent cases where impractical, massive selectors."
- source:   assertion / error message / reference (docs)
- reading:  The guard names its own purpose: a *nesting* limit of 8192. The library thus states
            that the boundary between accepted and rejected selectors (by size/nesting) is the
            count of 8192, and that beyond it the response is a clean ValueError. That rules
            out any other failure mode for a well-formed selector whose count is below the
            limit — in particular an interpreter-level RecursionError at a much smaller depth.
- claim:    A syntactically valid selector consisting of N nested `:is(...)` / `:not(...)` /
            `:has(...)` with total selector count well below 8192 either compiles or raises
            the documented ValueError / SelectorSyntaxError — never RecursionError.
- strength: Strongest form: any depth whose count < 8192 compiles successfully. I test that
            directly (depth up to 2000, count ≈ depth+1).

## CLAIM-2
- evidence: soupsieve/css_parser.py:267-271 — `codepoint = int(m.group(1)[1:], 16); if codepoint == 0: codepoint = UNICODE_REPLACEMENT_CHAR; value = chr(codepoint)`; CSS_ESCAPES pattern `\\[a-f0-9]{1,6}` (line 119) accepts any 1–6 hex digit escape.
- source:   structure + reference (CSS Syntax Level 3 §4.3.7 "consume an escaped code point":
            "If this number is zero, or is for a surrogate, or is greater than the maximum
            allowed code point, return U+FFFD")
- reading:  The tokenizer accepts any 1–6 hex digit escape as a valid identifier part, so the
            selector is syntactically valid. The zero→U+FFFD branch shows the author follows
            the CSS spec rule, of which the out-of-range clause is a sibling. At minimum, an
            input the grammar accepts must not raise an undocumented exception (implicit).
- claim:    css_unescape of any `\XXXXXX` escape (1–6 hex digits) returns a string and does not
            raise; compiling `.a\XXXXXX` does not raise.
- strength: Strong form (value == U+FFFD for > 0x10FFFF) also checked as a secondary assert.

## CLAIM-3
- evidence: soupsieve/css_parser.py:284-285 — `def escape(ident: str) -> str: """Escape identifier."""`; css_parser.py:257 `def css_unescape(content: str, ...)` — "Unescape CSS value."
- source:   structure (escape/unescape pair)
- reading:  An escaped identifier must be a valid CSS identifier that denotes the original
            string; that is the only purpose of escaping. Parsing `.` + escape(s) must yield a
            class selector whose class equals s. Exception: '\x00' is deliberately mapped to
            U+FFFD (CSS spec), so excluded.
- claim:    For non-empty s without NUL, compile('.' + escape(s)) has classes == (s,).
- strength: Full round-trip equality, the strongest form.

## CLAIM-4
- evidence: css_parser.py:899-927 parse_pseudo_nth; NTH grammar `[-+]?([0-9]+n?|n)([-+][0-9]+)?`
- source:   mathematics / structure
- reading:  `:nth-child(An+B)` denotes the pair (A, B); the parser must store a=A, b=B.
- claim:    For integers A, B, compiling `:nth-child({A}n{+/-}{|B|})` yields SelectorNth with a == A, n True, b == B.
- strength: exact equality.

## CLAIM-5
- evidence: —
- source:   implicit (must not hang)
- reading:  The tokenizer is a set of regexes with nested quantifiers (COMMENTS, WSC*, PAT_COMBINE).
            Parse cost must be roughly linear in pattern length.
- claim:    Compiling (or rejecting) any selector string of length ≤ ~2000 built from the
            special characters finishes within 2 seconds.
- strength: loose time bound.
