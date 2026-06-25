import os
import json
import shutil
import subprocess

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def main():
    base_dir = os.path.dirname(os.path.abspath(__line__)) if '__file__' in locals() else os.getcwd()
    reports_dir = os.path.join(base_dir, "workspace", "reports")
    docs_dir = os.path.join(base_dir, "sphinx_docs")
    
    if os.path.exists(docs_dir):
        shutil.rmtree(docs_dir)
    os.makedirs(docs_dir)

    # 1. Create Sphinx conf.py
    conf_content = """
import os
import sys
sys.path.insert(0, os.path.abspath('..'))
project = 'Java Migration Reports'
copyright = '2026, AI Migration System'
author = 'AI Migration System'
extensions = ['rst2pdf.pdfbuilder']
pdf_documents = [('index', u'JavaMigrationReports', u'Java Migration Reports', u'AI Migration System')]
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
"""
    with open(os.path.join(docs_dir, "conf.py"), "w") as f:
        f.write(conf_content)
        
    os.makedirs(os.path.join(docs_dir, "_static"), exist_ok=True)
    os.makedirs(os.path.join(docs_dir, "_templates"), exist_ok=True)

    # Load data
    analysis = load_json(os.path.join(reports_dir, "last_analysis.json"))
    migration = load_json(os.path.join(reports_dir, "last_migration.json"))
    conversion = load_json(os.path.join(reports_dir, "last_conversion.json"))

    # 2. Generate index.rst
    index_content = """
Welcome to Java Migration Reports
=================================

Here you can view the latest generated reports from the AI Migration System.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   analysis
   migration
   conversion
"""
    with open(os.path.join(docs_dir, "index.rst"), "w") as f:
        f.write(index_content)

    # 3. Generate analysis.rst
    analysis_content = "Repository Analysis Report\n==========================\n\n"
    if analysis:
        for k, v in analysis.items():
            analysis_content += f"**{k}**\n\n  {v}\n\n"
    else:
        analysis_content += "No analysis report found.\n"
    with open(os.path.join(docs_dir, "analysis.rst"), "w") as f:
        f.write(analysis_content)

    # 4. Generate migration.rst
    migration_content = "Migration Status Report\n=======================\n\n"
    if migration:
        for k, v in migration.items():
            if isinstance(v, list):
                migration_content += f"**{k}**\n\n"
                for item in v:
                    migration_content += f"  - {item}\n"
                migration_content += "\n"
            else:
                migration_content += f"**{k}**\n\n  {v}\n\n"
    else:
        migration_content += "No migration report found.\n"
    with open(os.path.join(docs_dir, "migration.rst"), "w") as f:
        f.write(migration_content)

    # 5. Generate conversion.rst
    conversion_content = "Code Conversion Report\n======================\n\n"
    if conversion:
        for k, v in conversion.items():
            if k == "convertedFiles" and isinstance(v, list):
                conversion_content += f"**{k}**\n\n"
                for file in v:
                    conversion_content += f"File: ``{file.get('filename')}``\n\n.. code-block:: java\n\n"
                    for line in file.get('content', '').split('\\n'):
                        conversion_content += f"    {line}\n"
                    conversion_content += "\n"
            else:
                conversion_content += f"**{k}**\n\n  {v}\n\n"
    else:
        conversion_content += "No conversion report found.\n"
    with open(os.path.join(docs_dir, "conversion.rst"), "w") as f:
        f.write(conversion_content)

    # 6. Run Sphinx Build
    print("Building Sphinx PDF Documentation...")
    import sys
    subprocess.run([sys.executable, "-m", "sphinx.cmd.build", "-b", "pdf", docs_dir, os.path.join(docs_dir, "_build", "pdf")], check=True)

    # 7. Copy the PDF to base dir
    pdf_source = os.path.join(docs_dir, "_build", "pdf", "JavaMigrationReports.pdf")
    pdf_target = os.path.join(base_dir, "JavaMigrationReports.pdf")
    if os.path.exists(pdf_source):
        shutil.copyfile(pdf_source, pdf_target)
        print(f"\\nSuccessfully generated PDF report to: {pdf_target}")
    else:
        print("Failed to find generated PDF!")

if __name__ == "__main__":
    main()
