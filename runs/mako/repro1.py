from mako.lookup import TemplateLookup

tl = TemplateLookup(directories=["."])
tl.put_string("index.html", "<%include file='${name}'/>")
tl.get_template("index.html").render(name="")
