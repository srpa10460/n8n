# HOMURA Interior Field DX (dev workspace)

Isolated from n8n packages. Python 3.11 stdlib only. No Production, payment, or external service is touched.

Run tests:   `cd homura-field-dx && python3 -m unittest discover -s tests -v`
Run case 1:  `python3 cases/run_representative.py evidence/case1`  (writes preview/ and approved/ plan.svg, model.obj, manifest.json)

Layout: src/hoa_field (units, catalog, project, interference, export, scene, blender_build) / tests / cases / docs / evidence / checkpoints
