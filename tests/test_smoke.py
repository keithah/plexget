def test_package_imports_and_has_version():
    import plexget

    assert isinstance(plexget.__version__, str)
    assert plexget.__version__
