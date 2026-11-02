from bs4 import BeautifulSoup
import soupsieve as sv
from soupsieve import css_parser as cp

print(cp.CSSParser(r'p:-soup-contains("a\\b")').process_selectors()[0].contains[0].text)
soup = BeautifulSoup(r'<p>a\b</p>', 'html.parser')
print(sv.select(r'p:-soup-contains("a\\b")', soup))
print(sv.select(r'p:-soup-contains("a\5c b")', soup))
