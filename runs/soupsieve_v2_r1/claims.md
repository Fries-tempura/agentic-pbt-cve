# Claims for `soupsieve.css_parser`

## CLAIM-1
- evidence: css_parser.py:284-285 — `def escape(ident: str) -> str:` / `"""Escape identifier."""`; css_parser.py:257-262 `css_unescape` — "Unescape CSS value."
- source:   structure
- reading:  `escape` produces a CSS identifier; the parser's `parse_class_id` reads `.IDENT` and passes it through `css_unescape`. An escape/unescape pair claims a round trip: escaping any string must yield something the parser accepts as an identifier and which unescapes back to the original (NUL excepted — `escape` maps it to U+FFFD by spec).
- claim:    For any non-empty `s` without NUL, parsing `.` + escape(s) succeeds and the class recorded is exactly `s`.
- strength: Strongest form: exact equality, not just "parses".

## CLAIM-2
- evidence: css_parser.py:1080-1097 `parse_pseudo_contains`; css_parser.py:1105-1116 `parse_pseudo_lang` — quoted values are decoded with `css_unescape(value[1:-1], True)`; css_parser.py:257-262 "Strings allow for spanning the value on multiple strings by escaping a new line."
- source:   structure / reference (CSS Syntax: a quoted string is unescaped exactly once)
- reading:  A CSS string token's content is the unescaped text. Both pseudo-classes use the same decoding per token, so the stored text should equal `css_unescape(content, True)` — one pass. Anything that unescapes twice changes texts containing a backslash.
- claim:    For `:-soup-contains("<S>")`, the stored text equals `css_unescape(S, True)`, the same as `:lang("<S>")` stores.
- strength: Exact equality against the module's own single-pass decoder.

## CLAIM-3
- evidence: css_parser.py:744-746 — `# Value matches` / `pattern = re.compile(r'^%s$' % re.escape(value), flags)`; css_parser.py:728-731 `# Value start with`, `# Value ends with`.
- source:   comment / reference (CSS Selectors 4: `[att=val]` matches when value is exactly "val")
- reading:  "Value matches" for `=` means the whole attribute value equals `val`; `$=` means the value ends with `val`. A value with an extra trailing `\n` neither equals nor ends with `val`.
- claim:    `[x="v"]` (and `[x$="v"]`) does not match an element whose `x` is `v + "\n"`.
- strength: Direct consequence of exact equality.

## CLAIM-4
- evidence: css_parser.py:691-695 — `raise ValueError(f'Selector exceeds pseudo-class nesting limit of {SELECTOR_LIMIT}')`, `SELECTOR_LIMIT = 8192`
- source:   error message / assertion
- reading:  The author enforces a nesting limit and signals it with ValueError; below it, selectors are accepted. A pseudo-class nesting depth well under 8192 is within the stated limit and must parse (or at worst fail with the documented ValueError/SelectorSyntaxError), not RecursionError.
- claim:    `:is(` * d + `a` + `)` * d parses for d well under 8192 tokens, or raises only ValueError/SelectorSyntaxError.
- strength: Weakened to "no undocumented exception" because whether depth itself must succeed is not stated.

## CLAIM-5
- evidence: —
- source:   implicit (must not hang)
- reading:  Tokenising a selector should cost time linear in its length. `selector_iter` strips trailing whitespace with `RE_WS_END.search(pattern)` (`{WSC}*$`, unanchored at the start).
- claim:    Parsing time grows ~linearly with the amount of whitespace in a selector (doubling n must not ~quadruple time).
- strength: Ratio bound, robust to machine speed.

## CLAIM-6
- evidence: css_parser.py:119 — `CSS_ESCAPES = ... \\(?:[a-f0-9]{1,6}{WS}?` (the tokenizer accepts any 1–6 hex digit escape); css_parser.py:269-271 — `if codepoint == 0: codepoint = UNICODE_REPLACEMENT_CHAR` (the author already maps out-of-spec codepoints to U+FFFD, per CSS Syntax §4.3.7 which also covers > 0x10FFFF).
- source:   implicit (must not crash) + reference (CSS Syntax 3 §4.3.7)
- reading:  Any 6-hex-digit escape is accepted by the grammar, so `css_unescape` must handle it; the spec replaces codepoints above U+10FFFF with U+FFFD. An internal `chr()` ValueError is not a documented outcome.
- claim:    Selectors containing `\HHHHHH` with value > 0x10FFFF compile (escape decodes to U+FFFD) instead of raising `ValueError: chr() arg not in range`.
- strength: Full spec behaviour.
