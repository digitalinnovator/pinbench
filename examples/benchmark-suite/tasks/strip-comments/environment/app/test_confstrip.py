from confstrip import strip_comments


def test_line_and_block_comment():
    assert strip_comments("port = 80\n# note\n") == "port = 80\n\n"
    assert strip_comments("a = /* x */ 1\n") == "a =  1\n"
