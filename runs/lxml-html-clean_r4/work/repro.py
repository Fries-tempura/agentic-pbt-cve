from lxml_html_clean import clean_html

print(clean_html('<div><style>@import url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@impor\\74  url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@\\69mport url(http://evil.example/x.css);</style></div>'))
