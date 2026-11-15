from padel.auth.tokens import make_token, read_token


def test_token_holds_the_user_id():
    assert read_token("secret", make_token("secret", 7)) == 7


def test_token_signed_with_another_secret_is_rejected():
    assert read_token("secret", make_token("other-secret", 7)) is None


def test_changed_token_is_rejected():
    token = make_token("secret", 7)

    assert read_token("secret", token[:-2] + "xx") is None


def test_expired_token_is_rejected():
    assert read_token("secret", make_token("secret", 7), max_age=-1) is None
