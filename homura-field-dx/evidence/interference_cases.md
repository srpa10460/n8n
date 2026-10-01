# Interference case table (expected vs actual)

| case | check | expected | expected text | actual | actual text | match |
|---|---|---|---|---|---|---|
| contact (face touching) | #overlap | PASS | contact | PASS | contact (0 mm), no overlap | OK |
| contact (face touching) | #distance | INFO | distance 0.000 | INFO | distance 0.000 mm (axis gaps x/y/z 0.000/-1000.000/-1000.000) | OK |
| overlap x by 100 | #overlap | FAIL | 100.000/1000.000/1000.000 | FAIL | solids overlap (penetration x/y/z = 100.000/1000.000/1000.000 mm) | OK |
| overlap x by 100 | #distance | INFO | distance 0.000 | INFO | distance 0.000 mm (axis gaps x/y/z -100.000/-1000.000/-1000.000) | OK |
| single-axis gap 300 | #overlap | PASS | no overlap | PASS | no overlap | OK |
| single-axis gap 300 | #distance | INFO | distance 300.000 | INFO | distance 300.000 mm (axis gaps x/y/z 300.000/-1000.000/-1000.000) | OK |
| diagonal gap 30/40 (Euclid 50, per-axis max 40) | #overlap | PASS | no overlap | PASS | no overlap | OK |
| diagonal gap 30/40 (Euclid 50, per-axis max 40) | #distance | INFO | distance 50.000 | INFO | distance 50.000 mm (axis gaps x/y/z 30.000/40.000/-1000.000) | OK |
| stacked above, gap 200 | #overlap | PASS | no overlap | PASS | no overlap | OK |
| stacked above, gap 200 | #distance | INFO | distance 200.000 | INFO | distance 200.000 mm (axis gaps x/y/z -1000.000/-1000.000/200.000) | OK |
| stacked, contact z | #overlap | PASS | contact | PASS | contact (0 mm), no overlap | OK |
| vertical partial overlap 100 | #overlap | FAIL | 1000.000/1000.000/100.000 | FAIL | solids overlap (penetration x/y/z = 1000.000/1000.000/100.000 mm) | OK |
| service space blocked (B at y=1300 inside 500 zone) | A#service-front | FAIL | blocked by B | FAIL | blocked by B (500 mm, basis: test input (synthetic)) | OK |
| service space free, B touching zone edge y=1500 | A#service-front | PASS | space free | PASS | space free (500 mm, basis: test input (synthetic)) | OK |
| service zone vs diagonal object outside zone footprint | A#service-front | PASS | space free | PASS | space free (500 mm, basis: test input (synthetic)) | OK |
| service undefined -> UNCHECKED, not PASS | A#service | UNCHECKED | no required service space | UNCHECKED | no required service space defined for this definition version | OK |
| rotation 90: front faces -x, B at x=200 blocks | A#service-front | FAIL | blocked by B | FAIL | blocked by B (500 mm, basis: test input (synthetic)) | OK |
| rotation 180: front faces -y, zone leaves room | A#service-front | FAIL | outside room | FAIL | extends outside room (500 mm, basis: test input (synthetic)) | OK |
| B estimated (unconfirmed) -> overlap/service UNCHECKED | #overlap | UNCHECKED | unconfirmed | UNCHECKED | an object is unconfirmed/unplaced | OK |
| B estimated (unconfirmed) -> overlap/service UNCHECKED | A#service-front | UNCHECKED | unconfirmed objects exist | UNCHECKED | clear of known objects, but unconfirmed objects exist: B (500 mm, basis: test input (synthetic)) | OK |
| door object without opening envelope -> UNCHECKED | A#opening | UNCHECKED | without a declared opening | UNCHECKED | door/drawer object without a declared opening envelope | OK |
