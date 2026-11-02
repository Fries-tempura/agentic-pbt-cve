# Claims for soupsieve.css_parser

## CLAIM-1
- evidence: —
- source:   implicit
- reading:  CSSParser builds tokens by running regexes (IDENTIFIER, CSS_ESCAPES, PAT_ATTR, ...) over a
            user-supplied selector string. Every correct tokenizer does work polynomial (here roughly linear)
            in the length of the selector, whether it accepts it or rejects it with SelectorSyntaxError.
- claim:    compile(s) returns or raises SelectorSyntaxError in time bounded by a small polynomial of len(s);
            doubling a short input must not multiply the time by orders of magnitude.
- strength: Strongest implicit form; we assert an absolute bound (< 1 s) on inputs of length <= ~60.

## CLAIM-2
- evidence: docs/src/markdown/api.md:176 — "`escape` is used to escape CSS identifiers. It follows the [CSS specification][cssom] and escapes any character that would normally cause an identifier to be invalid."
- source:   docstring (API docs)
- reading:  After escaping, the result is a valid identifier for any input; in particular it can be used as a
            class/id/tag in a selector, and the parser unescapes it back to the original (except NUL, which the
            doc example shows mapped to U+FFFD, matching CSSParser's own NUL replacement).
- claim:    For any non-empty string x, compile('.' + escape(x)) succeeds and its class equals x with '\0'->U+FFFD.
- strength: Round trip is the strongest form; "valid identifier" alone would be weaker.

## CLAIM-3
- evidence: soupsieve/css_parser.py:257 — css_unescape "Unescape CSS value."
- source:   structure
- reading:  escape/css_unescape are an inverse pair on identifiers.
- claim:    css_unescape(escape(x)) == x.replace('\0','�').
- strength: full equality.
