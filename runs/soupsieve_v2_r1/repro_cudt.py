from bs4 import BeautifulSoup
import soupsieve as sv

soup = BeautifulSoup('<div x="foo\n"></div>', 'html.parser')
print(sv.select('div[x="foo"]', soup))
print(sv.select('div[x$="foo"]', soup))
print(sv.select('div[x|="foo"]', soup))
