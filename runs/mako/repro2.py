from mako.lookup import TemplateLookup

tl = TemplateLookup(directories=["/srv/templates"])
print(tl.filename_to_uri("/srv/templates_backup/secret.html"))
