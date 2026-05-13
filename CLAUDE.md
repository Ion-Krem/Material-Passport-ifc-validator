# Madaster IFC Validator

## Project Overview
Standalone local Python CLI tool that validates IFC (BIM) files against Madaster platform requirements before upload. Checks completeness of classification codes, base quantities, materials, and property sets. Outputs HTML + Excel reports for BIM coordinators to send back to trades/subcontractors.

**This is NOT part of NeuraBIM yet.** Standalone tool for personal use. Will integrate into NeuraBIM audit tools later.

## Tech Stack
- Python 3.11+
- ifcopenshell — IFC file parsing (v0.8.5+)
- ifctester — IDS-based validation
- xlsxwriter — Excel report generation
- jinja2 — HTML report templating
- tqdm — CLI progress bars
- tkinter (built-in) — folder picker dialog

## Response Rules
1. Code only — skip lengthy explanations
2. One step at a time — complete one task, then stop
3. Wait for approval — don't proceed to next step without confirmation
4. Minimal commentary — 1-2 sentences max if explanation needed
5. Always work on main branch

## Project Structure
```
madaster-ifc-validator/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── main.py                        # Entry point: argparse CLI + tkinter folder picker
├── validator/
│   ├── __init__.py
│   ├── core.py                    # Per-element validation orchestrator
│   ├── classification_checker.py  # NL/SfB, OmniClass, Uniclass validation
│   ├── quantity_checker.py        # Base quantities validation
│   ├── material_checker.py        # Material assignment + picklist matching
│   ├── pset_madaster_checker.py   # Pset_Madaster property set validation
│   ├── phase_checker.py           # Building phase / renovation status
│   ├── proxy_checker.py           # IfcBuildingElementProxy overuse detection
│   └── batch.py                   # Multi-file processing with ProcessPoolExecutor
├── reporters/
│   ├── __init__.py
│   ├── html_report.py             # Jinja2 + Bootstrap → standalone .html
│   ├── excel_report.py            # xlsxwriter → color-coded .xlsx
│   └── templates/
│       └── report.html            # Jinja2 template
├── data/
│   ├── madaster.ids               # IDS specification (if using IfcTester)
│   └── material_picklist.json     # Approved Madaster materials list
└── tests/
    └── test_validators.py
```

## Validation Checks (Madaster Requirements)

### 1. Classification Codes
- Check for IfcClassificationReference or IfcExternalReference on each element
- Valid systems: NL/SfB (2 or 4 digit), OmniClass Table 21 (6/8/10 digit), Uniclass 2015 (Ss_ prefix)
- Use `ifcopenshell.util.classification.get_references(element)`
- Flag: MISSING_CLASSIFICATION, INVALID_CLASSIFICATION_FORMAT

### 2. Base Quantities (IfcElementQuantity)
- Check for populated, non-zero quantities per element type
- Volume lookup order: NetVolume → Volume → GrossVolume
- Area lookup order: NetSideArea → GrossSideArea → TotalSurfaceArea → GrossSurfaceArea → OuterSurfaceArea → CrossSectionArea → NetFootprintArea → GrossFootprintArea → GrossArea → Area
- Length, Width, Height, Depth from IfcQuantityLength
- Weight from IfcQuantityWeight
- Use `ifcopenshell.util.element.get_psets(element, qtos_only=True)`
- Flag: MISSING_QUANTITIES, ZERO_VOLUME, ZERO_AREA

### 3. Material Assignment
- Every IfcBuildingElement must have a material via IfcMaterialSelect
- Handles: IfcMaterial, IfcMaterialLayerSetUsage, IfcMaterialLayerSet, IfcMaterialList, IfcMaterialConstituentSet
- For LayerSet elements: check each layer has Material.Name and Thickness > 0
- Volume calculation for layers: Area × Thickness
- Use `ifcopenshell.util.element.get_material(element)`
- Flag: MISSING_MATERIAL, EMPTY_MATERIAL_NAME, ZERO_THICKNESS_LAYER

### 4. Material Picklist Matching
- Material names should match the Madaster approved picklist (fuzzy match OK)
- Picklist stored in data/material_picklist.json (extracted from Madaster PDF)
- Flag: UNKNOWN_MATERIAL (warning, not error)

### 5. Pset_Madaster (Custom Property Set)
- Check if Pset_Madaster exists on elements
- Key properties: MaterialOrProductId, MaterialOrProductName, Volume, Area, Length, Width, Height, Depth, Weight, Classification, Phase
- When present, Madaster prioritizes these over standard IFC properties
- Use `ifcopenshell.util.element.get_pset(element, "Pset_Madaster")`
- Flag: MISSING_PSET_MADASTER (info level — not always required)

### 6. Building Phase
- Check for phase property via: Phase Created, Renovation Status, or Phase
- Valid phase values map to: Demolition (Demolition/To be demolished/Sloop), New (Nieuw/New), Casco (casco/existing/bestaand)
- Case-insensitive matching
- Construction phases: Existing = Demolition + Casco, Final = Casco + New
- Flag: MISSING_PHASE

### 7. IfcBuildingElementProxy Detection
- Flag elements using IfcBuildingElementProxy — Madaster cannot classify these
- Report count and percentage of total elements
- Flag: PROXY_ELEMENT (warning)

## Severity Levels
- **ERROR** — Will cause Madaster import failure or incorrect analysis (missing material, missing quantities)
- **WARNING** — May reduce quality of Madaster analysis (unknown material name, proxy elements)
- **INFO** — Optional enhancement (missing Pset_Madaster, missing phase)

## Report Output Format

### HTML Report
- Summary dashboard: total elements, pass/fail counts per check, overall score
- Per-file breakdown if multiple IFC files
- Color-coded: green (pass), red (error), amber (warning), blue (info)
- Standalone file with embedded CSS (no external dependencies)

### Excel Report
- Sheet 1: Summary — file name, total elements, error/warning/info counts
- Sheet 2: Element Details — one row per element with columns: GlobalId, Name, Type, Classification, Material, HasQuantities, Phase, Issues
- Sheet 3: Issues Log — one row per issue: Element GlobalId, Check Name, Severity, Message
- Color-coded cells, auto-filters enabled, frozen header row

## Key IfcOpenShell Patterns

```python
import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.classification

model = ifcopenshell.open("model.ifc")

# Get all building elements (walls, slabs, beams, columns, etc.)
elements = model.by_type("IfcBuildingElement")

# Classification references
refs = ifcopenshell.util.classification.get_references(element)

# Base quantities (quantity sets only)
qtos = ifcopenshell.util.element.get_psets(element, qtos_only=True)

# Property sets only
psets = ifcopenshell.util.element.get_psets(element, psets_only=True)

# Specific property set
madaster_pset = ifcopenshell.util.element.get_pset(element, "Pset_Madaster")

# Material
material = ifcopenshell.util.element.get_material(element)
```

## Performance Notes
- ifcopenshell parses ~20 MB/s — a 100MB file loads in ~5s
- Use `ifcopenshell.open(path, should_stream=True)` for files >500MB
- No geometry processing needed — only alphanumeric data
- Multi-file: use ProcessPoolExecutor with max 4 workers
- Each worker opens files independently (SWIG objects can't be pickled)

## Distribution
- Package with PyInstaller using --onedir mode (not --onefile)
- Must use: `--collect-all ifcopenshell --collect-all ifctester`
- Hidden import: `--hidden-import ifcopenshell.ifcopenshell_wrapper`
- Test packaging early — C++ bindings cause most issues

## Madaster Material Picklist (from requirements doc)
The full picklist is in data/material_picklist.json. Key materials include:
Concrete (various grades C20/25, C30/35, C30/37, C45/55), Steel, Stainless steel, Reinforcing steel B500/B500A, Structural steel, Aluminum, Copper, Brass, Bronze, Timber (Oak, Pine, Beech, Birch, Teak, etc.), Brick, Glass, Glass wool, Rock wool, Mineral wool, EPS polystyrene, XPS Polystyrene, PIR Polyisocyanurate, PU Polyurethane foam, Plasterboard, Concrete block, CLT Cross Laminated Timber, and ~200 more.

## Common Gotchas
1. IfcOpenShell auto-detects IFC schema (IFC2x3, IFC4, IFC4x3) — no config needed
2. `get_psets()` returns dict of dicts — outer key is pset name, inner keys are property names
3. `get_material()` returns None if no material — always check for None
4. Classification `Identification` field contains the code, `ReferencedSource` contains the system name
5. Some Revit exports use `IfcClassificationReference` without a parent `IfcClassification` — handle gracefully
6. Material names in IFC may not exactly match Madaster picklist — use case-insensitive + fuzzy matching
7. Phase properties may be in different psets depending on authoring tool (Revit vs ArchiCAD)
