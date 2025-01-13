from ndetect.cli import parse_args


def test_parse_args_default_mode():
    args = parse_args(["path/to/file"])
    assert args.mode == "interactive"
    assert args.threshold == 0.85
    assert args.paths == ["path/to/file"] 