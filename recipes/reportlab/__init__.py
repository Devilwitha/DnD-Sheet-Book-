"""Package ReportLab 4 without the optional native rendering accelerators."""
from pythonforandroid.recipe import PythonRecipe


class ReportLabRecipe(PythonRecipe):
    version = '4.4.10'
    url = 'https://files.pythonhosted.org/packages/source/r/reportlab/reportlab-{version}.tar.gz'
    depends = ['setuptools', 'Pillow', 'charset-normalizer']
    site_packages_name = 'reportlab'


recipe = ReportLabRecipe()
