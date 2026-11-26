import sys

import reprotrace


def test_package_imports_on_supported_python():
    assert reprotrace.__version__
    assert sys.version_info[:2] == (3, 12)
