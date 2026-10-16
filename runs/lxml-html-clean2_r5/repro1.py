from lxml_html_clean import clean_html
for h in ['<button><script></script></button>', '<applet><link></link></applet>', '<textarea></textarea>', '<button><input></button>', '<applet><param></applet>']:
    try:
        print(repr(h), '->', repr(clean_html(h)))
    except Exception as e:
        print(repr(h), '-> EXC', type(e).__name__, e)
