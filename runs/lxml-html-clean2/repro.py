from lxml.html import defs
from lxml_html_clean import Cleaner, clean_html

print(clean_html('<div><style>@impor\\t url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>@\\69mport url(http://evil.example/x.css);</style></div>'))
print(clean_html('<div><style>a{width:expre\\ssion(alert(1))}</style></div>'))
c = Cleaner(safe_attrs=defs.safe_attrs | {'style'})
print(c.clean_html('<p style="width:expre\\ssion(alert(1))">x</p>'))
print(c.clean_html('<p style="width:expre\\73sion(alert(1))">x</p>'))
print(c.clean_html('<p style="background:url(j\\avascript:alert(1))">x</p>'))
