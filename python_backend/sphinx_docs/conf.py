
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
