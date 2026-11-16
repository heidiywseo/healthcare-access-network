"""Recompute the default baseline (network travel times when available) and embed it in the browser preview."""
from pathlib import Path
import json,re
from engine import Model
root=Path(__file__).resolve().parent
result=Model().run({'travel_mode':'auto'})
raw=json.dumps(result,separators=(',',':'),ensure_ascii=False)
(root/'baseline_snapshot.json').write_text(raw,encoding='utf-8')
html=(root/'index.html').read_text(encoding='utf-8')
html=re.sub(r'(<script id="snapshot" type="application/json">).*?(</script>)',lambda m:m.group(1)+raw+m.group(2),html,flags=re.S)
(root/'index.html').write_text(html,encoding='utf-8')
# Create truly standalone HTML, with app.js inlined. Links to docs are for the extracted project.
app=(root/'assets'/'app.js').read_text(encoding='utf-8')
preview=html.replace('<script src="assets/app.js"></script>','<script>'+app+'</script>')
shapes=root/'assets'/'tract_boundaries.js'
preview=preview.replace('<script src="assets/tract_boundaries.js"></script>','<script>'+shapes.read_text(encoding='utf-8')+'</script>' if shapes.exists() else '')
(root/'AccessLab_Map_Preview.html').write_text(preview,encoding='utf-8')
print('Exported',len(result['flows']),'flows; default assigned',result['metrics']['assigned'])
