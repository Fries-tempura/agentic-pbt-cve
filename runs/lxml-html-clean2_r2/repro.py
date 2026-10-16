from lxml_html_clean import Cleaner, clean_html

print(clean_html(r'<div><style>@\import url(evil.css);</style></div>'))
print(clean_html(r'<div><style>a { background: url(java\script:alert(1)) }</style></div>'))
print(clean_html(r'<div><style>a { width: e\xpression(alert(1)) }</style></div>'))
print(Cleaner(safe_attrs_only=False).clean_html(r'<div style="width: e\xpression(alert(1))">t</div>'))
print(clean_html(r'<div><style>@\69mport url(evil.css);</style></div>'))
