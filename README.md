# IFC Material Passport Validator

Standalone Python CLI tool that validates IFC (BIM) files against material passport platform requirements (e.g. [Madaster](https://madaster.com)) before upload. Checks classification codes, base quantities, materials, and property sets — outputs HTML + Excel reports for BIM coordination.

## Why?

Before uploading IFC models to Madaster for material passport analysis, models need to pass a completeness check. Missing classifications, materials, or quantities will cause import failures or inaccurate results. This tool catches issues early so you can send actionable reports back to trades before upload.

## What It Checks

| Check | Severity | Description |
|-------|----------|-------------|
| Classification | Error | NL/SfB, OmniClass, or Uniclass 2015 code present on each element |
| Base Quantities | Error | Volume, area, length, width, height populated and non-zero |
| Material Assignment | Error | Every element has a material (IfcMaterial, LayerSet, etc.) |
| Material Picklist | Warning | Material names match the Madaster approved list |
| Pset_Madaster | Info | Custom Madaster property set present with required fields |
| Building Phase | Info | Phase Created / Renovation Status populated |
| Proxy Elements | Warning | Flags IfcBuildingElementProxy (Madaster can't classify these) |

## Usage

```bash
# Validate a single IFC file
python main.py --file model.ifc

# Validate all IFC files in a folder
python main.py --folder /path/to/ifc/files

# Opens a folder picker dialog if no arguments given
python main.py
```

Reports are saved to an `output/` folder alongside the input files.

## Output

- **HTML Report** — Visual dashboard with summary scores and per-element breakdown
- **Excel Report** — Filterable workbook with summary, element details, and issues log sheets. Designed to be sent directly to subcontractors.

## Installation

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/ifc-material-passport-validator.git
cd ifc-material-passport-validator

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Requirements
- Python 3.11+
- Dependencies: ifcopenshell, ifctester, xlsxwriter, jinja2, tqdm

## Standalone Executable

A packaged `.exe` version (no Python required) can be built with:

```bash
pip install pyinstaller
pyinstaller --onedir --name IFCMPValidator \
  --collect-all ifcopenshell \
  --collect-all ifctester \
  --hidden-import ifcopenshell.ifcopenshell_wrapper \
  --add-data "reporters/templates:reporters/templates" \
  --add-data "data:data" \
  main.py
```

The executable will be in `dist/IFCMPValidator/`.

## Madaster Reference

This tool validates against requirements documented in:
- [Preparing BIM IFC source files](https://docs.madaster.com/us/en/knowledge-base/preparing-bim-ifc-source-files)
- [Madaster Property Set](https://docs.madaster.com/nl/en/knowledge-base/madaster-property-set.html)

## License

MIT
